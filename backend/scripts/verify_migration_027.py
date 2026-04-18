"""verify_migration_027.py — Verifica que la migration 027 está aplicada en la DB.

Comprueba la presencia de los 3 FK constraints y los 2 índices que instala
027_fk_indexes_hardening.sql consultando directamente el catálogo de PostgreSQL.

Uso:
    DATABASE_URL=<url> python3 backend/scripts/verify_migration_027.py

Salida:
    Tabla por objeto con PASS / FAIL y detalles.
    Exit 0 si todo está presente; Exit 1 si falta algún objeto.
"""
from __future__ import annotations

import os
import sys

import psycopg2

# ── Objetos esperados ────────────────────────────────────────────────────────

EXPECTED_CONSTRAINTS: list[dict] = [
    {
        "name": "fk_stop_proofs_route_stop",
        "table": "stop_proofs",
        "foreign_table": "route_stops",
        "description": "stop_proofs.route_stop_id → route_stops(id) ON DELETE CASCADE",
    },
    {
        "name": "fk_stop_proofs_route",
        "table": "stop_proofs",
        "foreign_table": "routes",
        "description": "stop_proofs.route_id → routes(id) ON DELETE CASCADE",
    },
    {
        "name": "fk_route_messages_route",
        "table": "route_messages",
        "foreign_table": "routes",
        "description": "route_messages.route_id → routes(id) ON DELETE CASCADE",
    },
]

EXPECTED_INDEXES: list[dict] = [
    {
        "name": "idx_orders_tenant_status",
        "table": "orders",
        "description": "orders(tenant_id, status) — hot-path colas",
    },
    {
        "name": "idx_route_stops_route_status",
        "table": "route_stops",
        "description": "route_stops(route_id, status) — hot-path detalle ruta",
    },
]

# ── Queries al catálogo ──────────────────────────────────────────────────────

CONSTRAINT_QUERY = """
SELECT
    c.conname        AS constraint_name,
    ct.relname       AS table_name,
    ft.relname       AS foreign_table,
    c.confdeltype    AS delete_action   -- 'c' = CASCADE
FROM pg_constraint c
JOIN pg_class ct ON ct.oid = c.conrelid
JOIN pg_class ft ON ft.oid = c.confrelid
WHERE c.contype = 'f'
  AND c.conname = %s
  AND ct.relname = %s;
"""

INDEX_QUERY = """
SELECT
    i.relname    AS index_name,
    t.relname    AS table_name,
    ix.indisunique
FROM pg_index ix
JOIN pg_class i ON i.oid = ix.indexrelid
JOIN pg_class t ON t.oid = ix.indrelid
WHERE i.relname = %s
  AND t.relname = %s;
"""


# ── Helpers ──────────────────────────────────────────────────────────────────

def _strip_prefix(url: str) -> str:
    for prefix in ("postgresql+psycopg2://", "postgresql+psycopg://"):
        if url.startswith(prefix):
            return url.replace(prefix, "postgresql://", 1)
    return url


def _pad(s: str, width: int) -> str:
    return s.ljust(width)


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL es requerida")
    database_url = _strip_prefix(database_url)

    conn = psycopg2.connect(database_url)
    try:
        cur = conn.cursor()
        results: list[tuple[str, str, str, str]] = []  # (kind, name, status, detail)
        failures = 0

        print()
        print("═" * 70)
        print("  Verificación migration 027 — HARDENING-DB-001")
        print("═" * 70)

        # ── Constraints ────────────────────────────────────────────────────
        print()
        print("  FK CONSTRAINTS")
        print("  " + "─" * 66)
        for spec in EXPECTED_CONSTRAINTS:
            cur.execute(CONSTRAINT_QUERY, (spec["name"], spec["table"]))
            row = cur.fetchone()
            if row:
                on_delete = row[3]
                cascade_ok = on_delete == "c"
                status = "PASS" if cascade_ok else "WARN (no CASCADE)"
                detail = f"ON DELETE {'CASCADE' if cascade_ok else repr(on_delete)}"
            else:
                status = "FAIL"
                detail = "constraint no encontrado"
                failures += 1
            print(f"  [{status:^4}]  {_pad(spec['name'], 34)}  {detail}")
            results.append(("FK", spec["name"], status, detail))

        # ── Índices ────────────────────────────────────────────────────────
        print()
        print("  ÍNDICES")
        print("  " + "─" * 66)
        for spec in EXPECTED_INDEXES:
            cur.execute(INDEX_QUERY, (spec["name"], spec["table"]))
            row = cur.fetchone()
            if row:
                status = "PASS"
                detail = f"en tabla {spec['table']}"
            else:
                status = "FAIL"
                detail = "índice no encontrado"
                failures += 1
            print(f"  [{status:^4}]  {_pad(spec['name'], 34)}  {detail}")
            results.append(("IDX", spec["name"], status, detail))

        # ── Resumen ────────────────────────────────────────────────────────
        print()
        print("═" * 70)
        total = len(EXPECTED_CONSTRAINTS) + len(EXPECTED_INDEXES)
        passed = total - failures
        if failures == 0:
            print(f"  RESULTADO: {passed}/{total} objetos presentes — migration 027 APLICADA ✓")
        else:
            print(f"  RESULTADO: {passed}/{total} objetos presentes — {failures} FALTANTES ✗")
            print()
            print("  Para aplicar: DATABASE_URL=... ./scripts/migrate_neon.sh --target 027")
        print("═" * 70)
        print()

    finally:
        conn.close()

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
