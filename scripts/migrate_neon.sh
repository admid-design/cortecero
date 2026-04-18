#!/usr/bin/env bash
# migrate_neon.sh — Aplica migraciones directamente contra Neon (sin Docker).
#
# Uso:
#   DATABASE_URL="postgresql://..." ./scripts/migrate_neon.sh [--target NNN] [--dry-run]
#
# Variables de entorno:
#   DATABASE_URL   URL de conexión PostgreSQL (requerida)
#   MIGRATIONS_DIR Override de carpeta de migraciones (opcional)
#
# Ejemplos:
#   # Aplicar todas las migraciones
#   DATABASE_URL="$NEON_DATABASE_URL" ./scripts/migrate_neon.sh
#
#   # Aplicar solo hasta la 027 (modo seguro para hardening)
#   DATABASE_URL="$NEON_DATABASE_URL" ./scripts/migrate_neon.sh --target 027
#
#   # Ver qué se aplicaría sin ejecutar
#   DATABASE_URL="$NEON_DATABASE_URL" ./scripts/migrate_neon.sh --dry-run

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# ── Validar DATABASE_URL ────────────────────────────────────────────────────
if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL no está definida." >&2
  echo "       Ejemplo: DATABASE_URL='postgresql://user:pass@host/db?sslmode=require' ./scripts/migrate_neon.sh" >&2
  exit 1
fi

echo "================================================================"
echo "  CorteCero — Migraciones → Neon"
echo "================================================================"
echo "  Target DB: ${DATABASE_URL%%@*}@***"   # oculta credenciales
echo ""

# ── Activar venv si existe ──────────────────────────────────────────────────
if [[ -f "backend/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "backend/.venv/bin/activate"
  echo "  venv activado: backend/.venv"
elif [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
  echo "  venv activado: .venv"
fi

# ── Instalar psycopg2 si no está disponible ─────────────────────────────────
if ! python3 -c "import psycopg2" 2>/dev/null; then
  echo "  psycopg2 no encontrado — instalando (solo para este entorno)..."
  pip install psycopg2-binary --quiet --break-system-packages 2>/dev/null || \
  pip install psycopg2-binary --quiet
fi

echo ""
# ── Ejecutar runner ─────────────────────────────────────────────────────────
python3 backend/scripts/apply_migration.py "$@"

echo ""
echo "================================================================"
echo "  Listo."
echo "================================================================"
