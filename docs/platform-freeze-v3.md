# CorteCero — Plan de congelación por capas v3

> **Fecha**: 2026-04-16
> **Base**: `platform-analysis-v2.md`
> **Propósito**: decisión operativa — qué congelar, qué no, en qué orden, qué no mezclar.

---

## Qué significa "congelado" aquí

Una capa está **congelada** cuando:
- Su contrato (endpoints, schemas, comportamiento) no va a cambiar en el siguiente bloque
- Sus tests están en verde en HEAD actual (no en un CI histórico)
- No tiene dependencias abiertas que puedan forzar un cambio regresivo

Congelar no significa "no tocar nunca". Significa que el siguiente bloque puede asumir que esa capa es estable sin necesidad de revisarla.

---

## Nota sobre HEAD CI

El último CI verde confirmado externamente corresponde a la salida del bloque SEC-DATA-001 (antes de E.2 y R8 Phase A).
Los commits de E.2 y R8 Phase A fueron hechos fuera de sesión. Su CI en HEAD no está externamente confirmado.

**Consecuencia para la clasificación:**
- Los bloques confirmados como CI verde antes de E.2/R8 → se mantienen en `PROMULGADO`
- Los bloques de E.2 y R8 que tienen tests pero sin confirmación de CI en HEAD → bajan a `VERIFICADO LOCAL` hasta que CI en HEAD sea visible

---

## 1. Capas que pueden congelarse ya

Estas capas tienen contrato estable, tests en CI verde histórico confirmado, y ningún bloque abierto que fuerce cambios en ellas.

| Capa | Condición de congelación |
|------|--------------------------|
| Operaciones core (órdenes, planes, colas, dashboard, admin, audit) | Ya congelada. Contrato estable. Sin dependencias abiertas. |
| Auth JWT / RBAC / multi-tenant | Ya congelada. Sin dependencias abiertas. |
| Routing: flujo dispatcher (Bloques B/C) | Ya congelada. Ningún bloque abierto toca estos endpoints. |
| Routing: ejecución conductor (Bloque D, sin GPS/POD) | Ya congelada. GPS y POD son capas separadas que no modifican arrive/complete/fail/skip. |
| Routing E.1: mock optimize | Ya congelada. El contrato del endpoint `POST /routes/{id}/optimize` está fijo. E.2 no lo modifica, solo cambia el provider interno. |
| DB migrations 001–019 | Ya congeladas. No tocar migrations históricas. |

**Una condición para todas**: confirmar CI verde en HEAD actual antes de declarar cualquiera como congelada formalmente. El congelamiento es provisional hasta ese check.

---

## 2. Capas que NO pueden congelarse todavía

### 2a. E.2 — Google real provider

**Razón**: sin smoke 200 real. El código existe (`google_provider.py`, 7.2 KB), los unit tests pasan con monkeypatch, pero ningún request ha llegado al endpoint real de Google.

**Prerrequisito bloqueante**: dataset geo-ready en tenant demo (`prepare_google_smoke_dataset.py`).

**No congelar hasta**: smoke con `SMOKE_CREATE_ROUTE=1` devuelve 200 y rutas con ETAs calculadas.

---

### 2b. R8 GPS-001 backend

**Razón**: CI en HEAD no confirmado externamente. Los 10 tests en `test_routing_gps_a3.py` son DB-only pero no hay constancia de que pasen en el CI del HEAD actual.

**No congelar hasta**: CI backend-tests verde con `test_routing_gps_a3.py` incluido.

---

### 2c. R8 POD-001 backend

**Razón**: igual que GPS-001. 9 tests en `test_routing_proof_a2.py`, CI en HEAD no confirmado.

**No congelar hasta**: CI backend-tests verde con `test_routing_proof_a2.py` incluido.

---

### 2d. R8 MAP-001 backend (geometría)

**Razón**: 2 tests en `test_map_geom_001.py`, CI en HEAD no confirmado. Además, la geometría depende de que `optimization_response_json` tenga el campo `routes[].transitions[].routePolyline`, lo que requiere smoke E.2 real para validarse end-to-end.

