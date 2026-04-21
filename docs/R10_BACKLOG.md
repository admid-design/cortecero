# R10 Backlog — CorteCero

> Fase: R10 — PLANIFICADOR + CONTRATOS + UX MONITOR + IMPORTACIÓN XLSX
> Principio rector: completar el planificador semanal, cerrar contratos API, finalizar monitor mode y habilitar importación de rutas estacionales desde XLSX.
> Última actualización: 2026-04-21 (rev 4 — pipeline XLSX completado)

---

## Orden de bloques

| Prioridad | ID | Bloque | Estado |
|-----------|-----|--------|--------|
| 1 | ROUTE-PLANNER-TW-001 | `PATCH /stops/{stop_id}/scheduled-arrival` — backend + OpenAPI + api.ts | **PROMULGADO** — `7cf26e3` |
| 2 | ROUTE-PLANNER-CAL-001 | Calendario semanal `RoutePlannerCalendar` v2 — KPI strip, gantt, drawer, TW-001-UI | **PROMULGADO** — `6d505ac` |
| 3 | TW-001-UI | Input inline `type="time"` en drawer del planificador (incluido en CAL-001 v2) | **PROMULGADO** — incluido en `6d505ac` |
| 4 | UX-CLEANUP-001 | Eliminar nav "Rutas" interno + pills de estado azules en `OpsMapDashboard` | **PROMULGADO** — `442be46` |
| 5 | ROUTIFIC-ANALYSIS-001 | Análisis quirúrgico Routific Beta + comparativa + diseño XLSX import | **PROMULGADO** — `docs/routific-analysis-and-xlsx-import.md` |
| — | UX-FIXES-001 | hideSidebar, dropdowns Gestión, DetailPanel, useToast, Insights 6 KPIs, Nueva ruta | **PROMULGADO** — `f6aa23f` |
| 6 | ROUTE-TEMPLATE-MODEL-001 | Migration + models `RouteTemplate` + `RouteTemplateStop` | **PROMULGADO** — `f2cc690` |
| 7 | XLSX-PARSE-001 | Librería parsing XLSX en backend (`openpyxl`), auto-detect columnas, normalización | **PROMULGADO** — `f2cc690` |
| 8 | XLSX-TEMPLATES-001 | `POST /route-templates/import-xlsx` — importación rutas estacionales | **PROMULGADO** — `2a9888c` |
| 9 | ROUTE-FROM-TEMPLATE-001 | `POST /routes/from-template` — genera ruta del día desde plantilla | **PROMULGADO** — `bd7db90` + fixes `dba1cc8`, `048cc35`, `62f9385` |
| 10 | XLSX-UI-TEMPLATES-001 | Frontend: sección Plantillas con lista e importación XLSX | **PROMULGADO** — `b081ff6` |
| — | XLSX-UI-TEMPLATES-002 | Frontend: crear ruta del día desde plantilla seleccionada | **PROMULGADO** — `4faa590` |
| 11 | XLSX-ORDERS-001 | `POST /orders/import-xlsx` — importación pedidos como Routific | **PROMULGADO** — `79e5c93` |
| 12 | XLSX-UI-ORDERS-001 | Frontend: modal upload pedidos + mapper visual + vista previa | **PROMULGADO** — `a362568` |
| — | FIX-READY-DISPATCH | `ready-to-dispatch` filtra `ready_for_planning`, no `planned` | **PROMULGADO** — `307b66a` |
| 13 | DATE-FORMAT-CONFIG-001 | Setting `xlsx_date_format` en tenant + PATCH endpoint + UI Settings | PENDIENTE |
| 14 | R9-CONTRACT-001 | OpenAPI ↔ runtime alineados + catálogo de errores cerrado | PENDIENTE |
| 15 | R9-MONITOR-UX-001 | Delay alerts visibles en panel/drawer + fixes monitor mode | **PROMULGADO** — `b9e9374` |
| 16 | MONITOR-MODE-002 | Chat flotante conductor en `DriverRoutingCard` (completa MONITOR-MODE-002) | PENDIENTE |

---

## Bloques cerrados en R10

### ROUTIFIC-ANALYSIS-001 — Análisis Routific Beta y diseño XLSX import

