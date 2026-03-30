# CorteCero R5 Backlog (Cliente Operativo)

Baseline: `main@v0.3.0`  
Objetivo R5: incorporar reglas operativas por cliente (restricciones, horarios, notas y consolidación) sin romper semántica núcleo (`late / lock / exception`) ni mezclar scope de optimización avanzada.

## Reglas de ejecución
- Mantener invariantes de R1-R4: multi-tenant, RBAC, idempotencia, auditoría append-only.
- Toda lectura/escritura debe resolver por `tenant_id`.
- No degradar contrato de errores (`detail.code`, `detail.message`).
- No introducir optimización de rutas, tracking GPS, pricing ni facturación.
- R5 debe añadir contexto operativo de cliente; no reemplazar reglas de `cutoff`, `lock` o `exception`.
- Cualquier evaluación operativa debe ser trazable (razón explícita), y sin side effects implícitos.

## Tickets Backend

### R5-BE-001 — Perfil Operativo de Cliente (Admin)
- Tipo: Backend
- Prioridad: Alta
- Scope:
  - `GET /admin/customers/{customer_id}/operational-profile`
  - `PUT /admin/customers/{customer_id}/operational-profile`
  - Perfil mínimo:
    - `accept_orders` (bool)
    - `window_start` / `window_end` (TIME, opcional)
    - `min_lead_hours` (int >= 0)
    - `consolidate_by_default` (bool)
    - `ops_note` (texto corto)
- Aceptación:
  - Tenant-safe estricto por `(customer_id, tenant_id)`.
  - RBAC: escritura `admin`; lectura `admin/logistics/office`.
  - Auditoría por cambio de perfil (`customer.operational_profile_updated`).

### R5-BE-002 — Fechas de Excepción Operativa de Cliente
- Tipo: Backend
- Prioridad: Alta
- Scope:
  - `GET /admin/customers/{customer_id}/operational-exceptions`
  - `POST /admin/customers/{customer_id}/operational-exceptions`
  - `DELETE /admin/customers/{customer_id}/operational-exceptions/{exception_id}`
  - Excepción mínima:
    - `date`
    - `type` (`blocked` | `restricted`)
    - `note`
- Aceptación:
  - No duplicar excepción misma `date+type` por cliente.
  - Sin borrado en cascada fuera de tenant.
  - Auditoría de alta/baja.

### R5-BE-003 — Evaluación Operativa de Pedido (Lectura Derivada)
- Tipo: Backend
- Prioridad: Alta
- Scope:
  - Extender `GET /orders` y `GET /orders/{order_id}` con campos derivados:
    - `operational_state` (`eligible` | `restricted`)
    - `operational_reason` (nullable, código estable)
  - Razones iniciales:
    - `CUSTOMER_NOT_ACCEPTING_ORDERS`
    - `OUTSIDE_CUSTOMER_WINDOW`
    - `INSUFFICIENT_LEAD_TIME`
    - `CUSTOMER_DATE_BLOCKED`
- Aceptación:
  - Sin side effects (solo lectura derivada).
  - No alterar `status` ni semántica `late/lock/exception`.
  - Cálculo determinista y tenant-safe.

### R5-BE-004 — Cola Operativa de Restricciones
- Tipo: Backend
- Prioridad: Media
- Scope:
  - `GET /orders/operational-queue`
  - Filtros: `service_date` (required), `zone_id` (optional), `reason` (optional)
  - Lista pedidos en `operational_state=restricted`.
- Aceptación:
  - Orden determinista documentado.
  - Payload mínimo útil para operación.
  - Sin duplicar lógica de pending queue R3; enfoque solo en restricciones de cliente.

### R5-BE-005 — Consolidación Operativa por Cliente (Lectura)
- Tipo: Backend
- Prioridad: Media
- Scope:
  - `GET /plans/{plan_id}/customer-consolidation`
  - Agrupación por cliente de pedidos incluidos en plan:
    - total pedidos por cliente
    - refs incluidas
    - peso total cliente (si existe)
- Aceptación:
  - Sin mutación de plan.
  - Tenant-safe.
  - Respuesta estable para UI operativa.

### R5-BE-006 — Contrato de Errores R5
- Tipo: Backend
- Prioridad: Media
- Scope:
  - Códigos mínimos:
    - `INVALID_OPERATIONAL_PROFILE`
    - `OPERATIONAL_EXCEPTION_CONFLICT`
    - `INVALID_OPERATIONAL_FILTER`
    - `ENTITY_NOT_FOUND`
    - `RBAC_FORBIDDEN`
- Aceptación:
  - Mantener formato estándar `detail.code/detail.message`.
  - No romper códigos existentes de R1-R4.

## Tickets DB

### R5-DB-001 — Perfil Operativo por Cliente
- Tipo: DB
- Prioridad: Alta
- Scope:
  - Tabla `customer_operational_profiles`:
    - `id`, `tenant_id`, `customer_id`
    - `accept_orders BOOLEAN`
    - `window_start TIME NULL`
    - `window_end TIME NULL`
    - `min_lead_hours INTEGER`
    - `consolidate_by_default BOOLEAN`
    - `ops_note TEXT NULL`
    - `created_at`, `updated_at`
  - Unicidad por `(tenant_id, customer_id)`.
- Aceptación:
  - Migración idempotente y backward-compatible.
  - `min_lead_hours >= 0`.

### R5-DB-002 — Excepciones Operativas por Fecha
- Tipo: DB
- Prioridad: Alta
- Scope:
  - Tabla `customer_operational_exceptions`:
    - `id`, `tenant_id`, `customer_id`
    - `date DATE`
    - `type` (`blocked`, `restricted`)
    - `note TEXT`
    - `created_at`
  - Índice/unique por `(tenant_id, customer_id, date, type)`.
