# CorteCero — Análisis de Plataforma v2

> **Fecha**: 2026-04-16
> **OpenAPI**: 1.5.2
> **Rama analizada**: `main`
> **Fuente de verdad**: estado real del repositorio (código + tests explorados)

---

## Sistema de estados

| Estado | Definición estricta |
|--------|---------------------|
| `PROMULGADO` | Código en `main` + CI green documentado + sin drift conocido entre runtime/OpenAPI/frontend |
| `VERIFICADO LOCAL` | Tests pasan en entorno local; CI post-commit no confirmado externamente |
| `IMPLEMENTADO NO VERIFICADO` | Código presente en repo; tests ausentes, insuficientes o smoke externo pendiente |
| `PARCIAL` | Parte del flujo verificada; otra parte ausente o bloqueada por prerrequisito |
| `NO EXISTE` | Ningún código funcional para esta capacidad |

**Nota importante**: `PROMULGADO` no significa "en producción". No existe entorno de producción conocido. El estado más alto del repo es CI green en local/GitHub Actions.

---

## 1. Infraestructura y plataforma base

| Elemento | Detalle | Estado |
|----------|---------|--------|
| Backend stack | FastAPI + SQLAlchemy 2.x + Pydantic v2 + JWT | `PROMULGADO` |
| Frontend stack | Next.js + TypeScript + Vitest | `PROMULGADO` |
| Base de datos | PostgreSQL 16 — 21 migraciones (001–021, sin 014) | `PROMULGADO` |
| Docker Compose | postgres + backend + frontend | `VERIFICADO LOCAL` — sin CI de stack completo integrado |
| CI: backend-tests | `docker compose run --rm backend pytest` | `PROMULGADO` — verde documentado |
| CI: frontend-smoke | Next.js build | `PROMULGADO` — verde documentado |
| CI: openapi-check | `openapi-spec-validator` sobre v1.5.2 | `PROMULGADO` — verde documentado |
| Alineación 3 vías | `routing.py` ↔ `openapi-v1.yaml` ↔ `api.ts` | `PROMULGADO` — 79 paths en spec |
| Multi-tenant estricto | `tenant_id` en todas las queries | `PROMULGADO` |
| RBAC | Roles: admin / logistics / office / driver | `PROMULGADO` |
| Contrato de errores | `{ detail: { code, message } }` | `PROMULGADO` |
| Seed reproducible | `backend/app/seed.py` — coordenadas sintéticas (SEC-DATA-001) | `PROMULGADO` |
| Sin datos reales de cliente | SEC-DATA-001 aplicado y publicado | `PROMULGADO` |

---

## 2. Operaciones core (pre-routing)

Todas estas capacidades tienen tests en CI y estaban verdes en el último estado documentado de CI.

| Capacidad | Archivo de test principal | Estado |
|-----------|--------------------------|--------|
| Autenticación JWT multi-tenant | `test_auth_tenant_aware.py` | `PROMULGADO` |
| Ingestión de pedidos | `test_ingestion_immutability.py` | `PROMULGADO` |
| Cola pendiente | `test_pending_queue.py` | `PROMULGADO` |
| Cola operativa | `test_operational_queue.py` | `PROMULGADO` |
| Cola de resolución operativa | `test_operational_resolution_queue.py` | `PROMULGADO` |
| Snapshots operativos (run + schema + timeline) | `test_operational_snapshot_*.py` ×3 | `PROMULGADO` |
| Planificación por zona/fecha | `test_plan_*.py` ×6 | `PROMULGADO` |
| Auto-lock de planes | `test_plans_auto_lock.py` | `PROMULGADO` |
| Asignación de vehículo a plan | `test_plan_vehicle_assignment.py` | `PROMULGADO` |
| Alertas de capacidad | `test_plan_capacity_alerts.py` | `PROMULGADO` |
| Consolidación de clientes en plan | `test_plan_customer_consolidation.py` | `PROMULGADO` |
| Excepciones operativas (scope + transiciones) | `test_exception_*.py` ×2 | `PROMULGADO` |
| Dashboard / métricas de fuente | `test_dashboard_source_metrics.py` | `PROMULGADO` |
| Export operativo (dataset) | `test_operational_dataset_export.py` | `PROMULGADO` |
| Auditoría append-only | `test_audit_append_only.py` | `PROMULGADO` |
| Admin: zonas | `test_admin_zones.py` | `PROMULGADO` |
| Admin: clientes | `test_admin_customers.py` | `PROMULGADO` |
| Admin: productos | `test_admin_products.py` | `PROMULGADO` |
| Admin: usuarios | `test_admin_users.py` | `PROMULGADO` |
| Admin: tenant settings | `test_admin_tenant_settings.py` | `PROMULGADO` |
| Perfiles operativos de cliente | `test_customer_operational_profile.py` | `PROMULGADO` |
| Excepciones operativas de cliente | `test_customer_operational_exceptions.py` | `PROMULGADO` |
| Pesos de pedido (update + total) | `test_order_weight_update.py`, `test_order_total_weight.py` | `PROMULGADO` |
| Tipo de ingesta de pedido | `test_order_intake_type.py` | `PROMULGADO` |
| State de pedido operativo | `test_order_operational_state.py` | `PROMULGADO` |
| DST / timezone hardening | `test_operational_temporal_dst.py`, `test_timezone_hardening_schema.py` | `PROMULGADO` |
| Locked plan requiere excepción | `test_locked_plan_requires_exception.py` | `PROMULGADO` |