**Tipo:** SPIKE + DOCS
**Estado:** CERRADO — 2026-04-20
**Objetivo:** Explorar Routific Beta de forma quirúrgica, comparar con CorteCero e identificar gaps. Diseñar la importación XLSX de rutas estacionales (caso de uso inmediato del usuario).

**Cerrado:**
- ✅ Análisis completo de Routific Beta: Orders, Customers, Routes (Plan/Dispatch/Monitor), Drivers, Insights, Settings, Company Settings
- ✅ Flujo de importación XLSX de Routific documentado (column mapper drag & drop, geocodificación, errores ⚠️)
- ✅ Insights: 4 KPI cards (Completed routes, Orders, Estimated distance, Working time) + drill-down por conductor
- ✅ Tabla comparativa Routific vs CorteCero (21 funcionalidades evaluadas)
- ✅ Diseño de 2 tipos de importación XLSX para CorteCero:
  - **Tipo A** (pedidos): `POST /orders/import-xlsx` — paridad con Routific
  - **Tipo B** (plantillas de ruta estacionales): `POST /route-templates/import-xlsx` — diferencial
- ✅ Modelos propuestos: `RouteTemplate` + `RouteTemplateStop`
- ✅ UI mockups para ambos modales de importación
- ✅ Orden de implementación en 8 bloques con dependencias
- ✅ Entregable: `docs/routific-analysis-and-xlsx-import.md`

**Hallazgos clave:**
- CorteCero supera a Routific en: GPS tracking, Monitor view, Planificador Gantt, Chat, POD
- Routific supera a CorteCero en: importación XLSX (gap crítico), Insights, notificaciones cliente
- El XLSX del usuario (rutas verano/invierno) corresponde al **Tipo B** — no existe en Routific, es diferencial
- Prioridad recomendada: Tipo B (plantillas) antes que Tipo A (pedidos)

---

### UX-CLEANUP-001 — Eliminación de ruido UI en OpsMapDashboard

**Tipo:** IMPLEMENTATION
**Estado:** CERRADO_LOCAL — 2026-04-20
**Objetivo:** Eliminar el botón de nav interno "Rutas" y las pills de filtro de estado azules que aparecían al hacer clic en "Rutas" desde el sidebar, ya que pertenecen al dashboard antiguo y crean confusión con el nuevo flujo.

**Cerrado:**
- ✅ Eliminado bloque `<button mf-nav-item onClick={() => setSidebarView("rutas")}>` (nav interno "Rutas") en `OpsMapDashboard.tsx`
- ✅ Eliminado bloque `<div className="mf-status-pills">` con los 7 botones de filtro (Todas/En curso/Despachada/Planificada/Completada/Borrador/Cancelada)
- ✅ Conservada barra `mf-filter-right` (toggle Monitoreo/Panel + date picker + refresh)
- ✅ Conservada lógica monitor mode (`sidebarView === "rutas"` sigue siendo válido internamente para KPI cards)
- ✅ `tsc --noEmit` pendiente de ejecutar (sandbox sin Docker)

**Huecos declarados:**
- `sidebarView` puede quedar en `"rutas"` si había rutas activas al cambiar de vista — comportamiento inocuo (solo afecta modo monitor)
- Vercel pendiente de confirmar con push del usuario

---

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

### UX-FIXES-001 — Pulido UX general

**Tipo:** IMPLEMENTATION
**Estado:** PROMULGADO — commit `f6aa23f` — 2026-04-21
**Objetivo:** Cerrar deuda UX acumulada en R9 antes de abrir pipeline XLSX.

**Cerrado:**
- ✅ `hideSidebar` en `OpsMapDashboard` — elimina sidebar doble cuando se accede desde GlobalShell
- ✅ `<select>` inline vehículo/conductor en pasos 3+4 del formulario Gestión
- ✅ `DetailPanel` en secciones Pedidos, Clientes, Conductores
- ✅ Hook `useToast` centralizado
- ✅ Insights con 6 KPIs (rutas + paradas + tasa de entrega)
- ✅ Botón "+ Nueva ruta" en Planificador → navega a Gestión

---

### ROUTE-TEMPLATE-MODEL-001 + XLSX-PARSE-001 — Modelos y parser XLSX

**Tipo:** IMPLEMENTATION
**Estado:** PROMULGADO — commit `f2cc690` — 2026-04-21
**Objetivo:** Base de datos y utilidad de parsing para el pipeline XLSX completo.

