# Reglas — Documentación

Aplica cuando trabajas en `docs/`, `README.md`, `AGENTS.md` o `CLAUDE.md`.

## Principio

La documentación describe el estado real. No es aspiracional.

Si algo no está verificado, dilo. Si algo está bloqueado, dilo.
Nunca conviertas ausencia de evidencia en afirmación positiva.

## Jerarquía documental

| Archivo | Propósito | Quién lo lee |
|---------|-----------|--------------|
| `README.md` | Entrada al proyecto, quick start, arquitectura | Todo el mundo |
| `docs/as-is.md` | Estado verificado del repo | Agentes, revisores |
| `docs/contracts/` | Contratos estables: errores, API, dominio | Backend + frontend |
| `docs/domain/cortecero/` | Semántica de dominio operativo | Agentes, nuevos devs |
| `CLAUDE.md` | Memory de Claude Code | Claude Code |
| `AGENTS.md` | Contrato operativo de agentes | Agentes |
| `docs/R*_BACKLOG.md` | Backlog por fase | Usuario/revisor |

## Reglas de edición

### docs/as-is.md

- Solo hechos verificados con evidencia (test, CI, smoke)
- Tres categorías explícitas: VERIFICADO / PARCIAL / NO EXISTE
- Actualiza cuando un bloque cambia el estado de una capacidad
- Fecha de última actualización al inicio del archivo

### README.md

- No añadas features que no existen
- La sección "Current capabilities" debe estar alineada con `docs/as-is.md`
- No es el lugar para el backlog ni el to-be
- Edita solo si el cambio estructural lo requiere (nuevo módulo, nueva arquitectura)

### AGENTS.md

- No modifiques el contrato sin instrucción explícita del usuario
- Es la fuente de verdad operativa para todos los agentes
- Si hay contradicción entre AGENTS.md y CLAUDE.md, gana AGENTS.md

### CLAUDE.md

- Complementa AGENTS.md, no lo duplica
- Añade contexto de navegación y stack-specific que AGENTS.md no cubre
- Los imports `@` referencian archivos reales — verifica que existan

## Huecos documentales conocidos

- `docs/contracts/` tiene solo `error-contract.md` — incompleto
- `docs/domain/cortecero/` tiene solo `overview.md` — incompleto
- El backlog de R7 (`docs/R7_BACKLOG.md`) puede estar desactualizado respecto al trabajo reciente