---

## 3. Routing — Flujo dispatcher (Bloques C / B)

| Capacidad | Test | Estado |
|-----------|------|--------|
| `GET /planning/orders/ready-to-dispatch` | `test_routing_bloque_c.py` | `PROMULGADO` |
| `GET /vehicles/available` | `test_routing_bloque_c.py` | `PROMULGADO` |
| `POST /routes/plan` → crea rutas en estado `draft` | `test_routing_bloque_c.py`, `test_routing_bloque_e.py` | `PROMULGADO` |
| `POST /routes/{id}/dispatch` → `draft/planned → dispatched` | `test_routing_bloque_c.py` | `PROMULGADO` |
| `POST /routes/{id}/move-stop` | `test_routing_bloque_c.py` | `PROMULGADO` |
| `GET /routes`, `GET /routes/{id}` | `test_routing_bloque_c.py` | `PROMULGADO` |
| `GET /routes/{id}/events` | `test_routing_bloque_c.py` | `PROMULGADO` |
| Driver auth con `Driver.user_id` (migration 018) | `test_routing_driver_auth_d2.py`, `test_pilot_hardening_001.py` | `PROMULGADO` |

---

## 4. Routing — Optimización (E.1 Mock + E.2 Google)

### 4.1 E.1 — Mock provider + endpoint `POST /routes/{id}/optimize`

El fixture `_force_mock_provider` en `test_routing_bloque_e.py` activa siempre el mock en tests.
No requiere credenciales externas → CI-compatible.

| Capacidad | Test | Estado |
|-----------|------|--------|
| `RouteOptimizationProvider` protocol (DTOs + interface) | `test_routing_bloque_e2.py` | `PROMULGADO` |
| `MockRouteOptimizationProvider` (15 min/parada) | `test_routing_bloque_e.py` ×12 | `PROMULGADO` |
| `POST /routes/{id}/optimize` → `draft → planned` | `test_routing_bloque_e.py` | `PROMULGADO` |
| Guard `MISSING_GEO` 422 (parada sin lat/lng) | `test_routing_bloque_e.py` | `PROMULGADO` |
| Guard 409 si ruta no está en `draft` | `test_routing_bloque_e.py` | `PROMULGADO` |
| Guard 404 multi-tenant | `test_routing_bloque_e.py` | `PROMULGADO` |
| Guard 403 para rol `office` | `test_routing_bloque_e.py` | `PROMULGADO` |
| Emit evento `route.planned` (actor: system) | `test_routing_bloque_e.py` | `PROMULGADO` |
| `Route.optimization_request_id` / `optimization_response_json` poblados | `test_routing_bloque_e.py` | `PROMULGADO` |
| Timestamps RFC3339 sin fracción de segundo | `_to_rfc3339_utc()` en routing.py | `PROMULGADO` — fix aplicado en commit anterior |

### 4.2 E.2 — Google Route Optimization provider (ADC / service account)

