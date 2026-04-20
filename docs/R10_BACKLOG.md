# R10 Backlog — CorteCero

> Fase: R10 — PLANIFICADOR + CONTRATOS + UX MONITOR + IMPORTACIÓN XLSX
> Principio rector: completar el planificador semanal, cerrar contratos API, finalizar monitor mode y habilitar importación de rutas estacionales desde XLSX.
> Última actualización: 2026-04-20 (rev 3)

---

## Orden de bloques

| Prioridad | ID | Bloque | Estado |
|-----------|-----|--------|--------|
| 1 | ROUTE-PLANNER-TW-001 | `PATCH /stops/{stop_id}/scheduled-arrival` — backend + OpenAPI + api.ts | **PROMULGADO** |
| 2 | ROUTE-PLANNER-CAL-001 | Calendario semanal `RoutePlannerCalendar` v2 — KPI strip, gantt, drawer, TW-001-UI | **PROMULGADO** |
| 3 | TW-001-UI | Input inline `type="time"` en drawer del planificador (incluido en CAL-001 v2) | **PROMULGADO** |
| 4 | UX-CLEANUP-001 | Eliminar nav "Rutas" interno + pills de estado azules en `OpsMapDashboard` | **CERRADO_LOCAL** |
| 5 | ROUTIFIC-ANALYSIS-001 | Análisis quirúrgico Routific Beta + comparativa + diseño XLSX import | **CERRADO** |
| 6 | ROUTE-TEMPLATE-MODEL-001 | Migration + models `RouteTemplate` + `RouteTemplateStop` | PENDIENTE |
| 7 | XLSX-PARSE-001 | Librería parsing XLSX en backend (`openpyxl`), auto-detect columnas, normalización | PENDIENTE |
| 8 | XLSX-TEMPLATES-001 | `POST /route-templates/import-xlsx` — importación rutas estacionales | PENDIENTE |
| 9 | ROUTE-FROM-TEMPLATE-001 | `POST /routes/from-template` — genera ruta del día desde plantilla | PENDIENTE |
| 10 | XLSX-UI-TEMPLATES-001 | Frontend: modal importación temporada + preview plantillas detectadas | PENDIENTE |
| 11 | XLSX-ORDERS-001 | `POST /orders/import-xlsx` — importación pedidos como Routific | PENDIENTE |
| 12 | XLSX-UI-ORDERS-001 | Frontend: modal upload pedidos + mapper visual + vista previa | PENDIENTE |
| 13 | DATE-FORMAT-CONFIG-001 | Setting `xlsx_date_format` en tenant + PATCH endpoint + UI Settings | PENDIENTE |
| 14 | R9-CONTRACT-001 | OpenAPI ↔ runtime alineados + catálogo de errores cerrado | PENDIENTE |
| 15 | R9-MONITOR-UX-001 | Delay alerts visibles en panel/drawer + fixes monitor mode | **CERRADO_LOCAL** |
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

## Definición de bloques pendientes

### ROUTE-TEMPLATE-MODEL-001 — Modelos de plantilla de ruta

**Tipo:** HARDENING (base de datos)
**Objetivo:** Crear las entidades de datos que soportan las rutas estacionales importadas desde XLSX

**Alcance:**
- Migration `NNN_route_templates.sql`:
  - Tabla `route_templates`: `id`, `tenant_id`, `name`, `season`, `vehicle_id`, `day_of_week`, `shift_start`, `shift_end`, `created_at`
  - Tabla `route_template_stops`: `id`, `template_id`, `sequence_number`, `customer_id`, `lat`, `lng`, `address`, `duration_min`, `notes`
  - FK constraints + índices `tenant_id`
- `backend/app/models.py`: clases `RouteTemplate` + `RouteTemplateStop` con relationships
- `backend/app/schemas.py`: schemas Pydantic para ambas entidades
- `openapi-spec-validator` OK tras añadir schemas

**Dependencias:** ninguna — puede implementarse en paralelo con XLSX-PARSE-001

---

### XLSX-PARSE-001 — Parser XLSX backend

**Tipo:** IMPLEMENTATION
**Objetivo:** Módulo reutilizable de parsing XLSX/CSV con auto-detección de columnas

**Alcance:**
- `backend/app/utils/xlsx_parser.py`:
  - Parsing con `openpyxl` (no pandas)
  - `parse_xlsx(file_bytes) → Generator[dict]`
  - `normalize_header(name) → str` — elimina tildes, lowercase, strip
  - `auto_map_columns(headers, field_aliases) → dict` — mapeo automático por alias
  - Soporte `.xlsx` y `.csv`
