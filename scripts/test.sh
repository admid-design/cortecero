#!/usr/bin/env bash
# test.sh — Ejecuta el suite completo de tests: backend + frontend
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "================================================================"
echo "  CorteCero — Test Suite"
echo "================================================================"

# Backend tests (pytest en Docker)
echo ""
echo "--- Backend tests ---"
docker compose run --rm backend pytest -q "${BACKEND_ARGS:-}" "$@" || {
  echo "[FAIL] Backend tests fallaron"
  exit 1
}

# Frontend tests (vitest local)
echo ""
echo "--- Frontend tests ---"
cd frontend
npm test -- --run "${FRONTEND_ARGS:-}" "$@" || {
  echo "[FAIL] Frontend tests fallaron"
  exit 1
}
cd "$ROOT"

echo ""
echo "================================================================"
echo "  Todos los tests pasaron"
echo "================================================================"