`test_routing_bloque_e2.py` monkeypatchea `_fetch_access_token` y el cliente HTTP → sin credenciales reales → CI-compatible.

| Capacidad | Test / evidencia | Estado |
|-----------|-----------------|--------|
| `_get_optimization_provider()` devuelve mock si `project_id` vacío | `test_routing_bloque_e2.py` | `VERIFICADO LOCAL` |
| `_get_optimization_provider()` devuelve `GoogleRouteOptimizationProvider` si `project_id` presente | `test_routing_bloque_e2.py` | `VERIFICADO LOCAL` |
| `GoogleRouteOptimizationProvider.optimize()` — parseo de respuesta, secuencia, ETA | `test_routing_bloque_e2.py` (HTTP mockeado) | `VERIFICADO LOCAL` |
| Error explícito si faltan shipments en respuesta Google | `test_routing_bloque_e2.py` | `VERIFICADO LOCAL` |
| Auth ADC / service account (`_fetch_access_token`) | Código en `google_provider.py` (7.2 KB) | `IMPLEMENTADO NO VERIFICADO` |
| **Smoke real** con `GOOGLE_APPLICATION_CREDENTIALS` + dataset geo-ready | Sin evidencia 200 — DEMO-OPT-001 bloqueado | `IMPLEMENTADO NO VERIFICADO` |

**Nota sobre DEMO-OPT-001**: El código E.2 está presente y el proveedor Google implementado. Lo que bloquea el cierre como smoke-green es el dataset geo-ready en el tenant demo. El script `prepare_google_smoke_dataset.py` existe para resolverlo. No declarar "integración Google operativa" sin smoke 200 real.

---

## 5. Routing — Ejecución conductor (Bloque D)

| Capacidad | Test | Estado |
|-----------|------|--------|
| `GET /driver/routes` | `test_routing_bloque_d.py` | `PROMULGADO` |
| `GET /routes/{id}/next-stop` | `test_routing_bloque_d.py` | `PROMULGADO` |
| `POST /stops/{id}/arrive` + idempotencia | `test_routing_bloque_d.py` | `PROMULGADO` |
| `POST /stops/{id}/complete` + idempotencia | `test_routing_bloque_d.py` | `PROMULGADO` |
| `POST /stops/{id}/fail` + idempotencia | `test_routing_bloque_d.py` | `PROMULGADO` |
| `POST /stops/{id}/skip` + idempotencia | `test_routing_bloque_d.py` | `PROMULGADO` |
| `POST /incidents` / `GET /incidents` | `test_routing_bloque_d.py` | `PROMULGADO` |
| `POST /incidents/{id}/review`, `/resolve` | `test_routing_bloque_d.py` | `PROMULGADO` |
| Máquina de estados de ruta: `dispatched → in_progress → completed` | `test_routing_bloque_d.py` | `PROMULGADO` |

---

## 6. R8 — Fase A: MAP-001 (Mapa de ruta)

R8 es la fase contenedora. MAP-001 es el ticket concreto de mapa. Se separan a continuación.

### Backend MAP-001

| Capacidad | Ubicación | Test | Estado |
|-----------|-----------|------|--------|
| `route_geometry` derivada de `optimization_response_json` polylines | `routing.py` / `RouteOut` schema | `test_map_geom_001.py` ×2 | `VERIFICADO LOCAL` |
| `route_geometry = null` si no hay polylines disponibles | `routing.py` | `test_map_geom_001.py` | `VERIFICADO LOCAL` |
| `RouteGeometryOut` schema en OpenAPI 1.5.2 | `openapi-v1.yaml` | openapi-check | `VERIFICADO LOCAL` |

### Frontend MAP-001

| Capacidad | Ubicación | Estado |
|-----------|-----------|--------|
| `RouteMapCard.tsx` — mapa de ruta con Google Maps JS API | `frontend/components/RouteMapCard.tsx` | `IMPLEMENTADO NO VERIFICADO` |
| Marcadores de paradas por estado | `RouteMapCard.tsx` | `IMPLEMENTADO NO VERIFICADO` |
| Marcador de posición del conductor (polling 30 s) | `RouteMapCard.tsx` | `IMPLEMENTADO NO VERIFICADO` |
| Renderizado real | Requiere `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` configurada | `IMPLEMENTADO NO VERIFICADO` |

