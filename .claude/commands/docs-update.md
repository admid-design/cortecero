# /docs-update

Actualiza la documentación tras un bloque cerrado.

## Instrucciones

El usuario indicará qué bloque se cerró. Actualiza los docs afectados.

### Qué actualizar siempre tras un bloque

**1. `docs/as-is.md`**

Si el bloque cambió el estado de una capacidad:
- Mueve de `NO EXISTE` a `PARCIAL` o `VERIFICADO`
- O añade la capacidad nueva a la tabla
- Actualiza la fecha de última actualización

**2. `CHANGELOG.md`** (si existe)

Añade entrada con: versión/fase, fecha, descripción del cambio.

### Qué actualizar solo si aplica

**`README.md`** — solo si cambió la arquitectura, el quick start o las capacidades principales.

**`openapi/openapi-v1.yaml`** — lo hace el bloque de implementación, no este comando.

### Qué NO tocar

- `AGENTS.md` — solo el usuario lo modifica
- `CLAUDE.md` — solo si hay nuevo contexto estructural del repo
- Backlogs — solo el usuario los gestiona

## Output esperado

```
Bloque cerrado: <nombre>
docs/as-is.md actualizado: sí/no — <qué cambió>
CHANGELOG.md actualizado: sí/no
README.md actualizado: sí/no — <qué cambió si aplica>
Otros: <lista o "ninguno">
```
