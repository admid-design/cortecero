"""apply_migration.py — Runner de migraciones SQL idempotente.

Uso:
    DATABASE_URL=<url> python3 backend/scripts/apply_migration.py [--target NNN]

Opciones:
    --target NNN   Aplica solo migraciones cuyo prefijo numérico <= NNN.
                   Ejemplo: --target 027 aplica 001..027 y omite 028+.

Resolución de la carpeta de migraciones (orden de prioridad):
    1. Variable de entorno MIGRATIONS_DIR (path absoluto o relativo)
    2. <repo_root>/db/migrations  (estructura estándar de CorteCero)
    3. <backend_root>/db/migrations  (fallback legacy)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg2


def _find_migrations_dir() -> Path:
    """Resuelve la carpeta de migraciones siguiendo el orden de prioridad documentado."""
    # 1. Override explícito por env
    env_override = os.getenv("MIGRATIONS_DIR")
    if env_override:
        p = Path(env_override)
        if p.is_dir():
            return p
        raise SystemExit(f"MIGRATIONS_DIR={env_override!r} no es un directorio accesible")

    script_dir = Path(__file__).resolve().parents[0]  # backend/scripts/
    backend_root = script_dir.parent                  # backend/
    repo_root = backend_root.parent                   # cortecero/

    # 2. Estructura estándar: <repo_root>/db/migrations
    candidate_repo = repo_root / "db" / "migrations"
    if candidate_repo.is_dir():
        return candidate_repo

    # 3. Fallback legacy: <backend_root>/db/migrations
    candidate_legacy = backend_root / "db" / "migrations"
    if candidate_legacy.is_dir():
        return candidate_legacy

    raise SystemExit(
        f"No se encontró la carpeta de migraciones.\n"
        f"  Buscado en: {candidate_repo}\n"
        f"              {candidate_legacy}\n"
        f"  Puedes sobreescribir con: MIGRATIONS_DIR=<path>"
    )


def _strip_driver_prefix(url: str) -> str:
    """Elimina el prefijo de driver SQLAlchemy para que psycopg2 acepte la URL."""
    for prefix in ("postgresql+psycopg2://", "postgresql+psycopg://"):
        if url.startswith(prefix):
            return url.replace(prefix, "postgresql://", 1)
    return url


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Aplica migraciones SQL a la base de datos.")
    parser.add_argument(
        "--target",
        metavar="NNN",
        default=None,
        help="Número máximo de migración a aplicar (ej. 027). Omite las de número superior.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Lista las migraciones que se aplicarían sin ejecutarlas.",
    )
    args = parser.parse_args(argv)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL es requerida (variable de entorno)")
    database_url = _strip_driver_prefix(database_url)

    migrations_dir = _find_migrations_dir()
    all_files = sorted(migrations_dir.glob("*.sql"))
    if not all_files:
        raise SystemExit(f"No se encontraron archivos .sql en {migrations_dir}")

    # Filtrar por --target si se especificó
    if args.target:
        target_prefix = args.target.lstrip("0") or "0"  # "027" → "27" para comparación numérica
        def _num(f: Path) -> int:
            return int(f.name.split("_")[0])
        target_num = int(target_prefix)
        migration_files = [f for f in all_files if _num(f) <= target_num]
        skipped = len(all_files) - len(migration_files)
    else:
        migration_files = all_files
        skipped = 0

    print(f"Migraciones a aplicar : {len(migration_files)}")
    if skipped:
        print(f"Omitidas (> {args.target})  : {skipped}")
    if args.dry_run:
        for f in migration_files:
            print(f"  [DRY-RUN] {f.name}")
        return

    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    applied = 0
    try:
        cursor = conn.cursor()
        for migration_file in migration_files:
            sql_text = migration_file.read_text(encoding="utf-8")
            cursor.execute(sql_text)
            print(f"  OK  {migration_file.name}")
            applied += 1
    except Exception as exc:
        print(f"\nERROR aplicando migración: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    finally:
        conn.close()

    print(f"\nAplicadas {applied} migraciones desde {migrations_dir}")


if __name__ == "__main__":
    main()