**Advertencia sobre reglas stale**: `.claude/rules/frontend.md` dice "no hay SDK Mapbox/Google Maps JS" — esto es incorrecto. `RouteMapCard.tsx` existe e importa Google Maps JS. Las reglas deben actualizarse.

**Qué no puede afirmarse de MAP-001**: El mapa no tiene evidencia de rendering real con API key en ningún dispositivo. Sin esa evidencia no puede llamarse "mapa operativo".

---

## 7. R8 — Fase A: POD-001 (Proof of Delivery)

### Backend POD-001

| Capacidad | Ubicación | Test | Estado |
|-----------|-----------|------|--------|
| Migration `020_stop_proofs.sql` — tabla `stop_proofs` | `db/migrations/020_stop_proofs.sql` | — | `PROMULGADO` — migration en main |
| ORM `StopProof` | `backend/app/models.py` | — | `PROMULGADO` |
| `POST /stops/{id}/proof` happy path (arrived + completed) | `test_routing_proof_a2.py` | 9 tests | `VERIFICADO LOCAL` |
| `POST /stops/{id}/proof` — `signature_data` obligatoria para `type=signature` | `test_routing_proof_a2.py` | | `VERIFICADO LOCAL` |
| Guard 409 estado incorrecto | `test_routing_proof_a2.py` | | `VERIFICADO LOCAL` |
| Guard 404 multi-tenant | `test_routing_proof_a2.py` | | `VERIFICADO LOCAL` |
| `GET /stops/{id}/proof` happy path | `test_routing_proof_a2.py` | | `VERIFICADO LOCAL` |
| `GET /stops/{id}/proof` sin proof → 404 | `test_routing_proof_a2.py` | | `VERIFICADO LOCAL` |
| `StopProofCreateRequest` / `StopProofOut` en OpenAPI 1.5.2 | `openapi-v1.yaml` | | `VERIFICADO LOCAL` |

### Frontend POD-001

| Capacidad | Ubicación | Estado |
|-----------|-----------|--------|
| Modal de firma canvas en `DriverRoutingCard.tsx` | `frontend/components/DriverRoutingCard.tsx` | `IMPLEMENTADO NO VERIFICADO` |
| Envío de `signature_data` a `POST /stops/{id}/proof` | `DriverRoutingCard.tsx` | `IMPLEMENTADO NO VERIFICADO` |
| Evidencia de firma real en dispositivo | Sin smoke en dispositivo | `IMPLEMENTADO NO VERIFICADO` |
| Foto como prueba de entrega | No hay UI ni endpoint para foto | `NO EXISTE` |

---

## 8. R8 — Fase A: GPS-001 (Seguimiento de posición)

### Backend GPS-001

| Capacidad | Ubicación | Test | Estado |
|-----------|-----------|------|--------|
| Migration `021_driver_positions.sql` — tabla `driver_positions` con índice | `db/migrations/021_driver_positions.sql` | — | `PROMULGADO` |
| ORM `DriverPosition` | `backend/app/models.py` | — | `PROMULGADO` |
| `POST /driver/location` happy path (ruta `in_progress`) | `test_routing_gps_a3.py` | 10 tests | `VERIFICADO LOCAL` |
| Guard 409 ruta no `in_progress` | `test_routing_gps_a3.py` | | `VERIFICADO LOCAL` |
| Guard 404 multi-tenant | `test_routing_gps_a3.py` | | `VERIFICADO LOCAL` |
| Guard 401 sin auth | `test_routing_gps_a3.py` | | `VERIFICADO LOCAL` |
| `GET /routes/{id}/driver-position` happy path | `test_routing_gps_a3.py` | | `VERIFICADO LOCAL` |
| `GET /routes/{id}/driver-position` sin posición → 404 | `test_routing_gps_a3.py` | | `VERIFICADO LOCAL` |
| `GET /driver/active-positions` (logistics) | `test_routing_gps_a3.py` | | `VERIFICADO LOCAL` |
| `DriverLocationUpdateRequest` / `DriverPositionOut` en OpenAPI 1.5.2 | `openapi-v1.yaml` | | `VERIFICADO LOCAL` |

### Frontend GPS-001