**No congelar hasta**: CI verde + E.2 smoke (que valida que Google devuelve polylines reales).

**Dependencia explícita**: MAP-001 backend geometry no está completamente verificado sin E.2 smoke.

---

### 2e. R8 MAP-001 frontend (`RouteMapCard`)

**Razón**: código presente pero sin evidencia de render real. Requiere `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` en entorno.

**No congelar hasta**: render real verificado con API key. Sin test de componente.

**Alerta**: `RouteMapCard` es la única pieza del frontend que tiene dependencia de infraestructura externa (Google Maps JS API). Si la key no está en entorno, el componente no renderiza y el frontend build pasa igualmente — el CI no lo detecta.

---

### 2f. R8 GPS-001 frontend (hook GPS + marcador en mapa)

**Razón**: hook implementado en `DriverRoutingCard`, sin smoke en dispositivo real con GPS activo. El CI frontend-smoke valida el build pero no la interacción con el GPS del dispositivo.

**No congelar hasta**: evidencia en dispositivo real (o emulado) con `POST /driver/location` llegando al backend.

---

### 2g. R8 POD-001 frontend (firma canvas)

**Razón**: modal de firma implementado en `DriverRoutingCard`, sin smoke en dispositivo. El canvas de firma requiere interacción táctil real para validarse.

**No congelar hasta**: smoke en dispositivo (o emulado con mouse) con `POST /stops/{id}/proof` llegando al backend y `StopProof` persisted en DB.

---

### 2h. Frontend: 9 componentes sin test

Afecta a: `RouteMapCard`, `RouteDetailCard`, `RoutingSidePanels`, `DispatcherRoutingShell`, `AdminShell`, `AdminCustomersSection`, `AdminZonesSection`, `AppShell`, `KpiRow`.

**Razón**: no hay test de componente. El build verde solo confirma que TypeScript compila — no comportamiento.

**No congelar hasta**: al menos un test de comportamiento por componente.

**Riesgo específico por componente**:
- `RouteMapCard`: dependencia externa (API key) + sin test → riesgo máximo
- `RoutingSidePanels` / `DispatcherRoutingShell`: modularizaciones de refactor — tests ausentes significan que la UI puede silenciosamente romperse
- `AdminShell` / `AppShell`: layouts globales — sin test significa que cambios de shell pueden romper toda la superficie sin señal

---

## 3. Dependencias entre capas

```
DB migrations 020+021
    └─► GPS-001 backend
    └─► POD-001 backend

E.1 mock optimize (congelado)
    └─► E.2 Google provider (depende de E.1 contrato, no de su implementación)
            └─► MAP-001 backend geometry (necesita polylines reales de Google)
                    └─► MAP-001 frontend render (necesita geometría + API key)

GPS-001 backend
    └─► GPS-001 frontend hook (necesita endpoints listos)
            └─► Marcador conductor en mapa (necesita GPS-001 frontend + MAP-001 frontend)

POD-001 backend
    └─► POD-001 frontend canvas (necesita endpoints listos)

GPS-001 backend + MAP-001 backend
    └─► Fleet view UI (necesita ambos congelados + UI nueva)
```

**Bloqueos críticos en cadena**:
- E.2 smoke bloquea → MAP-001 geometry verification completa
- MAP-001 frontend bloquea → Fleet view UI
- Si se trabaja en Fleet view sin MAP-001 congelado → retrabajo garantizado

---

## 4. Orden recomendado de cierre

### Paso 1 — Confirmar CI en HEAD (prerequisito de todo lo demás)

Ejecutar `docker compose run --rm backend pytest -q` en HEAD actual y confirmar que todos los tests de R8 pasan. Esto sube GPS-001, POD-001 y MAP-001 de `VERIFICADO LOCAL` a `PROMULGADO`.

Un comando, un resultado. Sin esto, el resto del orden es especulativo.

### Paso 2 — Cerrar E.2 smoke (DEMO-OPT-001)

Prerrequisito: dataset geo-ready.

