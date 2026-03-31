# R6-GATE-001 — Revisión de Cierre de R6

Estado: abierto  
Fecha: 2026-03-31  
Baseline revisado: `main@ce0a697`

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
- falta la vista timeline de snapshots (`R6-FE-003`)
- falta cerrar QA específico de coherencia evaluación vs snapshot (`R6-QA-002`) como bloque explícito
- falta un gate CI orientado a superficie R6/export (`R6-CI-001`)
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
| `R6-DB-003` | Pendiente | no hay migración específica de hardening timezone en R6 |
| `R6-FE-003` | Pendiente | no existe vista timeline de snapshots por pedido |
| `R6-QA-002` | Parcial/Pendiente | hay cobertura de idempotencia, pero no bloque QA cerrado como ticket |
| `R6-CI-001` | Pendiente | `openapi-check` sigue gateando superficie R5, no R6/export |

## 4) Checklist de fase (gate)

| Criterio de cierre R6 | Estado |
|---|---|
| Contrato R6 estable y validado | Parcial |
| Explicabilidad operativa en lectura | Cumplido |
| Persistencia histórica de snapshots | Cumplido |
| Export operativo estable para analítica/IA | Cumplido |
| QA temporal y DST contractual | Cumplido |
| QA de coherencia evaluación/snapshot | Parcial |
| CI bloqueando rotura de superficie R6/export | Pendiente |

## 5) Huecos restantes (lista exacta)

### P0 (bloquean cierre de R6)
1. Implementar `R6-CI-001`: gate CI de contrato R6 y smoke del export.
2. Cerrar `R6-FE-003`: timeline de snapshots por pedido (solo lectura, sin lógica paralela).

### P1 (debe quedar cerrado para considerar R6 robusto)
1. Cerrar `R6-QA-002` como bloque explícito:
- coherencia entre evaluación actual y snapshot persistido
- idempotencia de recalculado por lote verificada como criterio de ticket
2. Ejecutar `R6-DB-003` o formalizar su aplazamiento con riesgo aceptado:
- hardening de timezone en escritura
- evitar normalizar `utc_fallback` como estado operativo permanente

## 6) Riesgos residuales

1. Riesgo de “R6 incompleto pero percibido como cerrado” si se omite export+CI.
2. Riesgo de deriva de contrato si CI no bloquea superficie R6 explícitamente.
3. Riesgo analítico si timezone inválida termina absorbida por fallback sin hardening.

## 7) Criterio de salida de este gate

`R6-GATE-001` queda cerrado cuando:
1. `R6-FE-003` esté merged y verificado.
2. `R6-QA-002` esté cerrado con evidencia.
3. `R6-CI-001` esté activo y en verde.
4. `R6-DB-003` esté implementado o diferido formalmente con decisión explícita de riesgo.

Hasta entonces, **R6 permanece abierto** y **R7 no debería iniciarse**.
