#!/usr/bin/env bash
# migrate.sh — Aplica migraciones pendientes contra la DB local
# Requiere que el stack esté corriendo: docker compose up -d postgres
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "================================================================"
echo "  CorteCero — Migraciones"
echo "================================================================"

echo ""
echo "Aplicando migraciones en db/migrations/ ..."
docker compose run --rm backend python scripts/apply_migration.py

echo ""
echo "================================================================"
echo "  Migraciones aplicadas"
echo "================================================================"
