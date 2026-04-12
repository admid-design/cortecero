#!/usr/bin/env bash
# frontend-check.sh — Validación rápida del frontend: tests + build
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/frontend"

echo "================================================================"
echo "  CorteCero — Frontend check"
echo "================================================================"

EXIT=0

echo ""
echo "--- Frontend tests ---"
npm test -- --run || { echo "[FAIL] Frontend tests"; EXIT=1; }

echo ""
echo "--- Frontend build ---"
npm run build || { echo "[FAIL] Frontend build"; EXIT=1; }

cd "$ROOT"

echo ""
if [ $EXIT -eq 0 ]; then
  echo "================================================================"
  echo "  Frontend check: PASSED"
  echo "================================================================"
else
  echo "================================================================"
  echo "  Frontend check: FAILED"
  echo "================================================================"
  exit 1
fi
