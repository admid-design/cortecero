#!/usr/bin/env bash
# docs-check.sh — Verifica integridad de la estructura documental y de gobernanza
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "================================================================"
echo "  CorteCero — Docs & governance check"
echo "================================================================"

EXIT=0

check_file() {
  local f="$1"
  if [ -f "$f" ]; then
    echo "  OK  $f"
  else
    echo "  FALTA  $f"
    EXIT=1
  fi
}

check_exec() {
  local f="$1"
  if [ -x "$f" ]; then
    echo "  OK  $f (ejecutable)"
  elif [ -f "$f" ]; then
    echo "  WARN  $f (existe pero no es ejecutable)"
  else
    echo "  FALTA  $f"
    EXIT=1
  fi
}

echo ""
echo "--- Archivos de gobernanza ---"
check_file "README.md"
check_file "AGENTS.md"
check_file "CLAUDE.md"
check_file "docs/as-is.md"
check_file "docs/contracts/error-contract.md"
check_file "docs/domain/cortecero/overview.md"
check_file "openapi/openapi-v1.yaml"

echo ""
echo "--- .claude/rules ---"
for f in backend frontend db openapi docs review demo routing tests; do
  check_file ".claude/rules/$f.md"
done

echo ""
echo "--- .claude/commands ---"
for f in review-block close-block smoke-google map-task docs-update routing-check demo-check readme-refresh repo-governance-check; do
  check_file ".claude/commands/$f.md"
done

echo ""
echo "--- Scripts ---"
for f in test build migrate smoke backend-check frontend-check docs-check; do
  check_exec "scripts/$f.sh"
done

echo ""
echo "--- Imports en CLAUDE.md ---"
grep "^@" CLAUDE.md | while read -r ref; do
  file="${ref#@}"
  if [ -f "$file" ]; then
    echo "  OK  @$file"
  else
    echo "  ROTO  @$file — archivo no existe"
    EXIT=1
  fi
done

echo ""
echo "--- Kelko en archivos repo-safe ---"
KELKO_HITS=$(grep -rl "Kelko\|kelko" \
  --include="*.py" --include="*.ts" --include="*.tsx" --include="*.sql" \
  --exclude-dir=".git" --exclude-dir="node_modules" --exclude-dir=".next" \
  . 2>/dev/null | grep -v "docker-compose.yml" || true)
if [ -z "$KELKO_HITS" ]; then
  echo "  OK  Sin referencias a Kelko en código"
else
  echo "  WARN  Kelko encontrado en:"
  echo "$KELKO_HITS" | sed 's/^/    /'
fi

echo ""
if [ $EXIT -eq 0 ]; then
  echo "================================================================"
  echo "  Governance check: PASSED"
  echo "================================================================"
else
  echo "================================================================"
  echo "  Governance check: FAILED — ver errores arriba"
  echo "================================================================"
  exit 1
fi
