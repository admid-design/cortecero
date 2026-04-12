# GOOGLE-SMOKE-001 — Smoke test real de Route Optimization

**Tipo:** Validación operativa (no desarrollo)
**Fecha apertura:** 2026-04-12
**Estado:** ABIERTO

---

## Objetivo

Validar el proveedor `GoogleRouteOptimizationProvider` end-to-end contra el
proyecto `samurai-system` sin añadir features nuevas ni modificar código de
producción.

---

## Entorno

| Campo | Valor |
|---|---|
| Proyecto GCP | `samurai-system` |
| API activada | Route Optimization API |
| Auth | ADC / service account (privado, fuera de repo) |
| Location | `global` |
| Backend | El que corre en el entorno piloto |
| Script | `backend/scripts/smoke_google_optimization.py` |

### Variables de entorno requeridas (entorno privado)

```bash
# Credencial Google — NO en repo
export GOOGLE_APPLICATION_CREDENTIALS=/ruta/privada/service-account.json

# Config backend
export GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID=samurai-system
export GOOGLE_ROUTE_OPTIMIZATION_LOCATION=global
export GOOGLE_ROUTE_OPTIMIZATION_TIMEOUT_SECONDS=30

# Config smoke test
export CORTECERO_BASE_URL=http://localhost:8000
export CORTECERO_TENANT_SLUG=demo-cortecero
export CORTECERO_EMAIL=logistics@demo.cortecero.app
export CORTECERO_PASSWORD=logistics123
export CORTECERO_ROUTE_ID=<uuid-ruta-draft-con-paradas>
```

---

## Pre-requisitos antes de ejecutar

1. **Backend activo** con las nuevas variables inyectadas (el proveedor
   switch de mock → google ocurre en arranque si `GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID` está seteado).
2. **Ruta en estado `draft` con 5-10 paradas** cuyos clientes tienen `lat`/`lng`.
   - El seed demo genera rutas draft para hoy si existe un plan locked.
   - Si no hay paradas: usar `POST /routes/plan` desde el dispatcher con
     pedidos en estado `planned`.
3. **Service account configurada** con permiso IAM `routeoptimization.locations.use`
   sobre el proyecto `samurai-system`.

### Descubrir rutas disponibles

```bash
SMOKE_LIST_ROUTES=1 python backend/scripts/smoke_google_optimization.py
```

---

## Ejecución del test

```bash
export CORTECERO_ROUTE_ID=<uuid>
python backend/scripts/smoke_google_optimization.py
```

El script ejecuta en orden:

1. `POST /auth/login` → obtiene token logistics
2. `GET /routes/{route_id}` → captura estado PRE (status, paradas, secuencias)
3. `POST /routes/{route_id}/optimize` → llama al proveedor Google real
4. Verifica todos los campos y genera informe de evidencia

---

## Criterios de verificación (todos deben pasar)

| # | Verificación | Esperado |
|---|---|---|
| V1 | HTTP status | 200 |
| V2 | `route.status` | `planned` (era `draft`) |
| V3 | `optimization_request_id` | no vacío |
| V4 | `optimization_response_json.provider` | `"google"` |
| V5 | `estimated_arrival_at` en todos los stops | no nulo |
| V6 | Secuencia de stops | cambia respecto al pre |
| V7 | Fallback mock intacto | `GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID=""` → `MockProvider` sin error |

---

## Ruta/plan probado

*(completar tras ejecución)*

| Campo | Valor |
|---|---|
| Route ID | `[PENDIENTE]` |
| Fecha de servicio | `[PENDIENTE]` |
| N.º de paradas | `[PENDIENTE]` |
| N.º de vehículos | 1 (provider actual usa 1 vehículo por ruta) |
| Coordenadas depot | 39.5696, 2.6502 (Palma de Mallorca — config) |

---

## Resultado del optimize real

*(completar tras ejecución)*

```
[PENDIENTE — pegar salida del script aquí]
```

---

## Evidencia

*(completar tras ejecución)*

| Campo | Valor |
|---|---|
| Tiempo elapsed | `[PENDIENTE]` |
| `optimization_request_id` | `[PENDIENTE]` |
| Paradas reordenadas | `[PENDIENTE]` |
| `totalDuration` (Google) | `[PENDIENTE]` |
| `routeDistanceMeters` | `[PENDIENTE]` |
| Coste/cuota observada | `[PENDIENTE — verificar GCP Console]` |

---

## Incidencias

*(completar tras ejecución)*

Ninguna / [descripción si las hay]

---

## Verificación de fallback mock (V7)

```bash
# Con GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID vacío → debe usar MockProvider
GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID="" \
CORTECERO_ROUTE_ID=<uuid-ruta-draft-fresca> \
python backend/scripts/smoke_google_optimization.py
```

Esperado: el optimize completa sin error, `provider` no es `"google"` en
`optimization_response_json` (o el campo no existe — comportamiento del mock).

---

## Estado final

**[ ] GO** — todos los criterios V1–V7 satisfechos
**[ ] NO-GO** — uno o más criterios fallaron (ver Incidencias)

---

## Fuera de alcance

- No se toca frontend
- No se toca OpenAPI
- No se abre otro bloque técnico
- No se meten datos reales en el repo
- No se hace refactor del provider