```bash
python3 backend/scripts/prepare_google_smoke_dataset.py
SMOKE_CREATE_ROUTE=1 \
GOOGLE_APPLICATION_CREDENTIALS=~/.config/kelko/google/route-optimization-sa.json \
GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID=samurai-system \
python3 backend/scripts/smoke_google_optimization.py
```

Output esperado: respuesta 200 con ETAs calculadas. Esto cierra DEMO-OPT-001 y permite que MAP-001 geometry sea considerada verificada end-to-end.

### Paso 3 — Frontend: tests de los 9 componentes sin cobertura

Prioridad:
1. `RouteMapCard` — riesgo máximo, dependencia externa
2. `RoutingSidePanels` / `DispatcherRoutingShell` — modularizaciones frágiles
3. `RouteDetailCard` — componente operativo usado activamente
4. El resto (`AdminShell`, `AppShell`, `KpiRow`, `AdminCustomersSection`, `AdminZonesSection`)

### Paso 4 — MAP-001 frontend smoke

Requiere: `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` configurada + ruta `in_progress` en el seed.
Evidencia esperada: mapa renderizado en browser con marcadores de paradas y marcador de conductor visible.

### Paso 5 — GPS-001 + POD-001 frontend smoke

Requiere: dispositivo real o emulado. Evidencia:
- GPS: `POST /driver/location` en backend con coordenadas reales
- POD: `POST /stops/{id}/proof` con firma canvas capturada

---

## 5. Qué no mezclar en paralelo

| Combinación | Por qué no mezclar |
|-------------|-------------------|
| E.2 smoke + Frontend tests | Son cadenas de dependencia independientes. Mezclarlas genera contexto bifurcado sin cierre claro. |
| Fleet view UI + MAP-001 sin congelar | Fleet view requiere MAP-001 estable. Abrirlo antes garantiza retrabajo. |
| Nuevo bloque R8 Phase B + R8 Phase A sin PROMULGADO | Phase A tiene que tener CI verde antes de abrir Phase B. |
| GPS-001 frontend + POD-001 frontend | Se pueden hacer secuencialmente sin problema, pero no en el mismo commit si comparten `DriverRoutingCard` — los cambios se solaparán en el mismo archivo. |
| Docs update + código R8 | Los docs deben actualizarse DESPUÉS de que los cambios de código tienen CI verde, no antes. Si se actualizan antes, `as-is.md` vuelve a ser aspiracional. |

---

## 6. Una alerta sobre `as-is.md`

El documento `docs/as-is.md` describe un estado anterior al actual. Tiene drift en al menos:
- No menciona `google_provider.py` (E.2)
- No menciona `test_routing_gps_a3.py`, `test_routing_proof_a2.py`, `test_map_geom_001.py`
- OpenAPI en 1.5.2 vs lo que describe
- R8 Phase A marcada como "PARCIAL — pendiente docker tests" cuando ya tiene tests escritos

**Recomendación**: actualizar `as-is.md` en un bloque DOCS separado, después del Paso 1 (CI en HEAD confirmado). No antes — si hay tests rotos, `as-is.md` tiene que reflejar eso, no el estado deseado.

---

## Resumen ejecutivo

| Capa | ¿Congelar ya? | Bloqueante si no |
|------|--------------|-----------------|
| Operaciones core, Auth, Admin | Sí (condición: CI HEAD) | — |
| Routing B/C/D (sin GPS/POD) | Sí (condición: CI HEAD) | — |
| E.1 mock optimize | Sí (condición: CI HEAD) | — |
| E.2 Google provider | No | Dataset geo-ready |
| R8 GPS-001 backend | No | CI HEAD confirmado |
| R8 POD-001 backend | No | CI HEAD confirmado |
| R8 MAP-001 backend | No | CI HEAD + E.2 smoke |
| R8 MAP-001 frontend | No | API key + smoke render |
| R8 GPS-001 frontend | No | Dispositivo real/emulado |
| R8 POD-001 frontend | No | Dispositivo real/emulado |
| Frontend: 9 sin test | No | Tests de componente |

**Única acción de mayor leverage ahora**: `docker compose run --rm backend pytest -q` en HEAD. Un comando que resuelve la ambigüedad de CI para todo R8 y permite congelar o diagnosticar en un solo paso.
