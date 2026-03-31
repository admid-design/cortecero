# CorteCero R7 Backlog (Catalog + Warehouse + Physical Execution)

Baseline: `main@v0.5.0`  
Objetivo R7: abrir operación física (catálogo, ubicaciones, inventario, recepción y carga) con trazabilidad estricta, sin romper el core R1-R6.

## Criterio dual de aceptación (obligatorio en cada ticket)
- Valor operativo: mejora tangible de operación física diaria (menos ciego de stock/carga, menos retrabajo).
- Preparación IA: eventos y datos físicos trazables, consistentes y exportables para analítica/ML futura.

## Invariantes de ejecución
- Mantener semántica núcleo: `late / lock / exception / operational_state`.
- Multi-tenant estricto en toda lectura/escritura.
- RBAC y contrato de errores (`detail.code`, `detail.message`) sin degradación.
- Inventario y movimientos siempre append-only en capa de eventos.
- No side effects implícitos en endpoints de lectura.
- `inventory_movements` es la única fuente de verdad del inventario; `inventory_balances` se trata como estado derivado/materializado.

## No-hacer en R7
- No optimización avanzada de rutas.
- No pricing/facturación.
- No tracking GPS en tiempo real.
- No decisiones automáticas de IA (solo preparación de datos).

## Tickets DB

### R7-DB-001 — Catálogo de producto base
- Tipo: DB
- Scope:
  - `products` (`id`, `tenant_id`, `sku`, `name`, `barcode`, `uom`, `active`, timestamps).
  - unicidad por `tenant_id + sku`.
  - índice para lookup por `barcode`.

### R7-DB-002 — Ubicaciones de almacén
- Tipo: DB
- Scope:
  - `warehouse_locations` (`id`, `tenant_id`, `code`, `name`, `type`, `active`, timestamps).
  - unicidad por `tenant_id + code`.

### R7-DB-003 — Balances y movimientos de inventario
- Tipo: DB
- Scope:
  - `inventory_balances` por `tenant + location + product`.
  - `inventory_movements` append-only (`in`, `out`, `adjustment`, `transfer`).
  - checks para no permitir cantidades negativas en movimientos.
- Decisión contractual:
  - `inventory_balances` no admite escritura funcional directa de negocio.
  - altas/cambios de saldo ocurren exclusivamente por aplicación de `inventory_movements`.
  - cualquier endpoint de ajuste debe persistir primero movimiento y luego reflejar saldo derivado.

### R7-DB-004 — Eventos de recepción y carga
- Tipo: DB
- Scope:
  - `receipts` / `receipt_lines`.
  - `plan_load_events` append-only por `plan_id`.
  - enlace a `vehicle_id` cuando aplique.

## Tickets Backend

### R7-BE-001 — CRUD admin de producto (mínimo)
- Tipo: Backend
- Scope:
  - `GET /admin/products`
  - `POST /admin/products`
  - `PATCH /admin/products/{product_id}`
  - `POST /admin/products/{product_id}/deactivate`
- Aceptación:
  - tenant-safe + RBAC admin.
  - contrato de conflicto por SKU duplicado.

### R7-BE-002 — CRUD admin de ubicaciones
- Tipo: Backend
- Scope:
  - `GET /admin/warehouse-locations`
  - `POST /admin/warehouse-locations`
  - `PATCH /admin/warehouse-locations/{location_id}`
  - `POST /admin/warehouse-locations/{location_id}/deactivate`
- Aceptación:
  - tenant-safe + RBAC admin/logistics.

### R7-BE-003 — API de movimientos de inventario (append-only)
- Tipo: Backend
- Scope:
  - `POST /inventory/movements`
  - `GET /inventory/movements`
  - `GET /inventory/balances`
- Aceptación:
  - no update/delete de movimientos.
  - balances derivados consistentes.

### R7-BE-004 — Recepción operativa
- Tipo: Backend
- Scope:
  - `POST /receipts`
  - `GET /receipts`
  - `GET /receipts/{receipt_id}`
- Aceptación:
  - recepción trazable por actor/ts.
  - sin tocar todavía putaway automatizado.

### R7-BE-005 — Carga de plan por cliente/pedido
- Tipo: Backend
- Scope:
  - `POST /plans/{plan_id}/load-events`
  - `GET /plans/{plan_id}/load-events`
- Aceptación:
  - eventos append-only.
  - relación clara con `plan_orders`.

## Tickets Frontend

### R7-FE-001 — Admin productos
- Tipo: Frontend
- Scope:
  - tabla + formulario lateral + deactivate.
  - errores backend visibles sin reinterpretación.

### R7-FE-002 — Admin ubicaciones
- Tipo: Frontend
- Scope:
  - tabla + formulario lateral + deactivate.
  - cliente tipado y filtros básicos.

### R7-FE-003 — Vista operativa de balances
- Tipo: Frontend
- Scope:
  - consulta de stock por ubicación/producto.
  - empty/error states claros.

### R7-FE-004 — Recepción y carga (shopfloor básico)
- Tipo: Frontend
- Scope:
  - flujo mínimo de recepción.
  - flujo mínimo de carga sobre plan.
  - foco en claridad operativa, sin automatismos.

## QA / CI

### R7-QA-001 — Integridad de inventario y movimientos
- Cobertura:
  - tenant isolation
  - idempotencia transaccional
  - no mutación retroactiva

### R7-QA-002 — Coherencia plan vs carga
- Cobertura:
  - eventos de carga reflejan pedidos del plan
  - errores de contrato consistentes

### R7-CI-001 — Gate OpenAPI de superficie física
- Cobertura:
  - endpoints R7 críticos
  - schemas de movimientos/recepción/carga
  - bloqueo de PR si se rompe contrato

## Orden recomendado de ejecución
1. `R7-DB-001`
2. `R7-BE-001`
3. `R7-FE-001`
4. `R7-DB-002`
5. `R7-BE-002`
6. `R7-DB-003`
7. `R7-BE-003`
8. `R7-FE-003`
9. `R7-DB-004`
10. `R7-BE-004`
11. `R7-BE-005`
12. `R7-FE-004`
13. `R7-QA-001`
14. `R7-QA-002`
15. `R7-CI-001`

## Definition of Done R7
- Catálogo operativo mínimo estable por tenant.
- Ubicaciones y stock con trazabilidad de movimientos append-only.
- Recepción y carga con evidencia operativa consultable.
- Contrato OpenAPI y CI protegen superficie R7.
- R1-R6 sin degradación semántica.