- Tabla de alias definidos en el módulo para campos de pedidos y de plantillas
- Tests unitarios en `backend/tests/test_xlsx_parser.py`

**Dependencias:** ninguna

---

### XLSX-TEMPLATES-001 — Importación XLSX de plantillas de ruta

**Tipo:** IMPLEMENTATION
**Objetivo:** `POST /route-templates/import-xlsx` — permite importar las rutas de verano/invierno del usuario

**Alcance:**
- Endpoint `POST /route-templates/import-xlsx` (multipart/form-data)
- Recibe `.xlsx`, aplica `xlsx_parser`, agrupa filas por `(vehicle_plate, day_of_week)`
- Resolución de vehículo por matrícula → `vehicle_id`; si no existe → warning, no error fatal
- Resolución de cliente por nombre → `customer_id` + coordenadas; si no existe → crear cliente nuevo
- Crea `RouteTemplate` + `RouteTemplateStop` records (multi-tenant)
- Respuesta: `{ templates_created: N, stops_total: N, errors: [...], warnings: [...] }`
- OpenAPI + api.ts actualizados
- Tests: happy path (XLSX válido), vehículo desconocido, cliente no encontrado

**Dependencias:** ROUTE-TEMPLATE-MODEL-001 + XLSX-PARSE-001

---

### ROUTE-FROM-TEMPLATE-001 — Generar ruta desde plantilla

**Tipo:** IMPLEMENTATION
**Objetivo:** `POST /routes/from-template` — crea una ruta operativa del día a partir de una plantilla

**Alcance:**
- Endpoint `POST /routes/from-template` con body `{ template_id, service_date, plan_id }`
- Crea `Route` + `RouteStop`s copiando secuencia de `RouteTemplateStop`s
- Estado inicial: `planned`; listo para dispatch u optimize
- Guard multi-tenant: `template.tenant_id == current.tenant_id`
- `GET /route-templates` — lista plantillas del tenant (para el selector de UI)
- OpenAPI + api.ts actualizados

**Dependencias:** ROUTE-TEMPLATE-MODEL-001

---

### XLSX-UI-TEMPLATES-001 — Frontend: modal importación de temporada

**Tipo:** IMPLEMENTATION
**Objetivo:** UI para subir el XLSX de rutas estacionales y previsualizar las plantillas detectadas

**Alcance:**
- Modal en `OperationalQueueCard` o sección Settings: "📥 Importar temporada"
- Step 1: drag & drop / file picker `.xlsx`
- Step 2: mapper de columnas (dropdowns: Matrícula, Día, Orden, Cliente, Dirección, Duración, Notas)
- Step 3: preview de plantillas detectadas (`vehicle_plate + day_of_week → N paradas`)
- Nombre de temporada: input texto (ej. "Verano 2026")
- Botón "Crear N plantillas" → llama `importRouteTemplatesXlsx()` en `api.ts` → toast ok/err
- Lista de plantillas existentes con botón "Usar hoy" → `createRouteFromTemplate()`

**Dependencias:** XLSX-TEMPLATES-001 + ROUTE-FROM-TEMPLATE-001

---

### XLSX-ORDERS-001 — Importación XLSX de pedidos

**Tipo:** IMPLEMENTATION
**Objetivo:** `POST /orders/import-xlsx` — importar lista de pedidos del día como Routific

**Alcance:**
- Endpoint `POST /orders/import-xlsx` (multipart/form-data)
- Campos mapeables: `customer_name`, `address`, `lat`, `lng`, `delivery_from`, `delivery_until`, `duration_min`, `load_kg`, `external_ref`, `notes`
- Resolución cliente por nombre → usar `lat/lng` de la DB; si no existe → crear cliente nuevo
- Crea `Order` records en estado `ready_for_planning`
- Respuesta: `{ imported: N, errors: [...], warnings: [...] }`
- OpenAPI + api.ts actualizados

**Dependencias:** XLSX-PARSE-001

---

### XLSX-UI-ORDERS-001 — Frontend: modal importación de pedidos

**Tipo:** IMPLEMENTATION
**Objetivo:** Modal de importación de pedidos con mapper visual y vista previa de 3 filas

**Alcance:**
- Botón "📥 Importar pedidos" en `OperationalQueueCard` o sección Pedidos
- Step 1: upload `.xlsx` / `.csv`
- Step 2: mapper de columnas con dropdowns + detección automática
- Step 3: vista previa 3 primeras filas + contador "N pedidos a importar"
- Selector de formato de fecha si la config de tenant no está fijada
- Botón "Importar N pedidos" → toast ok/err con detalle de errores

**Dependencias:** XLSX-ORDERS-001

---

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
