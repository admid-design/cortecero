# CorteCero R2 Backlog (Admin / Master Data)

Baseline: `r1-fixes`
Objetivo R2: habilitar administración de maestros (`zones`, `customers`, `users`, `tenant settings`) sin romper la semántica R1.

## Reglas de ejecución
- Todo endpoint admin debe ser tenant-aware (`tenant_id` obligatorio en query scope).
- `admin` tiene CRUD; `logistics` y `office` no escriben maestros.
- No borrar físicamente `zones/customers/users` en R2; usar `active=false`.
- Todo cambio de maestro relevante genera `audit_log`.
- No introducir features de R3+ (peso, vehículo, routing, cliente operativo).

## Tickets Backend

### R2-BE-001 — Router Admin Zones
- Tipo: Backend
- Prioridad: Alta
- Scope:
  - `GET /admin/zones`
  - `POST /admin/zones`
  - `PATCH /admin/zones/{zone_id}`
- Aceptación:
  - `admin` crea/edita/lista.
  - `office/logistics` solo lectura o `403` según endpoint.
  - `name` único por tenant.
  - `timezone` y `default_cutoff_time` validados.

### R2-BE-002 — Router Admin Customers
- Tipo: Backend
- Prioridad: Alta
- Scope:
  - `GET /admin/customers`
  - `POST /admin/customers`
  - `PATCH /admin/customers/{customer_id}`
- Aceptación:
  - `customer.zone_id` debe pertenecer al mismo tenant.
  - `cutoff_override_time` opcional y validado.
  - `active=false` soportado.

### R2-BE-003 — Router Admin Users
- Tipo: Backend
- Prioridad: Alta
- Scope:
  - `GET /admin/users`
  - `POST /admin/users`
  - `PATCH /admin/users/{user_id}`
- Aceptación:
  - `email` único por tenant.
  - roles permitidos: `office|logistics|admin`.
  - `password_hash` generado en creación/cambio de password.
  - no permitir desactivar último admin activo del tenant.

### R2-BE-004 — Tenant Settings Endpoint
- Tipo: Backend
- Prioridad: Media
- Scope:
  - `GET /admin/tenant-settings`
  - `PATCH /admin/tenant-settings`
- Aceptación:
  - editar `default_cutoff_time`, `default_timezone`, `auto_lock_enabled`.
  - auditoría de cambio de configuración.

### R2-BE-005 — Error Contract Admin
- Tipo: Backend
- Prioridad: Alta
- Scope:
  - normalizar errores admin con códigos consistentes.
- Códigos mínimos:
  - `ENTITY_NOT_FOUND` (404)
  - `RESOURCE_CONFLICT` (409)
  - `INVALID_STATE_TRANSITION` (422)
  - `RBAC_FORBIDDEN` (403)
- Aceptación:
  - payload homogéneo `{"detail":{"code":"...","message":"..."}}`.

## Tickets DB

### R2-DB-001 — Migración 002 Admin Hardening
- Tipo: DB
- Prioridad: Alta
- Scope:
  - `updated_at` + trigger en `zones`, `customers`, `users`, `tenants`.
  - índices:
    - `zones(tenant_id, active)`
    - `customers(tenant_id, active, zone_id)`
    - `users(tenant_id, is_active, role)`
- Aceptación:
  - migración idempotente en entorno limpio.
  - migración compatible con datos seed actuales.

### R2-DB-002 — Constraints de Integridad Admin
- Tipo: DB
- Prioridad: Media
- Scope:
  - reforzar checks no cubiertos por app (si aplica).
- Aceptación:
  - constraints no rompen flujo seed ni tests R1.

## Tickets Frontend

### R2-FE-001 — Shell Admin
- Tipo: Frontend
- Prioridad: Alta
- Scope:
  - sección Admin con navegación:
    - Zonas
    - Clientes
    - Usuarios
    - Configuración Tenant
- Aceptación:
  - accesible solo para `admin`.
  - estado de error/loader básico consistente.

### R2-FE-002 — Pantalla Zonas
- Tipo: Frontend
- Prioridad: Alta
- Scope:
  - tabla + formulario crear/editar.
  - activar/desactivar zona.
- Aceptación:
  - refresco tras acción.
  - manejo de errores por `detail.code`.

### R2-FE-003 — Pantalla Clientes
- Tipo: Frontend
- Prioridad: Alta
- Scope:
  - tabla + formulario crear/editar.
  - selector de zona del tenant.
- Aceptación:
  - validación visual de datos obligatorios.
  - desactivación (`active`) sin borrado.

### R2-FE-004 — Pantalla Usuarios
- Tipo: Frontend
- Prioridad: Alta
- Scope:
  - listado usuarios.
  - alta usuario y cambio rol/estado.
- Aceptación:
  - no exponer hashes ni datos sensibles.
  - feedback claro de conflicto de email.

### R2-FE-005 — Pantalla Tenant Settings
- Tipo: Frontend
- Prioridad: Media
- Scope:
  - edición de `default_cutoff_time`, `default_timezone`, `auto_lock_enabled`.
- Aceptación:
  - persistencia correcta y mensaje de confirmación.

## Tickets Tests

### R2-QA-001 — Tests RBAC Admin
- Tipo: QA/Backend tests
- Prioridad: Alta
- Scope:
  - cubrir permisos por rol en endpoints admin.
- Aceptación:
  - `office/logistics` no escriben.
  - `admin` sí escribe.

### R2-QA-002 — Tests Tenant Isolation Admin
- Tipo: QA/Backend tests
- Prioridad: Alta
- Scope:
  - un tenant no puede leer/escribir maestros de otro.
- Aceptación:
  - casos positivos y negativos por entidad.

### R2-QA-003 — Tests CRUD Happy Path Admin
- Tipo: QA/Backend tests
- Prioridad: Alta
- Scope:
  - create/list/update para zonas, clientes, usuarios, tenant settings.
- Aceptación:
  - asserts de payload y persistencia en DB.

### R2-QA-004 — Regression Pack R1
- Tipo: QA/Backend tests
- Prioridad: Alta
- Scope:
  - mantener suite crítica R1 en verde.
- Aceptación:
  - `pytest -q` sin regresiones.

## Tickets CI

### R2-CI-001 — Workflow Backend Tests
- Tipo: CI
- Prioridad: Alta
- Scope:
  - GitHub Actions: build backend + `pytest`.
- Aceptación:
  - PR falla si tests fallan.

### R2-CI-002 — OpenAPI Validation
- Tipo: CI
- Prioridad: Media
- Scope:
  - check de spec OpenAPI (`yaml` válido + lint básico).
- Aceptación:
  - PR falla ante contrato inválido.

### R2-CI-003 — Docker Build Check
- Tipo: CI
- Prioridad: Media
- Scope:
  - build de imágenes backend/frontend.
- Aceptación:
  - PR falla si build rompe.

## Orden recomendado (secuencial)
1. R2-DB-001
2. R2-BE-001, R2-BE-002, R2-BE-003, R2-BE-004, R2-BE-005
3. R2-QA-001, R2-QA-002, R2-QA-003, R2-QA-004
4. R2-FE-001 a R2-FE-005
5. R2-CI-001 a R2-CI-003

## No-hacer en R2
- No integrar `fastapi-users` como dependencia core.
- No refactor de arquitectura a boilerplate externo.
- No features de R3/R4/R5.
- No soft-delete complejo: `active` es suficiente.
- No cambiar semántica `late / lock / exception`.
