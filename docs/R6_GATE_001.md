# R6-GATE-001 — Revisión de Cierre de R6

Estado: abierto  
Fecha: 2026-03-31  
Baseline revisado: `main@060a9f0`

## 1) Objetivo del gate
Validar si R6 está listo para cierre formal contra los criterios de fase:
- contrato
- explicabilidad
- snapshots
- export estable
- QA temporal / DST
- CI de contrato/export

## 2) Resumen ejecutivo
Veredicto actual: **NO-GO para cierre de R6**.

R6 tiene una base sólida y varios bloques cerrados, pero aún quedan huecos de fase:
- sigue abierto el hardening de timezone en escritura (`R6-DB-003`)

## 3) Estado por ticket R6

| Ticket | Estado | Evidencia principal |
|---|---|---|
| `R6-DB-001` | Cerrado | `db/migrations/010_operational_reason_catalog.sql`, commit `2ac17dd` |
| `R6-BE-001` | Cerrado | `operational_explanation` en `/orders` y `/orders/{id}`, commit `39be037` |
| `R6-FE-001` | Cerrado | explicación operativa en vista de pedidos, commit `867fde9` |
| `R6-DB-002` | Cerrado | `db/migrations/011_order_operational_snapshots.sql`, commit `339c1fc` |
| `R6-BE-002` | Cerrado | `/orders/operational-snapshots/run`, commit `fe5881a` |
| `R6-QA-001` | Cerrado | `docs/R6_QA_001_TEMPORAL_MATRIX.md`, `backend/tests/test_operational_temporal_dst.py`, commit `e484906` |
| `R6-BE-003` | Cerrado | `/orders/operational-resolution-queue`, commit `b7621c9` |
| `R6-FE-002` | Cerrado | vista resolution queue + deuda técnica FE cerrada, commits `1738b20`, `47eebc1`, `f8b52b6`, `aa4cd4a` |
| `R6-BE-004` | Cerrado | `/exports/operational-dataset`, commit `ce0a697` |
| `R6-CI-001` | Cerrado | `openapi-check` gateando superficie R6/export, commit `7d507c6` |
| `R6-FE-003` | Cerrado | timeline de snapshots en UI operativa, commit `060a9f0` |
| `R6-QA-002` | Cerrado | coherencia evaluación↔snapshot e idempotencia por lote, `backend/tests/test_operational_snapshot_consistency.py` |
| `R6-DB-003` | Pendiente | no hay migración específica de hardening timezone en R6 |

## 4) Checklist de fase (gate)

| Criterio de cierre R6 | Estado |
|---|---|
| Contrato R6 estable y validado | Cumplido |
| Explicabilidad operativa en lectura | Cumplido |
| Persistencia histórica de snapshots | Cumplido |
| Export operativo estable para analítica/IA | Cumplido |
| QA temporal y DST contractual | Cumplido |
| QA de coherencia evaluación/snapshot | Cumplido |
| CI bloqueando rotura de superficie R6/export | Cumplido |

## 5) Huecos restantes (lista exacta)

### P0 (bloquean cierre de R6)
Sin pendientes P0 abiertos.

### P1 (debe quedar cerrado para considerar R6 robusto)
1. Ejecutar `R6-DB-003` o formalizar su aplazamiento con riesgo aceptado:
- hardening de timezone en escritura
- evitar normalizar `utc_fallback` como estado operativo permanente

## 6) Riesgos residuales

1. Riesgo analítico si timezone inválida termina absorbida por fallback sin hardening.
2. Riesgo de cierre prematuro de R6 si no se implementa o difiere formalmente `R6-DB-003`.

## 7) Criterio de salida de este gate

`R6-GATE-001` queda cerrado cuando:
1. `R6-DB-003` esté implementado o diferido formalmente con decisión explícita de riesgo.

Hasta entonces, **R6 permanece abierto** y **R7 no debería iniciarse**.
