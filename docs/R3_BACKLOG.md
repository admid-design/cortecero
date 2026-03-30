# CorteCero R3 Backlog (Planificación Asistida)

Baseline: `main@v0.2.0`
Objetivo R3: enriquecer operación diaria sin romper semántica núcleo (`late / lock / exception`) ni abrir scope de R4/R5.

## Reglas de ejecución
- Mantener invariantes de R1/R2: multi-tenant, RBAC, idempotencia, auditoría append-only.
- No introducir peso/carga/vehículos/routing avanzado en R3.
- Toda lectura/escritura debe resolver por `tenant_id`.
- No degradar contrato de errores (`detail.code`, `detail.message`).
- Cualquier automatismo de lock debe ser trazable y reversible por operador autorizado.

## Tickets Backend

### R3-BE-001 — Clasificación Operativa `nuevo` vs `añadido`
- Tipo: Backend
- Prioridad: Alta
- Scope:
  - Extender ingesta para clasificar pedidos como:
    - `new_order`
    - `same_customer_addon`
  - Reglas mínimas (MVP R3):
    - mismo `customer_id` + `service_date` con pedido previo existente => `same_customer_addon`
    - resto => `new_order`
  - Exponer clasificación en `GET /orders` y `GET /orders/{order_id}`.
- Aceptación:
  - No cambia cálculo de `is_late` ni flujo de excepción.
  - Clasificación se recalcula solo en creación, no muta por actualizaciones normales.
  - Auditoría al crear pedido incluye clasificación asignada.

### R3-BE-002 — Pending Queue Operativa
- Tipo: Backend
- Prioridad: Alta
- Scope:
  - Nuevo endpoint `GET /orders/pending-queue`.
  - Filtros: `service_date` (required), `zone_id` (optional), `reason` (optional).
  - Razones mínimas:
    - `LATE_PENDING_EXCEPTION`
    - `LOCKED_PLAN_EXCEPTION_REQUIRED`
    - `EXCEPTION_REJECTED`
- Aceptación:
  - Lista solo pedidos no elegibles para inclusión normal en plan.
  - Resultado incluye `order_id`, `external_ref`, `status`, `reason`, `service_date`, `zone_id`.
  - Respeta aislamiento tenant.

### R3-BE-003 — Métricas por Origen de Pedido
- Tipo: Backend
- Prioridad: Media
- Scope:
  - Nuevo endpoint `GET /dashboard/source-metrics`.
  - Filtros: `date_from`, `date_to`, `zone_id` (optional).
  - KPIs por `source_channel`:
    - `total_orders`
    - `late_orders`
    - `late_rate`
    - `approved_exceptions`
    - `rejected_exceptions`
- Aceptación:
  - Cálculo consistente con estados reales de `orders`/`exceptions`.
  - Respuesta estable para consumo frontend.

### R3-BE-004 — Auto-lock Operativo de Planes
- Tipo: Backend
- Prioridad: Alta
- Scope:
  - Job/servicio aplicable manualmente: `POST /plans/auto-lock/run`.
  - Lock automático de planes `open` por regla tenant (`auto_lock_enabled=true` + hora configurada).
  - Excluir planes ya `locked/dispatched`.
- Aceptación:
  - Operación idempotente (re-ejecutar no rompe estado).
  - Auditoría explícita de lock automático (`action=auto_lock_plan`).
  - No modifica reglas de inclusión post-lock.

### R3-BE-005 — Contrato de Errores R3
- Tipo: Backend
- Prioridad: Media
- Scope:
  - Extender contrato con códigos R3:
    - `PENDING_QUEUE_FILTER_INVALID`
    - `AUTO_LOCK_DISABLED`
    - `AUTO_LOCK_WINDOW_NOT_REACHED`
- Aceptación:
  - Sin romper códigos existentes de R1/R2.
  - OpenAPI actualizado.

## Tickets DB

### R3-DB-001 — Migración 003 Order Classification
- Tipo: DB
- Prioridad: Alta
- Scope:
  - Enum `order_intake_type`: `new_order`, `same_customer_addon`.
  - Columna `orders.intake_type` NOT NULL con default `new_order`.
  - Índice `orders(tenant_id, customer_id, service_date, created_at)` para clasificación eficiente.
- Aceptación:
  - Migración idempotente.
  - Compatible con datos existentes en producción/piloto.

### R3-DB-002 — Migración 004 Tenant Auto-lock Window
- Tipo: DB
- Prioridad: Media
- Scope:
  - `tenants.auto_lock_time TIME NULL`.
  - `tenants.auto_lock_grace_minutes INTEGER NOT NULL DEFAULT 0`.
- Aceptación:
  - Constraints para evitar valores negativos en grace.
  - Sin impacto en tenants que no usan auto-lock.

