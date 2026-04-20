# R10 Backlog — CorteCero

> Fase: R10 — PLANIFICADOR + CONTRATOS + UX MONITOR
> Principio rector: completar el planificador semanal, cerrar contratos API y finalizar monitor mode.
> Última actualización: 2026-04-20

---

## Orden de bloques

| Prioridad | ID | Bloque | Estado |
|-----------|-----|--------|--------|
| 1 | ROUTE-PLANNER-TW-001 | `PATCH /stops/{stop_id}/scheduled-arrival` — backend + OpenAPI + api.ts | **PROMULGADO** |
| 2 | ROUTE-PLANNER-CAL-001 | Calendario semanal `RoutePlannerCalendar` v2 — KPI strip, gantt, drawer, TW-001-UI | **PROMULGADO** |
| 3 | TW-001-UI | Input inline `type="time"` en drawer del planificador (incluido en CAL-001 v2) | **PROMULGADO** |
| 4 | R9-CONTRACT-001 | OpenAPI ↔ runtime alineados + catálogo de errores cerrado | PENDIENTE |
| 5 | R9-MONITOR-UX-001 | Delay alerts visibles en panel/drawer + fixes monitor mode | PENDIENTE |
| 6 | MONITOR-MODE-002 | Chat flotante conductor en `DriverRoutingCard` (completa MONITOR-MODE-002) | PENDIENTE |

---

## Bloques cerrados en R10

### ROUTE-PLANNER-TW-001 — Edición hora prevista por parada

**Tipo:** IMPLEMENTATION
**Estado:** PROMULGADO — commit `7cf26e3` — 2026-04-20
**Objetivo:** Permitir al dispatcher editar `estimated_arrival_at` de una parada sin re-optimizar

**Cerrado:**
- ✅ `PATCH /stops/{stop_id}/scheduled-arrival` con guard multi-tenant + rechazo estados terminales
- ✅ Schema `RouteStopScheduledArrivalRequest` en `schemas.py`
- ✅ `openapi/openapi-v1.yaml` actualizado y validado (`openapi-spec-validator OK`)
- ✅ `patchStopScheduledArrival()` en `frontend/lib/api.ts`
- ✅ CI verde — 4 files, 98 insertions

**Huecos declarados:**
- UI inline en `RouteDetailCard.tsx` no implementada — el endpoint existe y está tipado, pero ningún componente lo llama todavía (→ TW-001-UI, bloque 3)
- No propaga el cambio al optimizador (es un override manual, por diseño)

---

### ROUTE-PLANNER-CAL-001 — Calendario semanal de planificación

**Tipo:** IMPLEMENTATION
**Estado:** CERRADO_LOCAL — commit `e8510d4` — 2026-04-20
**Objetivo:** Vista semanal para que el dispatcher asigne pedidos a rutas existentes

**Cerrado:**
- ✅ `frontend/components/RoutePlannerCalendar.tsx` — nuevo componente
  - Semana navegable (lun–dom), 7 columnas, salto prev/next/hoy
  - Sidebar con pedidos en estado `ready_for_planning` (fuente: `listReadyToDispatchOrders`)
  - Click pedido → seleccionado (banner de asignación); click ruta → `includeOrderInPlan(plan_id, orderId)`
  - Route cards por día con estado (color CSS var), nº paradas, barra de progreso para `in_progress`
  - Toast ok/err con auto-dismiss 4s
- ✅ `frontend/app/globals.css` — bloque `rpc-*` (180+ líneas de CSS)
- ✅ `frontend/components/OpsMapDashboard.tsx` — prop `onSwitchToPlanner` + nav item "📅 Planificador"
- ✅ `frontend/app/page.tsx` — `ViewMode` añade `"planner"`, bypass full-screen, `onSwitchToPlanner` wired
- ✅ `tsc --noEmit`: 0 errores

**Huecos declarados:**
- La spec original pedía: click en celda de día vacío → modal vehículo+conductor → `POST /routes/plan` (crear ruta nueva desde el calendario). Lo implementado: click en ruta existente → `includeOrderInPlan` (asignar pedido a ruta ya creada). Diferencia de alcance deliberada — el flujo de creación desde el calendario queda como extensión posible.
- Vercel pendiente de confirmar (push lo hace el usuario desde su terminal; `e8510d4` commit local)
- `npm run build` completo no corrió (timeout en sandbox); solo `tsc --noEmit`

---

## Definición de bloques pendientes

### TW-001-UI — Input inline hora prevista en RouteDetailCard

**Tipo:** IMPLEMENTATION
**Objetivo:** Conectar `patchStopScheduledArrival` con la UI de detalle de ruta

**Alcance:**
- En `RouteDetailCard.tsx` (o el componente que muestra la tabla de paradas del detalle), columna `Hora prevista`:
  - Mostrar `estimated_arrival_at` formateado como `HH:MM`
  - Al hacer click: se convierte en `<input type="time">`
  - Enter o blur: llama `patchStopScheduledArrival(token, stopId, isoValue)` → spinner → actualiza valor
  - Error inline si falla (no toast global)
- Solo editable si ruta NO está en `in_progress`, `completed`, `cancelled`

**Huecos predeclarados:** no re-optimiza; es override manual puntual.

---

### R9-CONTRACT-001 — Alineación OpenAPI ↔ runtime

**Tipo:** HARDENING
**Objetivo:** Que `openapi-v1.yaml` refleje exactamente el runtime actual, sin paths aspiracionales ni faltantes

**Alcance:**
- Auditar todos los paths de `backend/app/routers/` vs `openapi-v1.yaml`
- Añadir paths faltantes / eliminar paths aspiracionales
- Cerrar catálogo de errores: que todos los `4xx` usados en runtime tengan su `response` en el YAML
- `openapi-spec-validator` OK al finalizar
- `frontend/lib/api.ts` alineado si hay paths que difieren

---

### R9-MONITOR-UX-001 — Delay alerts visibles en panel

**Tipo:** IMPLEMENTATION
**Objetivo:** Que las alertas de retraso (`getDelayAlerts`) sean visibles en el drawer de ruta del monitor mode

**Alcance:**
- En `OpsMapDashboard`, el drawer de ruta activa muestra sección "Alertas de retraso" si `delayAlerts.length > 0`
- Pill/badge rojo en el chip de la ruta flotante si hay alertas activas
- No requiere endpoint nuevo — `delayAlerts` ya se carga en `page.tsx` vía `getDelayAlerts`

---

### MONITOR-MODE-002 — Chat conductor en DriverRoutingCard

**Tipo:** IMPLEMENTATION
**Objetivo:** Completar el chat bidireccional — lado conductor (móvil)

**Alcance:**
- En `DriverRoutingCard.tsx`: panel de chat flotante (o sección al pie) para la ruta activa
- Polling `GET /routes/{id}/messages` cada 10–15s durante `in_progress`
- Input de texto + botón enviar → `POST /routes/{id}/messages`
- Solo visible durante ruta `dispatched` o `in_progress`
- Lado dispatcher ya operativo (`ChatFloating` en `OpsMapDashboard`)
