# R9 Backlog — CorteCero

> Fase: R9 — HARDENING / PRE-PROD  
> Principio rector: estabilizar runtime, contratos y rendimiento antes de seguir montando UI.  
> Última actualización: 2026-04-20  
> **Estado de fase: R9 CERRADO** — `R9-REALTIME-001` diferido por decisión de arquitectura.

---

## Orden de bloques

| Prioridad | ID | Bloque | Estado |
|-----------|-----|--------|--------|
| 1 | R9-HARDENING-001 | Runtime/deploy safety + envs + api.ts + CI frontend | **PROMULGADO** |
| 2 | R9-PERF-001 | Eliminar N+1 en optimize / dispatch / list_routes | **PROMULGADO** |
| 3 | FIX-DEPLOY-001 | `functions`+`builds` conflict en `backend/vercel.json` | **PROMULGADO** |
| 4 | DRIVER-MOBILE-001 | Smoke móvil real: login conductor + GPS + flujo parada | **CERRADO_CON_EVIDENCIA_REAL** |
| 5 | R9-CONTRACT-001 | OpenAPI ↔ runtime alineados + catálogo de errores cerrado | PENDIENTE — próxima fase |
| 6 | R9-MONITOR-UX-001 | Delay alerts visibles en panel/drawer + fixes monitor mode | PENDIENTE — próxima fase |
| 7 | MONITOR-MODE-002 | Chat flotante dispatcher↔conductor (CHAT-001 UI) | PARCIAL — ver nota |
| 8 | R9-REALTIME-001 | SSE Redis / pub-sub compartido (multi-worker) | **CONGELADO** — decisión de arquitectura |

---

## Bloques cerrados en R9

### FIX-DEPLOY-001 — `backend/vercel.json` functions+builds conflict

**Tipo:** HARDENING  
**Estado:** PROMULGADO — commit `7a5e159` — 2026-04-20  
**Objetivo:** desbloquear todos los deploys del backend en Vercel

**Causa raíz:** `backend/vercel.json` tenía simultáneamente `"functions"` y `"builds"`. Vercel rechaza esta combinación. Todos los commits desde `dc65fd9` hasta `7a5e159` habían fallado silenciosamente — ningún deployment record se creaba en Vercel.

**Fix:** eliminar el bloque `"functions"` completo.

**Impacto desbloqueado:**
- Seed fix `f4cdd8f` (User sin campo `updated_at` inexistente) llegó a Neon
- Cuentas de conductores demo creadas en cold start
- Driver login operativo en móvil real

**Huecos:** `maxDuration` ya no está configurado. Si se necesita timeout extendido en Vercel Pro, usar `functions` key sin `builds`.

---

### DRIVER-MOBILE-001 — Smoke móvil real conductor

**Tipo:** DEMO  
**Estado:** CERRADO_CON_EVIDENCIA_REAL — 2026-04-20  
**Objetivo:** verificar flujo completo de conductor en dispositivo real

**Evidencia real (capturas en sesión):**
- Login `driver_a@demo.cortecero.app` / `driver123` en móvil: ✅
- Viewport / UX móvil usable: ✅
- GPS activado tras acción operativa ("Llegar"): ✅
- Posición real del dispositivo reflejada en mapa (marker conductor): ✅
- Transición de parada `Pendiente → Llegó`: ✅
- Acciones correctas post-arrive (`Completar` / `Falla` / `Omitir`): ✅
- `trayectoria vial real` activa (Google Route Optimization): ✅

**Observación menor:** botón "Omitir" visible en estado `arrived`. No invalida la evidencia. Ajuste cosmético para post-R9.

---

### R9-HARDENING-001 — Runtime / Deploy / api.ts / CI frontend

**Tipo:** HARDENING  
**Estado:** PROMULGADO — commits `099ec24` + `ed6cfbe` + `a5c3f27` — 2026-04-19

**Cerrado:**
- ✅ Envs auditados: drift resuelto entre local, repo y Vercel
- ✅ `api.ts`: `204`/`205` manejados; timeout explícito; errores backend propagados
- ✅ CI: `npm test` (vitest) activo en `frontend-smoke` workflow
- ✅ Cold start Vercel + seed() en Neon: sin errores (verificado vía FIX-DEPLOY-001)
- ✅ `STARTUP_SEED_RESET` env documentado y wired

---

### R9-PERF-001 — N+1 en routing

**Tipo:** HARDENING  
**Estado:** PROMULGADO — 2026-04-19

**Cerrado:**
- ✅ `_serialize_routes_batch`: 2 queries planas para `list_routes`
- ✅ `dispatch`: batch IN query para orders
- ✅ `optimize`: 3× batch pre-loop (orders + customers + profiles)

---

## MONITOR-MODE-002 — Chat flotante dispatcher↔conductor

**Tipo:** IMPLEMENTATION  
**Estado:** PARCIAL  
**Lado dispatcher (web):** OPERATIVO — `ChatFloating` montado en `OpsMapDashboard`, polling 10s, tabs por ruta activa, `GET/POST /routes/{id}/messages`  
**Lado conductor (móvil):** PENDIENTE — `DriverRoutingCard` no tiene UI de chat

**Criterio para "completo":** conductor puede leer y responder mensajes desde PWA móvil  
**Presentación correcta hoy:** "chat de monitor para dispatcher — canal conductor en móvil pendiente"  
**No presentar como:** "chat bidireccional completo dispatcher↔conductor"

---

## R9-REALTIME-001 — SSE Redis / pub-sub multi-worker

**Tipo:** HARDENING / INFRA  
**Estado:** CONGELADO — decisión de arquitectura pendiente

**Contexto:** `RouteEventBus` usa `asyncio.Queue` in-process. No escala con múltiples instancias serverless. Fix requiere Redis pub/sub. No urgente mientras Vercel sirva una instancia por request. Solo se activa cuando se decida entre Vercel Functions vs. servicio realtime dedicado (Railway, Fly.io, etc.).

**No bloquea R9 ni demo.**

---

## Diferido a próxima fase

| Ítem | Estado |
|------|--------|
| R9-CONTRACT-001 | OpenAPI ↔ runtime alineados + catálogo errores |
| R9-MONITOR-UX-001 | Delay alerts visibles en panel/drawer |
| MONITOR-MODE-002 conductor | Chat en DriverRoutingCard móvil |

---

## Congelado / fuera de scope R9

| Ítem | Motivo |
|------|--------|
| AI assistant | Sin scope técnico definido |
| ERP/CRM integration | Decisión comercial pendiente |
| Fleet view avanzada | R8 cubre el caso demo |
| Reoptimización automática | Trigger manual cubre el caso real |
| POD R2 real | Entra cuando lleguen credenciales, no como bloque R9 |
| Notificaciones D1 | Condicional a decisión de proveedor email/SMS |