### R3-DB-003 — Índices para Pending Queue y Métricas
- Tipo: DB
- Prioridad: Media
- Scope:
  - Índices compuestos para consultas de cola pendiente y métricas por rango fecha.
- Aceptación:
  - Plan de consultas sin secuenciales costosos en tablas grandes (validación básica con `EXPLAIN`).

## Tickets Frontend

### R3-FE-001 — Vista “Pending Queue”
- Tipo: Frontend
- Prioridad: Alta
- Scope:
  - Nueva vista operativa con tabla filtrable por fecha/zona/razón.
  - Acciones rápidas: abrir pedido, crear excepción.
- Aceptación:
  - Errores backend mostrados literal por `detail.code: detail.message`.
  - No bloquea navegación operativa existente.

### R3-FE-002 — Señalización `nuevo` vs `añadido`
- Tipo: Frontend
- Prioridad: Media
- Scope:
  - Badges en tablas de pedidos y detalle de plan.
- Aceptación:
  - Claridad visual sin alterar flujos actuales.

### R3-FE-003 — Panel de Métricas por Origen
- Tipo: Frontend
- Prioridad: Media
- Scope:
  - Tabla/mini panel por `source_channel` con filtros de rango.
- Aceptación:
  - Totales consistentes con backend.
  - Sin componentes ornamentales; enfoque operativo.

### R3-FE-004 — Configuración Auto-lock (Admin)
- Tipo: Frontend
- Prioridad: Media
- Scope:
  - Extender Tenant Settings para `auto_lock_time` y `auto_lock_grace_minutes`.
- Aceptación:
  - Guardado exitoso reflejado inmediatamente.
  - Errores de validación backend visibles sin reinterpretación.

## Tickets Tests

### R3-QA-001 — Tests Clasificación `nuevo/añadido`
- Tipo: QA/Backend tests
- Prioridad: Alta
- Scope:
  - casos creación pedido inicial y añadido mismo cliente/fecha.
- Aceptación:
  - clasificación esperada persistida.
  - sin impacto en `is_late` ni estados base.

### R3-QA-002 — Tests Pending Queue
- Tipo: QA/Backend tests
- Prioridad: Alta
- Scope:
  - razones correctas por cada estado/escenario.
  - aislamiento por tenant.
- Aceptación:
  - filtros y payload estables.

### R3-QA-003 — Tests Auto-lock
- Tipo: QA/Backend tests
- Prioridad: Alta
- Scope:
  - auto-lock sobre planes open elegibles.
  - idempotencia del endpoint run.
  - no lock si feature desactivada.
- Aceptación:
  - assert de auditoría `auto_lock_plan`.

### R3-QA-004 — Tests Métricas Origen
- Tipo: QA/Backend tests
- Prioridad: Media
- Scope:
  - validación de agregados por canal y rango fecha.
- Aceptación:
  - resultados consistentes con fixtures.

### R3-QA-005 — Regression Pack R1/R2
- Tipo: QA/Backend+Frontend
- Prioridad: Alta
- Scope:
  - conservar en verde suites críticas ya existentes.
- Aceptación:
  - sin regresiones en `late / lock / exception` y admin.

## Tickets CI

### R3-CI-001 — Gating de Tests R3
- Tipo: CI
- Prioridad: Alta
- Scope:
  - extender workflow backend-tests para incluir suite R3.
- Aceptación:
  - PR falla ante regresión R3.

### R3-CI-002 — Contract Check OpenAPI R3
- Tipo: CI
- Prioridad: Media
- Scope:
  - validar que endpoints/schemas R3 estén reflejados en `openapi-v1.yaml`.
- Aceptación:
  - PR falla ante drift API/implementación.

### R3-CI-003 — Smoke Auto-lock Job
- Tipo: CI
- Prioridad: Media
- Scope:
  - smoke de endpoint `POST /plans/auto-lock/run` con fixture controlado.
- Aceptación:
  - evidencia de ejecución idempotente en CI.

## Orden recomendado (secuencial)
1. R3-DB-001, R3-DB-002, R3-DB-003
2. R3-BE-001, R3-BE-002, R3-BE-003, R3-BE-004, R3-BE-005
3. R3-QA-001, R3-QA-002, R3-QA-003, R3-QA-004, R3-QA-005
4. R3-FE-001, R3-FE-002, R3-FE-003, R3-FE-004
5. R3-CI-001, R3-CI-002, R3-CI-003

## No-hacer en R3
- No introducir optimización de rutas ni asignación de vehículo.
- No abrir módulo de peso/carga (R4).
- No añadir tracking GPS o app de chofer.
- No cambiar semántica base de excepciones (`late_order`, `pending/approved/rejected`).
- No romper compatibilidad de API en endpoints existentes de R1/R2.
