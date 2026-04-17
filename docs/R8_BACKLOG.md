# R8 Backlog — CorteCero

> Fase activa: R8 — Mapas, Realtime y Operaciones avanzadas  
> Última actualización: 2026-04-17

---

## Estado de bloques

| ID | Bloque | Estado | Tests | Commit |
|----|--------|--------|-------|--------|
| R8-A-GPS | GPS-001 backend — `POST /driver/location`, `GET /routes/{id}/driver-position`, `GET /driver/active-positions` | VERIFICADO LOCAL | test_routing_gps_a3.py (✓) | `d1e0ff8` (fix `62cdb79`) |
| R8-A-POD | POD-001 backend — `POST /stops/{id}/proof`, `GET /stops/{id}/proof`, migration stop_proofs | VERIFICADO LOCAL | test_routing_proof_a2.py (✓) | `d1e0ff8` (fix `62cdb79`) |
| R8-A-MAP-BE | MAP-001 backend — `route_geometry` derivada de `optimization_response_json` | VERIFICADO LOCAL | test_map_geom_001.py (✓) | `a8b9a0d` |
| R8-A-MAP-FE | MAP-001 frontend — `RouteMapCard.tsx` con Google Maps JS API, marcadores por estado, marcador conductor (polling 30s) | VERIFICADO LOCAL | evidence en browser con API key | `62cdb79` |
| R8-A-GPS-FE | GPS-001 frontend — hook `useGpsTracking` publica posición durante `in_progress` | VERIFICADO LOCAL | incluido en DriverRoutingCard | `62cdb79` |
| R8-A-POD-FE | POD-001 frontend — modal firma canvas en `DriverRoutingCard` | VERIFICADO LOCAL | incluido en DriverRoutingCard | `62cdb79` |
| R8-E2 | DEMO-OPT-001 — Google Route Optimization smoke 200 real | CERRADO_CON_EVIDENCIA_LOCAL | — | `3e39b16` (fix `59bd16d`) |
| R8-FLEET | FLEET-VIEW-001 — panel OpsMapDashboard con marcadores de flota | VERIFICADO LOCAL | build frontend limpio | `777a4d0` |
| R8-B1 | REALTIME-001 — SSE backend (`GET /routes/{id}/stream`), RouteEventBus, hooks en transiciones | VERIFICADO LOCAL | test_realtime_b1.py (7/7 ✓) | `8f35c01` |
| R8-B2 | ETA-001 — `POST /routes/{id}/recalculate-eta`, `GET /routes/{id}/delay-alerts`, haversine calculator, migration 022 | VERIFICADO LOCAL | test_eta_b2.py (15/15 ✓) | `3e5980d` |
| R8-B3 | CHAT-001 — `POST/GET /routes/{id}/messages`, tabla route_messages, SSE event chat_message, migration 026 | VERIFICADO LOCAL | test_chat_b3.py (9/9 ✓) | `3e5980d` |
| R8-B4 | LIVE-EDIT-001 — `add-stop`, `remove-stop`, `move-stop` extendido a in_progress, SSE events | VERIFICADO LOCAL | test_live_edit_b4.py (11/11 ✓) | `3e5980d` |
| R8-C1 | RETURN-001 — `POST /orders/{id}/return-to-planning`, failed_delivery → ready_for_planning | VERIFICADO LOCAL | test_return_c1.py (7/7 ✓) | `3e5980d` |
| R8-F1 | TW-001 — Time windows por cliente en optimizer (`window_start/end` → `timeWindows` Google) | VERIFICADO LOCAL | test_tw_f1.py (14/14 ✓) | `3e5980d` |
| R8-F2 | CAPACITY-001 — Capacidad de vehículo en optimizer (`capacity_kg` → `loadLimits` Google) | VERIFICADO LOCAL | test_capacity_f2.py (13/13 ✓) | `3e5980d` |
| R8-F4 | DOUBLE-TRIP-001 — `Route.trip_number` + `startTimeWindows` para viaje 2, migration 023 | VERIFICADO LOCAL | test_double_trip_f4.py (8/8 ✓) | `3e5980d` |
| R8-F5 | ADR-001 — `Vehicle.is_adr_certified` + `Order.requires_adr` + validación pre-optimize, migration 024 | VERIFICADO LOCAL | test_adr_f5.py (8/8 ✓) | `3e5980d` |
| R8-F6 | ZBE-001 — `Customer.in_zbe_zone` + `Vehicle.is_zbe_allowed` + validación pre-optimize, migration 025 | VERIFICADO LOCAL | test_zbe_f6.py (8/8 ✓) | `3e5980d` |
| R8-SMOKE | Dataset geo-ready + smoke Google Route Optimization 200 real | CERRADO_CON_EVIDENCIA_LOCAL | — | `3e39b16` |

