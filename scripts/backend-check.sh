#!/usr/bin/env bash
# backend-check.sh — Validación rápida del backend: tests + OpenAPI
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "================================================================"
echo "  CorteCero — Backend check"
echo "================================================================"

EXIT=0

# Tests backend (excluyendo bloque_e que requiere Google)
echo ""
echo "--- pytest (sin test_routing_bloque_e.py) ---"
docker compose run --rm backend pytest -q \
  --ignore=tests/test_routing_bloque_e.py \
  || { echo "[FAIL] Backend tests"; EXIT=1; }

# OpenAPI validation
echo ""
echo "--- OpenAPI spec validator ---"
if command -v openapi-spec-validator &>/dev/null; then
  openapi-spec-validator openapi/openapi-v1.yaml && echo "OpenAPI: OK" || { echo "[FAIL] OpenAPI inválido"; EXIT=1; }
else
  # Intentar con venv
  if [ -f .venv/bin/openapi-spec-validator ]; then
    .venv/bin/openapi-spec-validator openapi/openapi-v1.yaml && echo "OpenAPI: OK" || { echo "[FAIL] OpenAPI inválido"; EXIT=1; }
  else
    echo "openapi-spec-validator no disponible — instala con: pip install openapi-spec-validator"
  fi
fi

echo ""
if [ $EXIT -eq 0 ]; then
  echo "================================================================"
  echo "  Backend check: PASSED"
  echo "================================================================"
else
  echo "================================================================"
  echo "  Backend check: FAILED"
  echo "================================================================"
  exit 1
fi
