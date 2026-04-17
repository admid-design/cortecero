# GMP-2 — Definición exacta de "mapa cerrado"
> Fecha: 2026-04-16
> Propósito: congelar el alcance de "mapa cerrado" con precisión suficiente para que ningún agente
> derive scope sin instrucción explícita.
> Estado de la fase: única prioridad activa. Todo lo demás (ERP, sales view, notificaciones,
> fases B-G de R8) está congelado hasta que este bloque quede en CERRADO_CON_EVIDENCIA_LOCAL.

---

## Qué significa "mapa cerrado"

Mapa cerrado = el dispatcher abre una ruta optimizada con Google, ve el recorrido real del conductor
dibujado en el mapa como polyline decodificada de Google, y esa línea viene del campo
`route_geometry` generado por `_extract_route_geometry()` a partir de la respuesta real de
Google Route Optimization API. No de puntos conectados manualmente entre paradas.

---

## Condiciones de cierre — las cuatro y solo las cuatro

### 1. Backend: `route_geometry` expuesta en el endpoint de detalle de ruta

`GET /routes/{routeId}` (o `GET /routes/{routeId}/map-data`) devuelve un campo `route_geometry`
con el encoded polyline concatenado de `transitions[*].routePolyline.points`.

`_extract_route_geometry()` ya existe en `routing.py`. La condición es que ese campo llegue al
frontend en la respuesta del endpoint de lectura de la ruta — no solo que exista internamente.

Verificación: `curl /routes/{id}` devuelve `route_geometry` con string no vacío después de optimize.

### 2. Backend: evidencia de que Google devuelve `routePolyline` en la respuesta real

La evidencia de DEMO-OPT-001 (`docs/evidence/DEMO-OPT-001.json`) contiene ETAs pero no tiene
`routes[0].transitions[*].routePolyline.points`. Hay que confirmar que la API de Google devuelve
ese campo con el request actual.

Si no lo devuelve: hay que ajustar el request en `google_provider.py` para solicitar geometría
codificada. El campo exacto se determina inspeccionando la respuesta real y la documentación del
endpoint — no se prescribe aquí.

Verificación: un JSON de respuesta real de Google con `routePolyline.points` no vacío, guardado
en `docs/evidence/GMP-2-google-raw.json`.

### 3. Frontend: RouteMapCard renderiza el polyline decodificado

`RouteMapCard.tsx` usa `google.maps.geometry.encoding.decodePath(route_geometry)` para trazar la
línea real en el mapa, no conecta los marcadores de paradas con líneas rectas entre lat/lng.

Si actualmente conecta puntos manualmente: se cambia para usar el encoded polyline del backend.
Si actualmente no traza ninguna línea: se añade el `google.maps.Polyline` con los puntos decodificados.

Verificación: screenshot del mapa en browser mostrando la línea de ruta real, no recta entre paradas.

### 4. Evidence green: archivo documentado

`docs/evidence/GMP-2-evidence.md` con:
- Screenshot del mapa con polyline real visible
- Hash del commit que implementa el cambio
- URL del request que produce la geometría
- Primeros 50 caracteres del encoded polyline recibido de Google (confirma que no es mock)

---

## Scope estricto — qué NO entra en este bloque

- Fleet view (múltiples rutas en el mapa simultáneamente) — F3, no GMP-2
- Marcador conductor en tiempo real (SSE push) — B1 ya está PROMULGADO, la integración frontend SSE va después
- ETA dinámica en el mapa — B2, no GMP-2
- Foto del albarán — POD-001 ya está verificado local; no tocar
- Cualquier migración de DB — GMP-2 no requiere cambios de schema
- Cualquier endpoint nuevo no relacionado con la geometría de la ruta
- Tests de componentes de los 9 sin cobertura — son deuda real pero no bloquean GMP-2
- Migración de `google.maps.Marker` a `AdvancedMarkerElement` — mejora válida, bloque posterior

Si durante GMP-2 aparece un bug en otra área: se documenta, no se arregla.

---

## Prerequisitos que deben estar resueltos antes de empezar