---

## Pendiente activo

### ~~R8-SMOKE — Google smoke dataset~~ — CERRADO_CON_EVIDENCIA_LOCAL
- Evidence en `docs/evidence/DEMO-OPT-001.json` — HTTP 200, provider=google, 2 paradas, ETAs reales
- Smoke reproducible con `CORTECERO_ROUTE_ID` + `GOOGLE_APPLICATION_CREDENTIALS` + `GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID=samurai-system`
- Commits: `59bd16d` (fix timestamps/skippedShipments) + `3e39b16` (cierre documentado) + `641c73a` (seed geo Mallorca)

### R8-SSE-FE — SSE frontend
- **Objetivo**: Conectar `GET /routes/{id}/stream` en frontend para reemplazar polling 30s en `RouteMapCard` y `DriverRoutingCard`
- **Alcance**:
  - Hook `useRouteStream` en frontend que consume SSE
  - Reemplaza `setInterval` de 30s por actualizaciones push
  - Manejo de reconexión y fallback a polling si SSE cae
- **Limitación conocida**: SSE backend usa asyncio.Queue in-process (no multi-worker). Fix futuro: Redis pub/sub.
- **Cierre**: evidence en browser con ruta in_progress actualizándose sin polling

### R8-POD-FOTO — Proof of delivery: foto
- **Objetivo**: Input de cámara en `DriverRoutingCard` para adjuntar foto a entrega
- **Alcance**:
  - `<input type="file" accept="image/*" capture="environment">` o API Camera
  - Upload a backend (storage TBD: base64 en DB o presigned URL)
  - Schema `stop_proofs` ya preparado con campo `photo_url`
- **Bloqueado por**: decisión de storage (DB blob vs. S3/presigned)
- **Cierre**: evidence en dispositivo real o emulado

---

## Congelado / fuera de scope R8

| Ítem | Motivo |
|------|--------|
| D1 — Notificaciones push/email a cliente | Pendiente decisión de proveedor email/SMS |
| SSE multi-worker con Redis | Complejidad infra — pospuesto a R9 |
| Reoptimización automática ante incidencias | Trigger manual existe; flujo automático no prioritario |
| Notificación de ETA a cliente final | Depende de D1 |
| Fleet view detallado (cluster, filtros, tiempo real) | Solo marcadores básicos en R8 |
| ERP/CRM integration | DECISION-ERP-SALES-001 — fuera de scope |
| Asistente IA | No existe en ninguna capa |

---

## Definition of Done R8

- CI verde en todos los commits (backend-tests + openapi-check + frontend-smoke)
- DEMO-OPT-001 smoke reproducible con dataset geo-ready
- SSE frontend reemplazando polling en al menos un componente
- POD foto con decisión de storage y evidence en device
- `docs/as-is.md` y `openapi/openapi-v1.yaml` alineados con runtime
- R1–R7 sin degradación semántica (283+ tests en verde)

---

## Orden recomendado

1. CI verde `3e5980d` (bloqueante)
2. R8-SMOKE — Google smoke dataset
3. R8-SSE-FE — SSE frontend
4. R8-POD-FOTO — POD foto (si storage decidido)
5. D1 — Notificaciones (si proveedor decidido)