| Capacidad | Ubicación | Estado |
|-----------|-----------|--------|
| `useGpsTracking` hook en `DriverRoutingCard.tsx` | `frontend/components/DriverRoutingCard.tsx` | `IMPLEMENTADO NO VERIFICADO` |
| Publicación de posición cada N segundos durante ruta `in_progress` | `DriverRoutingCard.tsx` | `IMPLEMENTADO NO VERIFICADO` |
| Evidencia en dispositivo real con GPS | Sin smoke en dispositivo | `IMPLEMENTADO NO VERIFICADO` |
| GPS server-push / SSE en tiempo real | No existe — solo polling 30 s por el dispatcher | `NO EXISTE` |
| Fleet view (múltiples conductores en un mapa) | `GET /driver/active-positions` backend OK; sin UI dispatcher | `PARCIAL` |

---

## 9. Frontend — Componentes y cobertura de tests

21 componentes TSX en `frontend/components/`.

| Componente | Test | Estado del componente | Estado del test |
|------------|------|-----------------------|-----------------|
| `DispatcherRoutingCard.tsx` | `dispatcher-routing-card.test.tsx` | `PROMULGADO` | `PROMULGADO` |
| `DriverRoutingCard.tsx` | `driver-routing-card.test.tsx` | `PARCIAL` — GPS/POD implementados sin smoke | `PROMULGADO` |
| `OperationalQueueTableCard.tsx` | `operational-queue-table-card.test.tsx` | `PROMULGADO` | `PROMULGADO` |
| `PendingQueueTableCard.tsx` | `pending-queue-table-card.test.tsx` | `PROMULGADO` | `PROMULGADO` |
| `OperationalResolutionQueueTableCard.tsx` | `operational-resolution-queue-table-card.test.tsx` | `PROMULGADO` | `PROMULGADO` |
| `OrderSnapshotsTimelineCard.tsx` | `order-snapshots-timeline-card.test.tsx` | `PROMULGADO` | `PROMULGADO` |
| `AdminProductsCard.tsx` | `admin-products-card.test.tsx` | `PROMULGADO` | `PROMULGADO` |
| `CapacityAlertsTableCard.tsx` | `capacity-alerts-table-card.test.tsx` | `PROMULGADO` | `PROMULGADO` |
| `ExceptionsTableCard.tsx` | `exceptions-table-card.test.tsx` | `PROMULGADO` | `PROMULGADO` |
| `PlansTableCard.tsx` | `plans-table-card.test.tsx` | `PROMULGADO` | `PROMULGADO` |
| `PlanConsolidationCard.tsx` | `plan-consolidation-card.test.tsx` | `PROMULGADO` | `PROMULGADO` |
| `OrdersTableCard.tsx` | `orders-table-card.test.tsx` | `PROMULGADO` | `PROMULGADO` |
| `RouteMapCard.tsx` | **Sin test** | `IMPLEMENTADO NO VERIFICADO` | `NO EXISTE` |
| `RouteDetailCard.tsx` | **Sin test** | `VERIFICADO LOCAL` | `NO EXISTE` |
| `RoutingSidePanels.tsx` | **Sin test** | `VERIFICADO LOCAL` | `NO EXISTE` |
| `DispatcherRoutingShell.tsx` | **Sin test** | `VERIFICADO LOCAL` | `NO EXISTE` |
| `AdminShell.tsx` | **Sin test** | `VERIFICADO LOCAL` | `NO EXISTE` |
| `AppShell.tsx` | **Sin test** | `VERIFICADO LOCAL` | `NO EXISTE` |
| `AdminCustomersSection.tsx` | **Sin test** | `VERIFICADO LOCAL` | `NO EXISTE` |
| `AdminZonesSection.tsx` | **Sin test** | `VERIFICADO LOCAL` | `NO EXISTE` |
| `KpiRow.tsx` | **Sin test** | `VERIFICADO LOCAL` | `NO EXISTE` |

---

## 10. Capacidades que NO EXISTEN

