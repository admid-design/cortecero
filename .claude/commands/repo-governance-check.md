# /repo-governance-check

Verifica que la estructura de gobernanza del repo está íntegra.

## Instrucciones

Ejecuta estas verificaciones y reporta el estado:

### 1. Archivos obligatorios

```bash
test -f README.md && echo "README.md: OK" || echo "README.md: FALTA"
test -f AGENTS.md && echo "AGENTS.md: OK" || echo "AGENTS.md: FALTA"
test -f CLAUDE.md && echo "CLAUDE.md: OK" || echo "CLAUDE.md: FALTA"
test -f docs/as-is.md && echo "docs/as-is.md: OK" || echo "docs/as-is.md: FALTA"
test -f openapi/openapi-v1.yaml && echo "openapi: OK" || echo "openapi: FALTA"
test -f docs/contracts/error-contract.md && echo "error-contract: OK" || echo "error-contract: FALTA"
```

### 2. Estructura .claude

```bash
ls .claude/rules/
ls .claude/commands/
```

Esperado: ≥9 reglas, ≥9 comandos.

### 3. Scripts ejecutables

```bash
for f in scripts/test.sh scripts/build.sh scripts/migrate.sh scripts/smoke.sh scripts/backend-check.sh scripts/frontend-check.sh; do
  test -x $f && echo "$f: OK" || echo "$f: NO EJECUTABLE o FALTA"
done
```

### 4. Nomenclatura Kelko

```bash
grep -r "Kelko\|kelko" --include="*.md" --include="*.py" --include="*.ts" --include="*.sql" \
  --exclude-dir=".git" --exclude-dir="node_modules" \
  . | grep -v "ANTIGRAVITY_CONTEXT_MASTER.md" | grep -v "AGENTS.md" | grep -v "CLAUDE.md" | grep -v "docs/as-is.md" | grep -v "docker-compose.yml"
```

Si hay hits fuera de los archivos permitidos, reportarlos.

### 5. Imports en CLAUDE.md apuntan a archivos reales

```bash
grep "^@" CLAUDE.md | while read ref; do
  file="${ref#@}"
  test -f "$file" && echo "$ref: OK" || echo "$ref: ARCHIVO NO EXISTE"
done
```

### 6. CI workflows presentes

```bash
ls .github/workflows/
```

Esperado: `backend-tests.yml`, `frontend-smoke.yml`, `openapi-check.yml`

## Output esperado

```
Archivos obligatorios: OK / PROBLEMA — <lista de faltantes>
Estructura .claude: OK / INCOMPLETA
Scripts ejecutables: OK / PROBLEMA — <lista>
Kelko en repo-safe: LIMPIO / PROBLEMA — <archivos afectados>
Imports CLAUDE.md: OK / PROBLEMA — <refs rotas>
CI workflows: OK / INCOMPLETA
Veredicto general: OK / REQUIERE ATENCIÓN
```
