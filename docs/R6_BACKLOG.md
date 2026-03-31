# CorteCero R6 Backlog (Operational Intelligence Readiness)

Baseline: `main@v0.4.0`
Objetivo R6: aumentar valor operativo inmediato y dejar trazabilidad/explicabilidad listas para una futura capa IA, sin introducir todavía predicción automática ni decisiones opacas.

## Criterio dual de aceptación (obligatorio en cada ticket)
- Valor operativo: mejora tangible para operación diaria (menos ambigüedad, mejor priorización, mejor resolución).
- Preparación IA: datos/razones/eventos más estructurados, estables y trazables para analítica/ML futura.

## Invariantes de ejecución
- Mantener semántica núcleo de R1-R5 (`late / lock / exception / operational_state`).
- Multi-tenant estricto en toda lectura/escritura.
- RBAC y contrato de errores (`detail.code`, `detail.message`) sin degradación.
- Cualquier regla derivada debe ser explicable (razón y evidencia mínima).
- Nada de side effects implícitos en endpoints de lectura.

## No-hacer en R6
- No optimización de rutas avanzada.
- No pricing/facturación.
- No recomendaciones de IA en producción.
- No auto-aprobación de excepciones.
- No cambios de semántica de estados existentes.

## Tickets DB

### R6-DB-001 — Catálogo versionado de razones operativas
- Tipo: DB
- Prioridad: Alta
- Scope:
  - Tabla `operational_reason_catalog`:
    - `id`, `code` (único), `category`, `severity`, `active`
    - `description`, `created_at`, `updated_at`
  - Semilla inicial con razones actuales de R5.
- Aceptación:
  - Códigos estables y consultables.
  - Migración backward-compatible.

### R6-DB-002 — Snapshot de evaluación operativa por pedido
- Tipo: DB
- Prioridad: Alta
- Scope:
  - Tabla append-only `order_operational_snapshots`:
    - `id`, `tenant_id`, `order_id`, `service_date`
    - `operational_state`, `operational_reason`
    - `evaluation_ts`, `timezone_used`, `rule_version`
    - `evidence_json`
- Aceptación:
  - Sin reemplazar estado actual; solo trazabilidad histórica.
  - Índices por `(tenant_id, service_date)` y `(tenant_id, order_id, evaluation_ts desc)`.

### R6-DB-003 — Hardening temporal y consistencia timezone
- Tipo: DB
- Prioridad: Media
- Scope:
  - Constraints y normalización de timezone en entidades configurables.
  - Guardrails para evitar fallback silencioso a `UTC` por dato inválido.
- Aceptación:
  - Invalidaciones explícitas en escritura.
  - Sin cambios destructivos sobre datos existentes.

## Tickets Backend

### R6-BE-001 — Contrato de explicación operativa por pedido
- Tipo: Backend
- Prioridad: Alta
- Scope:
  - Extender `GET /orders` y `GET /orders/{order_id}` con `operational_explanation` mínimo:
    - `reason_code`
    - `reason_category`
    - `severity`
    - `timezone_used`
    - `rule_version`
- Aceptación:
  - Lectura derivada sin side effects.
  - Totalmente tenant-safe.

### R6-BE-002 — Persistencia de snapshot de evaluación (escritura controlada)
- Tipo: Backend
- Prioridad: Alta
- Scope:
  - Hook explícito al recalcular evaluación operativa para persistir snapshot en `order_operational_snapshots`.
  - Endpoint interno/administrativo para recalcular lote por `service_date`.
- Aceptación:
  - Idempotencia por `(order_id, evaluation_ts_bucket, rule_version)`.
  - Auditoría de ejecución (`operational_snapshot_generated`).

### R6-BE-003 — Queue de resolución operativa priorizada
- Tipo: Backend
- Prioridad: Media
- Scope:
  - `GET /orders/operational-resolution-queue`
  - Orden determinista por `severity`, `operational_reason`, `created_at`, `id`.
  - Filtros: `service_date` (required), `zone_id`, `reason`, `severity`.
- Aceptación:
  - Sin duplicar semántica de colas anteriores; esta cola es de resolución.
  - Contrato de error para filtros inválidos.

### R6-BE-004 — Export operativo para analítica/IA (solo lectura)
- Tipo: Backend
- Prioridad: Media
- Scope:
  - `GET /exports/operational-dataset`
  - Ventana por fechas, paginado y formato estable (JSON/CSV).
  - Campos mínimos: pedido, cliente, zona, reasons, timestamps, decisiones y métricas de peso/plan.
- Aceptación:
  - Anonimización opcional (toggle).
  - Tenant-safe estricto.

## Tickets Frontend

### R6-FE-001 — Vista de explicación operativa en pedido
- Tipo: Frontend
- Prioridad: Alta
- Scope:
  - Mostrar `operational_explanation` en lista y detalle de pedidos.
  - UI operativa simple, sin interpretación adicional.
- Aceptación:
  - Códigos y severidad legibles.
  - Sin lógica paralela de cálculo.

### R6-FE-002 — Operational Resolution Queue
- Tipo: Frontend
- Prioridad: Media
- Scope:
  - Vista dedicada para `operational-resolution-queue`.
  - Filtros contract-faithful + orden backend intacto.
- Aceptación:
  - Empty/error states claros.
  - No recalcular prioridades en frontend.

### R6-FE-003 — Timeline de snapshots por pedido
- Tipo: Frontend
- Prioridad: Media
- Scope:
  - Línea temporal de snapshots de evaluación operativa.
  - Visualización de cambios de reason/state por orden cronológico.
- Aceptación:
  - Solo lectura.
  - Enfoque diagnóstico/operativo.

## Tickets QA / CI

### R6-QA-001 — Pruebas de bordes temporales y DST
- Tipo: QA
- Prioridad: Alta
- Scope:
  - Casos `same_day`, `cross_midnight`, DST forward/backward, timezone inválida.
- Aceptación:
  - Resultados deterministas documentados.

### R6-QA-002 — Pruebas de explainability y snapshot
- Tipo: QA
- Prioridad: Alta
- Scope:
  - Coherencia entre evaluación actual y snapshot persistido.
  - Idempotencia de recalculado por lote.
- Aceptación:
  - Sin mutar semántica de estados previos.

### R6-CI-001 — Gate de esquema de export y contrato explicación
- Tipo: CI
- Prioridad: Media
- Scope:
  - Validaciones automáticas de OpenAPI para endpoints R6.
  - Smoke de export (shape estable y paginado).
- Aceptación:
  - Bloqueo de PR si se rompe contrato.

## Orden recomendado de ejecución
1. `R6-DB-001`
2. `R6-BE-001`
3. `R6-FE-001`
4. `R6-DB-002`
5. `R6-BE-002`
6. `R6-QA-001`
7. `R6-BE-003`
8. `R6-FE-002`
9. `R6-BE-004`
10. `R6-CI-001`

## Definition of Done R6
- Operación puede entender y priorizar restricciones con explicación explícita y consistente.
- Existe traza histórica de evaluación operativa por pedido.
- Hay export estable tenant-safe para análisis y futura capa IA.
- QA/CI cubre bordes temporales y estabilidad de contrato.
- Ninguna semántica crítica de R1-R5 queda degradada.
