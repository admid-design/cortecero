# R9 Backlog — CorteCero

> Fase: R9 — HARDENING / PRE-PROD  
> Principio rector: estabilizar runtime, contratos y rendimiento antes de seguir montando UI.  
> Última actualización: 2026-04-19

---

## Orden de bloques

| Prioridad | ID | Bloque | Estado |
|-----------|-----|--------|--------|
| 1 | R9-HARDENING-001 | Runtime/deploy safety + envs + api.ts + CI frontend | **ABIERTO** |
| 2 | R9-PERF-001 | Eliminar N+1 en optimize / dispatch / plan_routes | PENDIENTE |
| 3 | R9-CONTRACT-001 | OpenAPI ↔ runtime alineados + catálogo de errores cerrado | PENDIENTE |
| 4 | R9-MONITOR-UX-001 | Delay alerts visibles en panel/drawer + fixes monitor mode | PENDIENTE |
| 5 | MONITOR-MODE-002 | Chat flotante dispatcher↔conductor (CHAT-001 UI) | PENDIENTE |
| 6 | R9-REALTIME-001 | SSE Redis / pub-sub compartido (multi-worker) | PENDIENTE — condicional a decisión de infra |

**Regla:** no abrir bloque N+1 sin bloque N en CERRADO o PROMULGADO.

---

## R9-HARDENING-001 — Runtime / Deploy / api.ts / CI frontend

**Tipo:** HARDENING  
**Estado:** ABIERTO  
**Objetivo:** dejar el stack libre de fragilidades silenciosas antes de seguir construyendo

### Alcance

#### 1. Runtime / deploy safety

- Verificar que el cold start Vercel (lifespan FastAPI → `seed()`) no produce errores silenciosos en Neon
- Confirmar que `CORTECERO_STARTUP_SEED=false` no bloquea arranque limpio en ningún escenario
- Revisar que variables de entorno críticas (`DATABASE_URL`, `JWT_SECRET_KEY`, `CORS_ORIGINS`) estén completas en ambos proyectos Vercel (`cortecero` y `cortecero-api`)
- Validar que el guard JWT-en-lifespan (HARDENING-SEC-001) no produce falsos positivos en Vercel

#### 2. Revisión de envs / secrets

- Auditar `frontend/.env.local` y `backend/.env` contra variables declaradas en Vercel
- Confirmar que ningún secret está en el repo (grep sobre historial si hay duda)
- Verificar que `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` está correctamente restringida por dominio en Google Cloud Console
- Confirmar que `GOOGLE_APPLICATION_CREDENTIALS` no referencia path local que no exista en Vercel (backend serverless no tiene filesystem persistente)

#### 3. `frontend/lib/api.ts` — robustez ante red y respuestas no-JSON

- Auditar todos los `request()` calls: ¿qué ocurre si el backend devuelve `204 No Content`?
- Añadir manejo explícito de `204`/`205` (respuestas sin body) donde aplique
- Añadir timeout o error boundary ante red caída (hoy: Promise que nunca resuelve)
- Verificar que errores `{ detail: { code, message } }` se propagan correctamente al UI (no se tragan silenciosamente)

#### 4. CI frontend — tests reales

- `frontend-smoke` en CI hoy solo valida `npm run build`, no ejecuta `npm test`
- Activar `npm test` (vitest) en el workflow de CI
- Verificar que los 26 tests de componentes pasan en CI sin API key real
- Si algún test requiere variables de entorno, añadir secrets en GitHub Actions

### Definition of Done

- [ ] Cold start Vercel sin errores en Neon (smoke post-deploy)
- [ ] Envs auditados: ningún drift entre local, repo y Vercel
- [ ] `api.ts`: `204`/`205` manejados; timeout explícito; errores backend propagados
- [ ] CI: `npm test` ejecuta y pasa en `frontend-smoke` workflow
- [ ] Sin secrets en repo (git log auditado)

---

## R9-PERF-001 — N+1 en routing

**Tipo:** HARDENING  
**Estado:** PENDIENTE  
**Objetivo:** eliminar queries redundantes en los endpoints de mayor carga operativa

### Alcance conocido

- `POST /routes/{id}/optimize` — carga paradas + clientes en loop
- `POST /routes/{id}/dispatch` — carga órdenes individualmente al construir stops
- `POST /routes/plan` — potencial N+1 al asignar pedidos a plan

### Approach esperado

- Eager loading con SQLAlchemy `selectinload` / `joinedload` donde aplique
- Medir antes/después con `EXPLAIN ANALYZE` en Neon si el volumen lo justifica

---

## R9-CONTRACT-001 — OpenAPI ↔ runtime + catálogo de errores

**Tipo:** HARDENING / DOCS  
**Estado:** PENDIENTE  
**Objetivo:** cerrar contrato antes de seguir montando UI encima

### Alcance

- Auditar `openapi/openapi-v1.yaml` contra todos los routers: paths, métodos, schemas de request/response
- Verificar que todos los códigos de error del catálogo (`docs/contracts/error-contract.md`) tienen correspondencia en OpenAPI
- Cerrar divergencias: si el runtime devuelve algo distinto al spec, spec → runtime (no al revés)

---

## R9-MONITOR-UX-001 — Delay alerts visibles + fixes monitor mode

**Tipo:** IMPLEMENTATION  
**Estado:** PENDIENTE  
**Objetivo:** surfacear en UI lo que el backend ya calcula

### Alcance

- `GET /routes/{id}/delay-alerts` → mostrar alertas de retraso en drawer de OpsMapDashboard
- Indicador visual en chip flotante si la ruta tiene ≥1 alerta activa
- Fixes que emerjan del uso real del monitor mode en demo

---

## MONITOR-MODE-002 — Chat flotante dispatcher↔conductor

**Tipo:** IMPLEMENTATION  
**Estado:** PENDIENTE  
**Prerequisito:** R9-HARDENING-001 + R9-CONTRACT-001 cerrados  
**Objetivo:** UI sobre CHAT-001 (endpoints ya operativos)

### Alcance

- Widget flotante bottom-right en OpsMapDashboard
- Tabs por conductor activo
- Conectado a `GET/POST /routes/{id}/messages`
- SSE event `chat_message` para push en tiempo real

---

## R9-REALTIME-001 — SSE Redis / pub-sub multi-worker

**Tipo:** HARDENING / INFRA  
**Estado:** PENDIENTE — condicional  
**Prerequisito:** decisión de migrar a gunicorn multi-worker o escalar Vercel con múltiples instancias  
**Objetivo:** hacer SSE compatible con arquitectura multi-worker

### Contexto

Hoy: `RouteEventBus` usa `asyncio.Queue` in-process. Un evento publicado en worker A no llega a cliente conectado a worker B.  
Fix: Redis pub/sub como bus compartido entre workers.  
**No es urgente mientras Vercel use una sola instancia serverless por request.**

---

## Congelado / fuera de scope R9

| Ítem | Motivo |
|------|--------|
| AI assistant | Sin scope técnico definido |
| ERP/CRM integration | Decisión comercial pendiente |
| Fleet view avanzada (clusters, filtros) | R8 cubre el caso demo |
| Reoptimización automática | Trigger manual cubre el caso real |
| POD R2 real | Deuda viva R8 — entra cuando lleguen credenciales, no como bloque R9 |
| Notificaciones D1 | Condicional a decisión de proveedor email/SMS |
