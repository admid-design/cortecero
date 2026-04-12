#!/usr/bin/env bash
# build.sh — Build completo: Docker images + frontend production build
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "================================================================"
echo "  CorteCero — Build"
echo "================================================================"

echo ""
echo "--- Docker build ---"
docker compose build

echo ""
echo "--- Frontend production build ---"
cd frontend
npm run build
cd "$ROOT"

echo ""
echo "================================================================"
echo "  Build completado"
echo "================================================================"
