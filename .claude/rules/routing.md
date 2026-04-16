# Reglas — Módulo de Routing

Aplica cuando trabajas en `backend/app/routers/routing.py`, `backend/app/optimization/`, o los tests de routing (`test_routing_bloque_*.py`).

## Arquitectura del módulo

```
routing.py                 # todos los endpoints de routing/despacho
optimization/
  protocol.py             # interface RouteOptimizationProvider
  google_provider.py      # implementación Google Route Optimization API
  mock_provider.py        # implementación mock para tests
```

El provider activo se selecciona en `_get_optimization_provider()`:
- Si `GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID` tiene valor → `GoogleRouteOptimizationProvider`
- Si vacío → `MockRouteOptimizationProvider`

## Endpoints del módulo (paths actuales)

```
GET  /planning/orders/ready-to-dispatch   # pedidos listos para asignar
GET  /vehicles/available
POST /routes/plan
POST /routes/{routeId}/dispatch
POST /routes/{routeId}/optimize
POST /routes/{routeId}/move-stop
GET  /routes
GET  /routes/{routeId}
GET  /routes/{routeId}/events
POST /stops/{stopId}/arrive
POST /stops/{stopId}/complete
POST /stops/{stopId}/fail
POST /stops/{stopId}/skip
GET  /driver/routes
GET  /routes/{routeId}/next-stop
```

**Nota**: El path es `/planning/orders/ready-to-dispatch` (no `/orders/...`).
El cambio fue necesario por colisión con `GET /orders/{order_id}` en `orders.router`.

## Driver auth

`_resolve_current_driver()` usa:
```python
Driver.user_id == current.id  # FK explícita (migration 018)
```

No `Driver.id == current.id` — ese es el patrón anterior, ya eliminado.

## Google Provider — reglas críticas

### Timestamps RFC3339

`_to_rfc3339_utc()` debe producir timestamps **sin fracción de segundo**:
```python
value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
```
Google Route Optimization API rechaza timestamps con `nanos != 0`.

### Coordenadas obligatorias

`POST /routes/{id}/optimize` falla con `MISSING_GEO` si alguna parada no tiene `lat/lng`.
El dataset demo debe tener coordenadas reales o sintéticas en los clientes.

### Preparar dataset geo-ready

```bash
python3 backend/scripts/prepare_google_smoke_dataset.py
```

## Tests de routing

| Archivo | Qué cubre |
|---------|-----------|
| `test_routing_bloque_c.py` | Flujo dispatcher (plan, dispatch, move-stop) |
| `test_routing_bloque_d.py` | Ejecución conductor (arrive/complete/fail/skip) |
| `test_routing_bloque_e.py` | Optimize con Google provider real (requiere credenciales) |
| `test_routing_bloque_e2.py` | Optimize con mock provider |
| `test_routing_driver_auth_d2.py` | Driver auth con user_id explícito |
| `test_routing_gps_a3.py` | GPS-001: POST /driver/location, GET /routes/{id}/driver-position, GET /driver/active-positions |
| `test_routing_proof_a2.py` | POD-001: POST /stops/{id}/proof, GET /stops/{id}/proof |

`test_routing_bloque_e.py` falla en CI sin `GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID`.
Esto es esperado en CI — los 5 tests de ese archivo son bloqueo conocido (DEMO-OPT-001).

## Smoke script

```bash
# Listar rutas draft
SMOKE_LIST_ROUTES=1 python3 backend/scripts/smoke_google_optimization.py

# Crear ruta + optimize
SMOKE_CREATE_ROUTE=1 \
GOOGLE_APPLICATION_CREDENTIALS=~/.config/kelko/google/route-optimization-sa.json \
GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID=samurai-system \
python3 backend/scripts/smoke_google_optimization.py
```

## Estado actual de DEMO-OPT-001

- CERRADO_CON_EVIDENCIA_LOCAL — commit `59bd16d`
- Smoke 200: confirmado. 2 paradas optimizadas, ETAs reales de Google, totalDuration=2693s.
- Evidence: `docs/evidence/DEMO-OPT-001.json`
- Fixes: seed.py backfill fuerza coordenadas Mallorca; `_build_result` maneja `skippedShipments` sin crashear.