**Cerrado:**
- ✅ Migration `028_route_templates.sql` — tablas `route_templates` + `route_template_stops` con FK, índices, idempotente
- ✅ `RouteTemplate` + `RouteTemplateStop` en `backend/app/models.py`
- ✅ Schemas Pydantic en `backend/app/schemas.py`
- ✅ `backend/app/utils/xlsx_parser.py` — `parse_xlsx()`, `parse_csv()`, `normalize_header()`, `auto_map_columns()`; robusto ante filas con más columnas que cabeceras (fix `a75ec68`)
- ✅ Tests unitarios `test_xlsx_parser.py`

---

### XLSX-ORDERS-001 — Importación XLSX de pedidos

**Tipo:** IMPLEMENTATION
**Estado:** PROMULGADO — commit `79e5c93` — 2026-04-21

**Cerrado:**
- ✅ `POST /orders/import-xlsx` (multipart/form-data) — crea pedidos `ready_for_planning`
- ✅ Resolución de cliente por nombre; crea cliente nuevo si no existe
- ✅ OpenAPI + `api.ts` actualizados

---

### XLSX-UI-ORDERS-001 — Modal importación pedidos

**Tipo:** IMPLEMENTATION
**Estado:** PROMULGADO — commit `a362568` — 2026-04-21

**Cerrado:**
- ✅ Modal con upload `.xlsx`/`.csv`, mapper visual de columnas, vista previa 3 filas
- ✅ Toast ok/err con detalle de filas importadas y errores

---

### XLSX-TEMPLATES-001 — Importación XLSX de plantillas de ruta

**Tipo:** IMPLEMENTATION
**Estado:** PROMULGADO — commit `2a9888c` — 2026-04-21

**Cerrado:**
- ✅ `POST /route-templates/import-xlsx` — agrupa filas por `(vehicle_plate, day_of_week)`, crea `RouteTemplate` + `RouteTemplateStop`
- ✅ Resolución vehículo por matrícula; warning si no existe (no error fatal)
- ✅ OpenAPI + `api.ts` actualizados

---

### ROUTE-FROM-TEMPLATE-001 — Generar ruta desde plantilla

**Tipo:** IMPLEMENTATION
**Estado:** PROMULGADO — commits `bd7db90`, `dba1cc8`, `048cc35`, `62f9385` — 2026-04-21

**Cerrado:**
- ✅ `GET /route-templates` — lista plantillas del tenant
- ✅ `POST /routes/from-template` — crea `Route` + `RouteStop`s desde plantilla; estado inicial `planned`
- ✅ `RoutingRoute.plan_id` y `RoutingRouteStop.order_id` son `string | null` en `api.ts`; null-guards en todos los componentes que usan esos campos

**Lección aprendida (Lección 8):** cambio de nullability de un campo es impacto 4-vías — ver CLAUDE.md § Lección 8.

---

### XLSX-UI-TEMPLATES-001 + XLSX-UI-TEMPLATES-002 — Frontend plantillas

**Tipo:** IMPLEMENTATION
**Estado:** PROMULGADO — commits `b081ff6`, `4faa590` — 2026-04-21

**Cerrado:**
- ✅ Sección "Plantillas" en GlobalShell con lista de plantillas por temporada/día
- ✅ Modal importación XLSX temporada — upload, mapper columnas, preview plantillas detectadas, nombre temporada
- ✅ Botón "Crear ruta hoy" por plantilla → `createRouteFromTemplate()` → toast

---

## Definición de bloques pendientes

### DATE-FORMAT-CONFIG-001 — Configuración formato de fecha XLSX

**Tipo:** HARDENING
**Objetivo:** Que el parser XLSX sepa en qué formato vienen las fechas del archivo del usuario

**Alcance:**
- Migration: `ALTER TABLE tenants ADD COLUMN xlsx_date_format VARCHAR(20) DEFAULT 'auto'`
- Endpoint `PATCH /settings/workspace` con body `{ xlsx_date_format: "DD-MM-YYYY" | "MM-DD-YYYY" | "YYYY-MM-DD" | "auto" }`
- `xlsx_parser.py` usa la configuración del tenant al parsear fechas
- UI: selector en sección Settings (simple dropdown, 4 opciones)

**Dependencias:** XLSX-PARSE-001

---

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