- Aceptación:
  - Tenant-safe por FK compuestas.
  - Sin impacto sobre datos R4 existentes.

### R5-DB-003 — Índices de Evaluación Operativa
- Tipo: DB
- Prioridad: Media
- Scope:
  - Índices para evaluación eficiente por:
    - `orders(tenant_id, service_date, customer_id, zone_id)`
    - `customer_operational_profiles(tenant_id, customer_id)`
    - `customer_operational_exceptions(tenant_id, customer_id, date)`
- Aceptación:
  - Plan de consultas operativo sin secuenciales dominantes.

## Tickets Frontend

### R5-FE-001 — Admin Cliente Operativo (Perfil)
- Tipo: Frontend
- Prioridad: Alta
- Scope:
  - Nueva sección/tab en Admin Customers para editar perfil operativo.
  - Campos: `accept_orders`, ventana horaria, `min_lead_hours`, `consolidate_by_default`, `ops_note`.
- Aceptación:
  - UI simple y operativa.
  - Errores backend visibles sin reinterpretación.

### R5-FE-002 — Admin Excepciones de Cliente (Fechas)
- Tipo: Frontend
- Prioridad: Alta
- Scope:
  - Listado/alta/baja de excepciones por fecha para cliente.
- Aceptación:
  - Flujo claro por cliente seleccionado.
  - Refresh y estado vacío/error explícitos.

### R5-FE-003 — Señal Operativa en Pedidos
- Tipo: Frontend
- Prioridad: Alta
- Scope:
  - Mostrar `operational_state` y `operational_reason` en tabla de pedidos.
  - Filtro por estado/reason.
- Aceptación:
  - Sin lógica paralela en frontend.
  - Badge legible y consistente con backend.

### R5-FE-004 — Vista Operational Queue
- Tipo: Frontend
- Prioridad: Media
- Scope:
  - Vista dedicada para `GET /orders/operational-queue`.
  - Filtros por fecha/zona/reason.
- Aceptación:
  - Orden respetado tal cual backend.
  - Empty/error state claros.

### R5-FE-005 — Consolidación por Cliente en Plan
- Tipo: Frontend
- Prioridad: Media
- Scope:
  - Exponer resumen por cliente en detalle de plan.
  - Mostrar pedidos agrupados + peso total cliente (si disponible).
- Aceptación:
  - Sin edición en este bloque.
  - Lectura fiel al endpoint backend.

## Tickets Tests

### R5-QA-001 — Tests Perfil Operativo
- Tipo: QA/Backend tests
- Prioridad: Alta
- Scope:
  - CRUD perfil operativo por cliente.
  - validaciones de `min_lead_hours` y ventanas.
- Aceptación:
  - tenant isolation + RBAC cubiertos.

### R5-QA-002 — Tests Excepciones por Fecha
- Tipo: QA/Backend tests
- Prioridad: Alta
- Scope:
  - alta/baja/listado + conflicto de duplicados.
- Aceptación:
  - códigos de error consistentes.

### R5-QA-003 — Tests Evaluación Operativa de Pedido
- Tipo: QA/Backend tests
- Prioridad: Alta
- Scope:
  - cada `operational_reason` principal.
  - casos borde de horario y lead time.
- Aceptación:
  - no muta `status` de pedido.
  - no altera `late/lock/exception`.

### R5-QA-004 — Tests Operational Queue
- Tipo: QA/Backend tests
- Prioridad: Media
- Scope:
  - filtros, orden determinista y tenant isolation.
- Aceptación:
  - payload estable para FE.

### R5-QA-005 — Regression Pack R1-R4
- Tipo: QA
- Prioridad: Alta
- Scope:
  - mantener en verde las suites críticas previas.
- Aceptación:
  - sin regresiones en flujos `late/lock/exception`, peso, vehículo y alertas.

## Tickets CI

### R5-CI-001 — Gating Suite R5
- Tipo: CI
- Prioridad: Alta
- Scope:
  - incluir tests R5 en `backend-tests`.
- Aceptación:
  - PR falla ante regresión R5.

### R5-CI-002 — OpenAPI Drift Check R5
- Tipo: CI
- Prioridad: Media
- Scope:
  - validar endpoint/schemas R5 presentes en OpenAPI.
- Aceptación:
  - PR falla ante drift contrato/implementación.

### R5-CI-003 — Smoke Frontend Operativo R5
- Tipo: CI
- Prioridad: Media
- Scope:
  - smoke de build frontend con vistas R5.
- Aceptación:
  - build en verde sin degradar pantallas operativas existentes.

## Orden recomendado (secuencial)
1. R5-DB-001, R5-DB-002, R5-DB-003
2. R5-BE-001, R5-BE-002, R5-BE-003, R5-BE-004, R5-BE-005, R5-BE-006
3. R5-QA-001, R5-QA-002, R5-QA-003, R5-QA-004, R5-QA-005
4. R5-FE-001, R5-FE-002, R5-FE-003, R5-FE-004, R5-FE-005
5. R5-CI-001, R5-CI-002, R5-CI-003

## No-hacer en R5
- No cambiar semántica `late / lock / exception`.
- No introducir optimización de rutas, asignación inteligente de flota ni tracking GPS.
- No mezclar pricing/finanzas/facturación.
- No automatizar bloqueo/rechazo de pedidos por restricciones R5 sin aprobación explícita de producto.
- No abrir R6 hasta cerrar review formal de R5 backlog y primeras entregas.