| Prerequisito | Estado |
|---|---|
| `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` configurada en entorno local | Debe verificarse |
| `GOOGLE_APPLICATION_CREDENTIALS` y `GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID` disponibles | Ya disponibles (usados en DEMO-OPT-001) |
| Ruta con paradas en estado `in_progress` en el tenant demo | Debe existir o crearse con smoke |
| `DEMO-OPT-001` ejecutado (ruta optimizada con respuesta 200 de Google) | CERRADO_CON_EVIDENCIA_LOCAL |

---

## Estado real del pipeline (post-inspect 2026-04-16)

El inspect de los cuatro archivos relevantes confirma que el pipeline completo ya está implementado:

| Pieza | Archivo | Estado |
|---|---|---|
| `populateTransitionPolylines: True` en request body | `google_provider.py` L122 | IMPLEMENTADO |
| `_extract_route_geometry()` extrae y expone polylines | `routing.py` | IMPLEMENTADO |
| `RouteGeometryOut` schema con `transition_polylines` | `schemas.py` | IMPLEMENTADO |
| `RoutingRouteGeometry` tipo en frontend | `api.ts` L289-293 | IMPLEMENTADO |
| `decodeGoogleEncodedPolyline()` y render condicional | `RouteMapCard.tsx` L40-264 | IMPLEMENTADO |
| Pill `"geometría vial: disponible"` vs `"fallback: recto"` | `RouteMapCard.tsx` L345 | IMPLEMENTADO |

**GMP-2 NO es un bloque de implementación. Es un bloque de smoke y evidencia.**

El único desconocido empírico: ¿el response real de Google incluye `routePolyline.points` en
`transitions[*]`? DEMO-OPT-001.json capturó solo el resultado procesado (ETAs). La geometría no
fue guardada en el archivo de evidencia.

## Secuencia de trabajo reducida

```
1. Levantar el stack: docker compose up -d

2. Ejecutar smoke con Google real:
   SMOKE_CREATE_ROUTE=1 \
   GOOGLE_APPLICATION_CREDENTIALS=~/.config/kelko/google/route-optimization-sa.json \
   GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID=samurai-system \
   python3 backend/scripts/smoke_google_optimization.py

3. Obtener el route_id de la ruta optimizada y llamar:
   curl -H "Authorization: Bearer <token>" http://localhost:8000/routes/{id}
   → inspeccionar route_geometry.transition_polylines
   → si el array tiene strings no vacíos → todo el pipeline funciona

4. Si transition_polylines está vacío o null:
   → el raw response de Google no incluye routePolyline → ajustar el request
   → re-ejecutar smoke

5. Si transition_polylines tiene strings → abrir browser en localhost:3000
   → abrir la ruta en el panel dispatcher → ver RouteMapCard
   → confirmar pill "geometría vial: disponible" y línea azul sobre carreteras reales

6. Guardar docs/evidence/GMP-2-evidence.md con:
   - Screenshot del mapa
   - Primeros 50 chars del primer encoded polyline (confirma dato real de Google)
   - route_id y commit
```

---

## Definition of done formal

```
Bloque: GMP-2
Tipo: DEMO
Objetivo: evidencia real de route_geometry con polylines de Google renderizados en mapa dispatcher
Evidence green: sí — screenshot + JSON con encoded polyline no vacío de respuesta Google real
Estado final válido: CERRADO_CON_EVIDENCIA_LOCAL
```

El bloque NO puede cerrarse con:
- Solo test green sin screenshot real
- Polyline mockeada o sintética
- "El mapa renderiza" sin confirmar que la línea viene de Google y no de coordenadas conectadas

---

## Qué sigue después de GMP-2

Solo después de que GMP-2 esté en CERRADO_CON_EVIDENCIA_LOCAL:

1. Reabrir la discusión sobre qué bloque es el siguiente en el mapa (fleet view, SSE frontend, o ETA)
2. Evaluar si es el momento de trasladar GMP-2 a PROMULGADO con CI
3. Retomar DECISION-ERP-SALES-001 solo si el mapa está cerrado y hay capacidad real para abrir una
   nueva frente

Nada de esto se adelanta mientras GMP-2 esté abierto.
