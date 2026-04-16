#!/usr/bin/env bash
# DEMO-OPT-001 — Smoke completo Google Route Optimization
#
# Uso: bash scripts/demo-opt-001-smoke.sh
#
# Requiere:
#   - Docker corriendo con la imagen backend actualizada
#   - Service account en ~/.config/kelko/google/route-optimization-sa.json
#
# Lo que hace:
#   1. Verifica que el backend responda en localhost:8000
#   2. Prepara las órdenes geo-ready en el tenant demo (via docker run)
#   3. Lista rutas disponibles
#   4. Crea una ruta nueva y ejecuta optimize contra Google Route Optimization API

set -euo pipefail

CREDS="${HOME}/.config/kelko/google/route-optimization-sa.json"
PROJECT_ID="samurai-system"

echo ""
echo "════════════════════════════════════════════════"
echo "  DEMO-OPT-001: Google Route Optimization Smoke"
echo "════════════════════════════════════════════════"
echo ""

# ── 1. Verificar backend ───────────────────────────────────────────────────
echo "[1/4] Verificando backend en localhost:8000..."
READY=0
for i in $(seq 1 24); do
  if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "      ✓ Backend listo"
    READY=1
    break
  fi
  echo "      Esperando backend... ($((i * 5))s)"
  sleep 5
done

if [ "$READY" -eq 0 ]; then
  echo ""
  echo "[FATAL] Backend no responde después de 2 minutos."
  echo "        Ejecuta primero: docker compose up -d backend"
  exit 1
fi

# ── 2. Preparar dataset geo-ready ─────────────────────────────────────────
echo ""
echo "[2/4] Preparando dataset geo-ready (tenant demo-cortecero)..."
docker compose run --rm backend python3 scripts/prepare_google_smoke_dataset.py

# ── 3. Listar rutas disponibles ───────────────────────────────────────────
echo ""
echo "[3/4] Listando rutas en tenant demo..."
SMOKE_LIST_ROUTES=1 \
GOOGLE_APPLICATION_CREDENTIALS="${CREDS}" \
GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID="${PROJECT_ID}" \
  python3 backend/scripts/smoke_google_optimization.py

# ── 4. Crear ruta + optimizar ─────────────────────────────────────────────
echo ""
echo "[4/4] Creando ruta nueva y ejecutando optimize → Google API..."
SMOKE_CREATE_ROUTE=1 \
GOOGLE_APPLICATION_CREDENTIALS="${CREDS}" \
GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID="${PROJECT_ID}" \
  python3 backend/scripts/smoke_google_optimization.py

echo ""
echo "════════════════════════════════════════════════"
echo "  Smoke completado. Verifica el output arriba."
echo "════════════════════════════════════════════════"
echo ""
