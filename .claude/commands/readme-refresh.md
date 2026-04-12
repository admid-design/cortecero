# /readme-refresh

Verifica y actualiza el README si ha quedado desactualizado.

## Instrucciones

Compara el README actual contra el estado real del repo.

### 1. Verificar Current capabilities

Contrasta la sección "Current capabilities" de `README.md` con `docs/as-is.md`.

¿Hay capacidades en README que `docs/as-is.md` marca como NO EXISTE o PARCIAL?
¿Hay capacidades verificadas en `docs/as-is.md` que no aparecen en README?

### 2. Verificar Quick start

¿Los comandos del Quick start siguen funcionando?

```bash
# Verificar que docker-compose.yml existe y es válido
docker compose config --quiet && echo "docker-compose: OK"

# Verificar que frontend package.json tiene los scripts esperados
cat frontend/package.json | python3 -c "import json,sys; p=json.load(sys.stdin); print('scripts:', list(p.get('scripts',{}).keys()))"
```

### 3. Verificar estructura del repo en README

¿La sección "Repository structure" refleja la estructura real?

```bash
ls -la . | grep -E "^d|CLAUDE.md|AGENTS.md|README.md"
ls .claude/
ls docs/
```

### 4. Propuesta de actualización

Si hay divergencias, propón los cambios mínimos necesarios.
No hagas un rediseño del README. Solo corrige lo que es factualmente incorrecto.

## Reglas

- No añadas features que no existen
- No elimines información correcta
- No cambies el tono ni la estructura general
- Solo corrige divergencias factuales
