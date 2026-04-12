# CorteCero — Estado real del repositorio

> Este documento es la línea base factual del repo. No es aspiracional ni to-be.
> Todo lo que aquí se afirma debe tener evidencia: código existente, test verde o smoke ejecutado.
> Si una capacidad no aparece aquí, no asumas que existe.

Última actualización: R7 activo. CI en verde sobre `main`.

---

## Estado por capa

### Backend

- **FastAPI** + SQLAlchemy + Pydantic + JWT
- Routers por dominio: `auth`, `orders`, `plans`, `routing`, `drivers`, `exceptions`, `exports`, `dashboard`, `audit`, `admin_*`
- Multi-tenant estricto en todas las queries
- RBAC con roles: `admin`, `logistics`, `office`, `driver`
- Contrato de errores uniforme: `{ detail: { code, message } }`
- Migraciones versionadas en `db/migrations/` (001–019), lexicográficas, idempotentes
- Seed reproducible en `backend/app/seed.py`
- Google Route Optimization integrado en `backend/app/optimization/google_provider.py`
- Mock provider disponible cuando no hay `GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID`
- `POST /routes/{id}/optimize` dispara el provider activo
- CI backend en verde: `backend-tests` (pytest en Docker)

### Frontend

- **Next.js** + TypeScript
- Cliente tipado en `frontend/lib/api.ts`
- Componentes operativos: `DispatcherRoutingCard`, `DriverRoutingCard`, `OperationalQueueCard`, `PendingQueueCard`, `OperationalResolutionQueueCard`, `OrderOperationalSnapshotsCard`, `AdminProductsCard`
- Panel dispatcher: asignación de rutas, despacho, visualización de paradas (lista, no mapa)
- PWA del conductor: arrive / complete / fail / skip / incidencias
- Frontend build en verde (CI `frontend-smoke`)
- Tests de componentes: 26 tests en verde

### Base de datos

- PostgreSQL 16
- Migraciones: 019 aplicadas
- Migraciones críticas recientes:
  - `017_user_role_driver.sql` — rol driver en tabla `users`
  - `018_driver_user_id.sql` — FK explícita `drivers.user_id → users.id` (PILOT-HARDEN-001)
  - `019_warehouse_locations.sql`
- Constraints y vocabularios explícitos donde aplica

### OpenAPI

- `openapi/openapi-v1.yaml` — contrato vivo, versionado
- Validado en CI (`openapi-check`)
- Cubre todos los endpoints del backend incluyendo `/planning/orders/ready-to-dispatch`

---

## Capacidades funcionales verificadas

| Capacidad | Estado | Evidencia |
|---|---|---|
| Autenticación JWT multi-tenant | VERIFICADO | tests + CI |
| Ingestión de pedidos | VERIFICADO | tests + CI |
| Cola de pedidos pendientes | VERIFICADO | tests + CI |
| Cola operativa | VERIFICADO | tests + CI |
| Cola de resolución operativa | VERIFICADO | tests + CI |
| Snapshots operativos | VERIFICADO | tests + CI |
| Planificación por zona/fecha | VERIFICADO | tests + CI |
| Auto-lock de planes | VERIFICADO | tests + CI |
| Excepciones operativas | VERIFICADO | tests + CI |
| Dashboard operativo | VERIFICADO | tests + CI |
| Export operativo | VERIFICADO | CI build |
| Auditoría append-only | VERIFICADO | tests + CI |
| Admin: zonas, clientes, usuarios, productos, tenant settings | VERIFICADO | tests + CI |
| Routing: flujo dispatcher (bloque C) | VERIFICADO | tests + CI |
| Routing: ejecución conductor (bloque D) | VERIFICADO | tests + CI |
| Routing: optimize con mock provider | VERIFICADO | tests + CI |
| Routing: optimize con Google provider | PARCIAL — timestamps fix aplicado; smoke pendiente de dataset geo-ready |
| Routing: driver auth con user_id explícito | VERIFICADO | PILOT-HARDEN-001 + CI |
| Frontend: panel dispatcher | VERIFICADO | tests + CI build |
| Frontend: PWA conductor | VERIFICADO | tests + CI build |

---

## Capacidades NO verificadas / pendientes

| Capacidad | Estado real |
|---|---|
| Mapa operativo (visualización de ruta en mapa) | NO EXISTE — frontend es list-centric, sin SDK de mapas |
| Seguimiento GPS en tiempo real del conductor | NO EXISTE |
| ETA dinámico post-incidencia | NO EXISTE — ETA es estático post-optimize |
| Reoptimización automática ante incidencias | NO EXISTE — trigger manual existe, flujo automático no |
| Prueba de entrega (foto/firma) | NO EXISTE |
| Notificación de ETA a cliente final | NO EXISTE |
| Fleet view (vista de flota en mapa) | NO EXISTE |
| Asistente IA en dispatcher | NO EXISTE |
| Asistente IA en app del conductor | NO EXISTE |
| Multi-vehicle en UI (fleet view) | NO EXISTE — backend soporta múltiples vehículos, UI no los visualiza juntos |
| Tráfico en tiempo real visible | PARCIAL — flag `considerRoadTraffic: true` enviado a Google; no hay visualización |

---

## Smoke y validación operativa

### Google Route Optimization smoke (`GOOGLE-SMOKE-001`)

- Script: `backend/scripts/smoke_google_optimization.py`
- Modos: `SMOKE_LIST_ROUTES`, `SMOKE_CREATE_ROUTE`, `CORTECERO_ROUTE_ID`
- Dataset helper: `backend/scripts/prepare_google_smoke_dataset.py`
- Estado actual: **BLOQUEADO por dataset** — tenant demo no tiene órdenes geo-ready suficientes
- Fix de timestamps (nanos) aplicado en `f370e81` pero no smoke con evidencia 200 aún

### Test suite

- Backend: `pytest` en Docker — CI verde en `main`
- Frontend: `npm test` — CI verde en `main`
- `test_routing_bloque_e.py` tiene 5 tests fallando localmente (relacionados con optimize Google — bloque `DEMO-OPT-001` pendiente)

---

## Configuración de entorno

El stack requiere:

```
backend/.env (o variables de entorno):
  DATABASE_URL
  JWT_SECRET_KEY
  CORS_ORIGINS

Para Google Route Optimization:
  GOOGLE_APPLICATION_CREDENTIALS   # path a service account .json
  GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID  # e.g. samurai-system
```

Service account montado en Docker: `~/.config/kelko/google/route-optimization-sa.json`

---

## Arquitectura de deployment

- Docker Compose: `postgres` + `backend` + `frontend`
- Backend: `uvicorn` en puerto 8000
- Frontend: Next.js en puerto 3000
- DB: PostgreSQL 16 en puerto 5432

---

## Contratos activos

- Error contract: `{ detail: { code: string, message: string } }`
- Todos los endpoints son tenant-scoped
- OpenAPI es fuente de verdad contractual
- `AGENTS.md` es fuente de verdad operativa para agentes

---

## Historial de fases

- R1–R6: cerradas
- R7: abierta (routing + optimización Google + demo)
- Bloque activo: `DEMO-OPT-001` (timestamp RFC3339 + smoke evidencia)