| Capacidad | Por qué no existe |
|-----------|------------------|
| GPS server-push / SSE en tiempo real | Solo polling 30 s por parte del dispatcher. No hay WebSocket ni SSE. |
| ETA dinámico post-incidencia | ETA es estático, calculado en `optimize`. No se recalcula ante incidencias. |
| Reoptimización automática ante incidencias | El trigger manual de optimize existe; flujo automático no existe. |
| Foto como prueba de entrega | Schema preparado en backend; UI sin implementar. |
| Notificación de ETA al cliente final | Ningún canal de notificación existe. |
| Fleet view en UI dispatcher | Backend `GET /driver/active-positions` existe; UI de mapa con múltiples conductores no. |
| Asistente IA (dispatcher) | No existe en ninguna capa. |
| Asistente IA (app conductor) | No existe en ninguna capa. |
| Visibilidad de tráfico en tiempo real | Flag `considerRoadTraffic: true` enviado a Google en E.2; sin visualización propia. |

---

## 11. Gaps documentales conocidos (reglas stale)

Estos archivos de reglas describen un estado anterior y requieren actualización:

| Archivo | Afirmación stale | Realidad actual |
|---------|-----------------|-----------------|
| `.claude/rules/frontend.md` | "no hay SDK Mapbox/Google Maps JS" | `RouteMapCard.tsx` implementado con Google Maps JS |
| `.claude/rules/frontend.md` | Lista de componentes incompleta (7 en reglas, 21 en repo) | 21 componentes activos |
| `.claude/rules/routing.md` | "5 tests fallando en bloque_e" | 12 tests con `_force_mock_provider`; estado distinto |
| `.claude/rules/routing.md` | E.2 listado como no iniciado | `google_provider.py` (7.2 KB) existe y tiene tests |
| `docs/as-is.md` | No menciona E.2, ni R8 GPS/POD tests, ni `test_map_geom_001.py` | Repo significativamente más avanzado |

---

## 12. Resumen ejecutivo por capa

| Capa | Estado general | Detalle |
|------|---------------|---------|
| Operaciones core (órdenes, planes, colas, dashboard, admin) | `PROMULGADO` | 46 archivos de test, CI verde documentado |
| Routing dispatcher (Bloques B/C) | `PROMULGADO` | Flujo completo verificado en CI |
| Routing conducción (Bloque D) | `PROMULGADO` | Arrive/complete/fail/skip + idempotencia |
| Optimización E.1 (mock) | `PROMULGADO` | 12 tests, mock fixture garantiza CI-compatible |
| Optimización E.2 (Google real) | `VERIFICADO LOCAL` (unit) / `IMPLEMENTADO NO VERIFICADO` (smoke) | Código completo; sin smoke 200 real |
| R8 GPS-001 backend | `VERIFICADO LOCAL` | 10 tests, DB-only, sin smoke en dispositivo |
| R8 POD-001 backend | `VERIFICADO LOCAL` | 9 tests, DB-only, sin smoke en dispositivo |
| R8 MAP-001 backend (geometría) | `VERIFICADO LOCAL` | 2 tests, DB-only |
| R8 MAP-001 frontend (`RouteMapCard`) | `IMPLEMENTADO NO VERIFICADO` | Requiere API key; sin evidencia de render real |
| R8 GPS-001 frontend (hook GPS) | `IMPLEMENTADO NO VERIFICADO` | Código presente; sin smoke en dispositivo real |
| R8 POD-001 frontend (firma canvas) | `IMPLEMENTADO NO VERIFICADO` | Código presente; sin smoke en dispositivo real |
| Frontend componentes core (12 con test) | `PROMULGADO` | CI frontend-smoke verde |
| Frontend componentes sin test (9) | `VERIFICADO LOCAL` | Build verde; sin tests de componente |

---

## 13. Métricas del repo (estado actual)

| Métrica | Valor |
|---------|-------|
| OpenAPI versión | 1.5.2 |
| Paths en OpenAPI | 79 |
| Schemas en OpenAPI | 66 |
| Migraciones DB | 21 (001–021, sin 014) |
| Tablas ORM | 23 |
| Archivos de test backend | 49 (incl. conftest, helpers, __init__) |
| Archivos de test frontend | 12 |
| Componentes frontend | 21 |
| Workflows CI | 3 (backend-tests, frontend-smoke, openapi-check) |
| Provider módulo optimization | 3 archivos (protocol, mock, google) |

---

*Este documento es descriptivo del estado real. No es aspiracional.*
*Actualizar cuando cambie el estado de CI, smoke o evidencia de cualquier capacidad.*
