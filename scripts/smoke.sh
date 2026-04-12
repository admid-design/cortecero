#!/usr/bin/env bash
# smoke.sh — Smoke test de Google Route Optimization
#
# Variables de entorno:
#   GOOGLE_APPLICATION_CREDENTIALS  — path al service account .json
#   GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID — default: samurai-system
#   CORTECERO_ROUTE_ID              — UUID de ruta draft existente (opcional)
#   SMOKE_LIST_ROUTES=1             — solo listar rutas, no optimizar
#   SMOKE_CREATE_ROUTE=1            — crear ruta y optimizar
#
# Uso:
#   ./scripts/smoke.sh
#   SMOKE_LIST_ROUTES=1 ./scripts/smoke.sh
#   CORTECERO_ROUTE_ID=<uuid> ./scripts/smoke.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Verificar que el backend responde
echo "Verificando backend en http://localhost:8000 ..."
HEALTH=$(curl -sf http://localhost:8000/health 2>/dev/null || echo "DOWN")
if [[ "$HEALTH" != *"ok"* ]]; then
  echo "[ERROR] Backend no responde. Levanta el stack primero:"
  echo "  docker compose up -d postgres backend"
  exit 1
fi
echo "Backend: OK"

echo ""
echo "================================================================"
echo "  CorteCero — Smoke Google Route Optimization"
echo "================================================================"

GOOGLE_APPLICATION_CREDENTIALS="${GOOGLE_APPLICATION_CREDENTIALS:-$HOME/.config/kelko/google/route-optimization-sa.json}"
GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID="${GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID:-samurai-system}"

export GOOGLE_APPLICATION_CREDENTIALS
export GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID

python3 backend/scripts/smoke_google_optimization.py

echo ""
echo "================================================================"
echo "  Smoke finalizado"
echo "================================================================"
