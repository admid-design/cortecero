# Routific Beta — Análisis quirúrgico y diseño de importación XLSX para CorteCero

> Fecha de análisis: 2026-04-20
> Analizado: https://beta.routific.com (cuenta Santiago Ospina)
> Autor: Claude (basado en exploración directa de la UI)

---

## 1. Mapa completo de Routific Beta

### 1.1 Navegación lateral (sidebar)

| Ítem | Descripción |
|------|-------------|
| **New Workspace** | Crea un espacio de trabajo nuevo dentro de la compañía |
| **Orders** | Lista de pedidos/entregas; importación XLSX; añadir pedido individual |
| **Customers** | Base de datos de clientes con nombre, dirección, notas |
| **Routes** | Planificación y gestión de rutas activas |
| **Drivers** | Lista y gestión de conductores |
| **Insights** | Panel de métricas y analítica (4 KPIs) |
| **Settings** | Configuración del workspace (templates, preferencias, notificaciones) |
| **Help** | Ayuda contextual |
| **Company settings** | Configuración global de empresa (perfil, workspaces, equipo, API) |
| **Account (nombre)** | Account settings / Log out |

---

### 1.2 Orders

La sección de Orders es la entrada principal de datos. El flujo de importación XLSX es el más relevante para CorteCero.

**Acciones disponibles desde "+ Add order":**
- Upload spreadsheet with orders
- Add order (formulario individual)

**Estado de la lista:**
- 18 órdenes importadas de prueba
- ⚠️ 11/18 con error de geocodificación (las direcciones en el XLSX de prueba eran matrículas y días de la semana, no direcciones reales)
- Columnas visibles: ID de pedido, cliente, dirección, ventana de tiempo, duración estimada

**Flujo de importación XLSX (columna mapper):**

1. El usuario sube el archivo `.xlsx` o `.csv`
2. Routific muestra un mapper de columnas con dos paneles:
   - Panel izquierdo: campos reconocidos de Routific
   - Panel derecho: columnas detectadas del archivo subido
3. El usuario arrastra columnas del archivo a los campos de Routific (drag & drop)
4. Campos disponibles en el mapper:
   - `Name` (obligatorio)
   - `Address` (para geocodificación — si no hay lat/lng)
   - `Latitude` / `Longitude` (alternativa a Address, sin geocodificación)
   - `Delivery start` / `Delivery end` (ventana de tiempo)
   - `Duration` (minutos en parada)
   - `Load` (capacidad/peso/volumen)
   - `Notes`
   - Campos personalizados (custom fields)
5. Routific geocodifica automáticamente las direcciones que no tienen lat/lng (usa Mapbox)
6. Si la geocodificación falla → la orden queda marcada con ⚠️ pero sigue en la lista

**Configuración de formato de fecha (global en Company Settings):**
- Detect automatically
- DD-MM-YYYY
- MM-DD-YYYY
- YYYY-MM-DD

---

### 1.3 Customers

Base de datos persistente de clientes. Permite reutilizar clientes entre planificaciones sin reimportar datos. No explorado en profundidad — en el demo la lista estaba vacía.

---

### 1.4 Routes — Plan Routes (flujo completo)

El flujo tiene dos pasos principales dentro de la misma pantalla:

**Paso 1 — Lista de órdenes:**
- Vista de todas las órdenes importadas
- Selección de órdenes para incluir en la planificación del día

**Paso 2 — Panel triple: Orders | Routes | Options**

**Panel Orders:**
- Lista de órdenes seleccionadas
- Drag & drop para mover entre rutas

**Panel Routes:**
- Rutas configuradas para el día
- "+ Add route" → dropdown: Add route | Add route from template
- **Create Route modal** (campos idénticos a Template):
  | Campo | Tipo | Obligatorio |
  |-------|------|-------------|
  | Route Name | texto | ✓ |
  | Shift start | hora | ✓ |
  | Shift end | hora | ✓ |
  | Start location | texto/dirección | — |
  | "Use same location for end address" | checkbox | — |
  | End location | texto/dirección | — |
  | Tags | texto libre | — |
  | Vehicle capacity | número | — |
  | Number of routes | número | — |

**Panel Options:**
- Resumen de Optimization Preferences (enlace para editar)
- Route Templates → "Automatically create routes: Yes/No"

---

### 1.5 Settings — Workspace Settings (modal)

Accesible desde el icono de engranaje en el sidebar.

#### Tab: Templates

| Columna | Descripción |
|---------|-------------|
| ACTIVE | Toggle on/off para activar/desactivar el template |
| TEMPLATE NAME | Nombre del template |
| SHIFT TIME | Rango horario (ej. 09:00 - 17:00) |
| START LOCATION | Dirección de inicio |
| END LOCATION | Dirección de fin |
| CAPACITY | Capacidad del vehículo |

**Editar template — campos completos:**

| Campo | Tipo | Obligatorio |
|-------|------|-------------|
| Template Name | texto | ✓ |
| Shift start | hora | ✓ |
| Shift end | hora | ✓ |
| Start Location | texto/dirección | — |
| "Use same location for end address" | checkbox | — |
| End Location | texto/dirección | — |
| Tags | texto libre | — |
| Capacity | número | — |
| Number of Routes | número | — |

#### Tab: Preferences — Optimization Preferences

| Preferencia | Valor por defecto observado |
|-------------|----------------------------|
| Balance routes | Off / Orders toggle |
| Flexible start time | OFF |
| Exclude toll roads | OFF |
| Exclude ferry routes | ON (auto-detectado — Mallorca) |
| Allow flexible route capacity | ON |
| Allow route overtime | ON |
| Allow late delivery | ON |
| Default order duration (min) | 10 |

#### Tab: Customer Notifications

**General:**
- Send Notifications: Off | Email

**Events (4, todos Inactive por defecto):**

| Evento | Configuración adicional |
|--------|------------------------|
| Delivery scheduled | Delivery window: ETA ± 30 min (dropdown) + template de email |
| On the way | Template de email |
| Delivery completed | Template de email |
| Delivery missed | Template de email |

**Template de email observado (Delivery scheduled):**
- Subject: "Your delivery has been scheduled!"
- Body: "Your delivery is planned between {eta_window} on {date}."

---

### 1.6 Company Settings

Accesible desde la parte inferior del sidebar.

#### Company profile

| Campo | Opciones |
|-------|---------|
| Company name | texto |
| Distance units | Kilometers / Miles |
| Time format | 24h / 12h |
| **Spreadsheet uploads → Delivery date format** | Detect automatically / DD-MM-YYYY / MM-DD-YYYY / YYYY-MM-DD |

#### Workspaces

- Lista de workspaces con badge "Current" y botón "Delete"
- "+ Create workspace"

#### Team

| Columna | Descripción |
|---------|-------------|
| TEAMMATE | Nombre |
| EMAIL | Email |
| STATUS | Estado (activo/pendiente) |
| ROLE | Rol |

Acción: "+ Add teammate"

#### Routific API

- Tabla de tokens: NAME | CREATED ON | CREATED BY
- Estado vacío cuando no hay tokens activos
- "+ Create API token"
- Link: "API documentation"

---

### 1.7 Insights

Panel de analítica. URL: `/insights?startDate=...&endDate=...&chart=bar`

**Sección "Route data" — 4 KPI cards:**

| Métrica | Descripción | Detalle |
|---------|-------------|---------|
| Completed routes | Rutas completadas en el período | Sparkline + "Driver stats" |
| Orders | Pedidos entregados | Sparkline + "Driver stats" |
| Estimated distance | Distancia total estimada (km) | Sparkline + "Driver stats" |
| Working time | Tiempo de trabajo total | Sparkline + "Driver stats" |

**Date range picker global:** top-right, por defecto el mes anterior.

**Driver stats (drill-down):**
- URL: `/insights/details?metric=<completed-routes|orders|estimated-distance|working-time>`
- Breadcrumb: Insights > Routes
- Gráfico por conductor (bar o line)
- **Chart type:** Bar / Line (2 opciones)
- **Filter:** solo un filtro — Drivers → "All drivers"
- **Export:** botón de exportación de datos

**Nota:** La sección Insights es simple en el beta — sin gráficos de tendencia detallados, sin comparativas entre períodos, sin métricas de puntualidad ni tasa de éxito. Routific tiene un chat contextual ("Suzanne: 👋 What do you want to see more of here?") que sugiere que está en desarrollo activo.

---

## 2. Routific vs CorteCero — Comparativa de funcionalidades

### 2.1 Tabla comparativa

| Funcionalidad | Routific Beta | CorteCero (estado actual) | Gap / Oportunidad |
|---------------|--------------|--------------------------|-------------------|
| **Importación XLSX de pedidos** | ✅ Completo — column mapper con drag & drop, geocodificación automática | ❌ No existe | **Prioridad alta — ver Sección 3** |
| **Importación XLSX de rutas plantilla** | ❌ No existe (solo templates de configuración de vehículo, no de paradas asignadas) | ❌ No existe | **Oportunidad diferencial — ver Sección 3** |
| **Route Templates** | ✅ Templates de vehículo/turno (reutilizables por día) | ❌ No existe explícitamente | Parcialmente cubierto por seed demo; formalizar como entidad |
| **Optimización de rutas** | ✅ Google ORTOOLS integrado, configurable | ✅ Google Route Optimization API (DEMO-OPT-001) | Paridad funcional |
| **Preferencias de optimización** | ✅ 8 parámetros configurables por workspace | ❌ Sin UI de configuración (parámetros hardcoded) | Añadir panel de preferencias |
| **GPS tracking conductor** | ❌ No visible en beta | ✅ GPS-001 implementado (polling 30s) | CorteCero gana |
| **Prueba de entrega (POD)** | ❌ No visible en beta | ✅ Firma implementada, foto schema ready | CorteCero gana |
| **Chat dispatcher ↔ conductor** | ❌ No visible en beta | ✅ CHAT-001 (dispatcher), lado conductor pendiente | CorteCero gana (parcial) |
| **Monitor view / Fleet view** | ❌ No visible en beta | ✅ OpsMapDashboard implementado | CorteCero gana |
| **Planificador visual (timeline)** | ❌ No visible en beta | ✅ RoutePlannerCalendar implementado | CorteCero gana |
| **Ventanas de tiempo (time windows)** | ✅ Delivery start / Delivery end por pedido | ✅ F1–F6 implementados | Paridad |
| **Notificaciones cliente** | ✅ Email por evento (4 eventos) | ❌ D1 congelado — pendiente proveedor | Gap relevante |
| **Multi-workspace** | ✅ Aislamiento completo por workspace | ❌ Multi-tenant sí, multi-workspace no (mismo tenant) | Gap arquitectónico |
| **Insights / Analytics** | ✅ Básico — 4 KPIs + drill-down por conductor | ❌ No existe | Gap significativo |
| **Exportación de datos de ruta** | ✅ Export por rango de fechas | ❌ No existe | Añadir cuando haya datos reales |
| **Gestión de conductores** | ✅ Sección Drivers dedicada | ✅ Gestión básica en UI | Paridad funcional básica |
| **Gestión de clientes (Customer DB)** | ✅ Base de datos persistente de clientes | ✅ `customers` table existe | Paridad en backend; UI limitada |
| **API pública** | ✅ Tokens por compañía | ✅ JWT, sin tokens de API pública | Gap si se necesita integración externa |
| **Configuración de formato de fecha** | ✅ Global en Company Settings | ❌ No existe | Necesario para XLSX import |
| **Exclude ferry routes** | ✅ Toggle en Optimization Preferences | ❌ No existe en UI | Crítico para Mallorca |
| **Balance routes** | ✅ Toggle Off/Orders | ❌ Sin UI | Añadir a preferencias |

### 2.2 Resumen de posición competitiva

**Donde CorteCero supera a Routific Beta:**
- GPS tracking conductor en tiempo real
- Monitor/Fleet view operativo
- Planificador visual tipo Gantt con ETAs editables
- Chat interno dispatcher ↔ conductor
- POD con firma digital

**Donde Routific supera a CorteCero:**
- Importación XLSX (gap crítico — el usuario tiene rutas de verano/invierno en XLSX)
- Insights / Analytics básico
- Notificaciones automáticas al cliente
- Preferencias de optimización configurables en UI
- Configuración global de workspace (formato de fecha, unidades)

**Gaps neutros (ambos limitados):**
- Notificaciones en tiempo real (Routific: email batch; CorteCero: SSE sin Redis)
- IA de asistencia operativa (ninguno)

---

## 3. Diseño de importación XLSX para CorteCero

### 3.1 Contexto del caso de uso

El usuario tiene **rutas de verano e invierno** en formato XLSX. Estas no son simples listas de pedidos — son **plantillas de ruta predefinidas**: cada fila representa una parada asignada a un conductor en un día de la semana específico. La estructura probable del XLSX:

```
| Matrícula | Día      | Cliente          | Dirección           | Observaciones |
|-----------|----------|------------------|---------------------|---------------|
| 6244 FKJ  | Lunes    | Supermercado Can Biel | Carrer Major 12, Sóller | ... |
| 6244 FKJ  | Lunes    | Bar Es Moli      | Plaça de la Vila 3  | ... |
| 7823 JBV  | Martes   | Restaurante Sa Plana | ... | ... |
```

Esto requiere **dos tipos de importación XLSX** para CorteCero:

| Tipo | Qué importa | Cuándo usar |
|------|-------------|-------------|
| **Tipo A: Importación de pedidos** | Lista de entregas del día | Operativa diaria — como Routific |
| **Tipo B: Importación de plantillas de ruta** | Rutas estacionales completas (conductor + paradas por día) | Configuración inicial, cambio de temporada |

---

### 3.2 Tipo A — Importación de pedidos (como Routific)

**Endpoint:**
```
POST /orders/import-xlsx
Content-Type: multipart/form-data
```

**Columnas mapeables:**

| Campo CorteCero | Alias reconocidos automáticamente | Obligatorio |
|-----------------|-----------------------------------|-------------|
| `customer_name` | Name, Cliente, Customer, Nombre | ✓ |
| `address` | Address, Dirección, Direccion | Condicional (si no hay lat/lng) |
| `lat` | Lat, Latitude, Latitud | Condicional |
| `lng` | Lng, Lon, Longitude, Longitud | Condicional |
| `delivery_from` | Delivery start, Desde, From, Time from | — |
| `delivery_until` | Delivery end, Hasta, Until, Time to | — |
| `duration_min` | Duration, Duración, Stop time | — |
| `load_kg` | Load, Weight, Peso, Capacidad | — |
| `external_ref` | Reference, Ref, Pedido, Order ID | — |
| `notes` | Notes, Notas, Observaciones | — |

**Ventaja sobre Routific:** CorteCero no necesita geocodificación si el XLSX ya tiene `lat/lng` — los clientes en la DB ya tienen coordenadas. Si falta lat/lng, usar la dirección del cliente en la DB por nombre coincidente antes de intentar geocodificación externa.

**Flujo:**
1. Upload → parse XLSX en servidor
2. Auto-detectar columnas por nombre (case-insensitive, sin tildes)
3. Mostrar mapper si hay columnas no reconocidas
4. Validar: cliente existe en DB → usar su `lat/lng`; si no existe → crear como cliente nuevo o marcar para geocodificación
5. Crear `Order` records en `tenant_id` del usuario
6. Devolver: `{ imported: N, errors: [...], warnings: [...] }`

---

### 3.3 Tipo B — Importación de plantillas de ruta (nuevo, diferencial)

Este tipo no existe en Routific. Es el caso de uso principal del usuario: rutas de verano/invierno donde cada matrícula/conductor tiene asignadas paradas fijas por día de la semana.

**Endpoint:**
```
POST /route-templates/import-xlsx
Content-Type: multipart/form-data
```

**Esquema esperado del XLSX:**

```
| vehicle_plate | day_of_week | sequence | customer_name | address | lat | lng | duration_min | notes |
```

**Columnas mapeables:**

| Campo | Alias reconocidos | Descripción |
|-------|-------------------|-------------|
| `vehicle_plate` | Matrícula, Plate, Vehículo, Vehicle | Vincula con `vehicles` por matrícula |
| `day_of_week` | Día, Day, Lunes/Martes/..., Mon/Tue/... | 1–7 o nombre del día (ES/EN) |
| `sequence` | Orden, Sequence, Seq, Parada# | Orden de la parada en la ruta |
| `customer_name` | Cliente, Customer, Name, Nombre | Vincula con `customers` o crea nuevo |
| `address` | Dirección, Address | Para resolución de lat/lng si falta |
| `lat` | Lat, Latitude | — |
| `lng` | Lng, Longitude | — |
| `duration_min` | Duration, Duración, Tiempo | — |
| `notes` | Notas, Notes, Observaciones | — |
| `template_name` | Plantilla, Template, Ruta | Nombre del grupo (ej. "Zona Norte Verano") |

**Modelos afectados:**

```python
# Nueva entidad RouteTemplate (en models.py)
class RouteTemplate(Base):
    __tablename__ = "route_templates"
    id = Column(UUID, primary_key=True)
    tenant_id = Column(UUID, ForeignKey("tenants.id"), nullable=False)
    name = Column(String, nullable=False)            # "Zona Norte Verano"
    season = Column(String)                          # "verano" | "invierno" | None
    vehicle_id = Column(UUID, ForeignKey("vehicles.id"))
    day_of_week = Column(Integer)                   # 1=Lunes ... 7=Domingo
    shift_start = Column(Time)
    shift_end = Column(Time)
    created_at = Column(DateTime, default=func.now())
    stops = relationship("RouteTemplateStop", back_populates="template")

class RouteTemplateStop(Base):
    __tablename__ = "route_template_stops"
    id = Column(UUID, primary_key=True)
    template_id = Column(UUID, ForeignKey("route_templates.id"), nullable=False)
    sequence_number = Column(Integer, nullable=False)
    customer_id = Column(UUID, ForeignKey("customers.id"))
    lat = Column(Float)
    lng = Column(Float)
    address = Column(String)
    duration_min = Column(Integer, default=10)
    notes = Column(Text)
```

**Flujo de importación Tipo B:**

1. Upload XLSX → parse en servidor
2. Agrupar filas por `(vehicle_plate, day_of_week)` → cada grupo = una `RouteTemplate`
3. Resolución de vehículo: buscar en `vehicles` por matrícula → vincular `vehicle_id`
4. Resolución de cliente: buscar en `customers` por nombre → si existe, usar `lat/lng` del cliente; si no, crear cliente nuevo
5. Crear `RouteTemplate` + `RouteTemplateStop` records
6. Devolver resumen: plantillas creadas, paradas por plantilla, errores

**Generación de ruta desde plantilla:**

```
POST /routes/from-template
{
  "template_id": "uuid",
  "service_date": "2026-07-01",
  "plan_id": "uuid"
}
```

Crea una `Route` + `RouteStop`s copiando la secuencia de la plantilla. El dispatcher puede luego optimizar si lo desea.

---

### 3.4 Configuración global — Formato de fecha XLSX

Añadir en tabla `tenants` (o nueva tabla `workspace_settings`):

```sql
-- Migration NNN_xlsx_date_format.sql
DO $$ BEGIN
  ALTER TABLE tenants ADD COLUMN xlsx_date_format VARCHAR(20) DEFAULT 'auto';
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- Valores válidos: 'auto' | 'DD-MM-YYYY' | 'MM-DD-YYYY' | 'YYYY-MM-DD'
```

Endpoint de configuración:
```
PATCH /settings/workspace
{ "xlsx_date_format": "DD-MM-YYYY" }
```

---

### 3.5 Frontend — UI de importación

#### Tipo A (pedidos) — Modal de importación

```
┌─────────────────────────────────────────────────────┐
│  Importar pedidos desde Excel / CSV                  │
│                                                       │
│  [ Arrastrar archivo aquí o hacer clic para subir ]  │
│          .xlsx  .csv  máx. 5 MB                      │
│                                                       │
│  ── Mapear columnas ─────────────────────────────── │
│                                                       │
│  Cliente*         ▼ [Columna detectada: "Nombre"]    │
│  Dirección        ▼ [Columna detectada: "Dirección"] │
│  Latitud          ▼ [No mapeado]                     │
│  Longitud         ▼ [No mapeado]                     │
│  Desde            ▼ [Columna detectada: "Desde"]     │
│  Hasta            ▼ [No mapeado]                     │
│  Duración (min)   ▼ [No mapeado]                     │
│  Peso/carga       ▼ [No mapeado]                     │
│  Referencia       ▼ [Columna detectada: "Pedido"]    │
│  Notas            ▼ [No mapeado]                     │
│                                                       │
│  Formato de fecha: [DD-MM-YYYY ▼]                    │
│                                                       │
│  Vista previa: 3 primeras filas                      │
│  ┌──────────────┬──────────────┬──────────────┐      │
│  │ Cliente      │ Dirección    │ Desde        │      │
│  │ Can Biel     │ Carrer Major │ 09:00        │      │
│  │ Es Moli      │ Plaça Vila   │ 10:30        │      │
│  └──────────────┴──────────────┴──────────────┘      │
│                                                       │
│  [Cancelar]                    [Importar 18 pedidos] │
└─────────────────────────────────────────────────────┘
```

#### Tipo B (plantillas de ruta) — Modal de importación

```
┌─────────────────────────────────────────────────────┐
│  Importar plantillas de ruta (temporada)             │
│                                                       │
│  [ Arrastrar archivo aquí o hacer clic para subir ]  │
│                                                       │
│  ── Mapear columnas ─────────────────────────────── │
│                                                       │
│  Matrícula*       ▼ [Columna: "Matrícula"]           │
│  Día semana*      ▼ [Columna: "Día"]                 │
│  Orden parada     ▼ [Columna: "Seq"]                 │
│  Cliente*         ▼ [Columna: "Cliente"]             │
│  Dirección        ▼ [Columna: "Dirección"]           │
│  Duración (min)   ▼ [No mapeado]                     │
│  Notas            ▼ [Columna: "Observaciones"]       │
│                                                       │
│  Nombre de temporada: [______________________]        │
│  (ej. "Verano 2026", "Invierno 2025")               │
│                                                       │
│  Vista previa de plantillas detectadas:              │
│  • 6244 FKJ — Lunes (12 paradas)                    │
│  • 6244 FKJ — Martes (9 paradas)                    │
│  • 7823 JBV — Lunes (11 paradas)                    │
│  • ... 14 plantillas en total                        │
│                                                       │
│  [Cancelar]              [Crear 14 plantillas]       │
└─────────────────────────────────────────────────────┘
```

---

### 3.6 Implementación — Orden de trabajo sugerida

| Paso | Bloque | Descripción | Dependencias |
|------|--------|-------------|--------------|
| 1 | `XLSX-PARSE-001` | Librería de parsing XLSX en backend (`openpyxl`); auto-detect de columnas; normalización de nombres (tildes, case) | Ninguna |
| 2 | `XLSX-ORDERS-001` | `POST /orders/import-xlsx` + mapper de columnas + resolución cliente por nombre | XLSX-PARSE-001 |
| 3 | `XLSX-UI-ORDERS-001` | Frontend: modal upload + mapper visual + vista previa 3 filas | XLSX-ORDERS-001 |
| 4 | `ROUTE-TEMPLATE-MODEL-001` | Migration + models `RouteTemplate` + `RouteTemplateStop` | Ninguna |
| 5 | `XLSX-TEMPLATES-001` | `POST /route-templates/import-xlsx` + agrupación por matrícula/día | XLSX-PARSE-001 + ROUTE-TEMPLATE-MODEL-001 |
| 6 | `ROUTE-FROM-TEMPLATE-001` | `POST /routes/from-template` — genera ruta del día desde plantilla | ROUTE-TEMPLATE-MODEL-001 |
| 7 | `XLSX-UI-TEMPLATES-001` | Frontend: modal importación temporada + preview de plantillas detectadas | XLSX-TEMPLATES-001 |
| 8 | `DATE-FORMAT-CONFIG-001` | Setting `xlsx_date_format` en tenant + PATCH endpoint + UI en Settings | XLSX-PARSE-001 |

**Recomendación de prioridad:** Empezar por **Tipo B (plantillas)** porque es el caso de uso inmediato del usuario (rutas de verano/invierno) y es diferencial respecto a Routific. El Tipo A puede esperar o desarrollarse en paralelo.

---

### 3.7 Decisiones técnicas clave

**Parsing XLSX:** usar `openpyxl` (ya está disponible en el ecosistema Python). No `pandas` — evita la dependencia pesada para una operación puntual.

```python
# backend/app/utils/xlsx_parser.py
import openpyxl
from typing import Generator

def parse_xlsx(file_bytes: bytes) -> Generator[dict, None, None]:
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb.active
    headers = [normalize_header(cell.value) for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    for row in ws.iter_rows(min_row=2, values_only=True):
        yield dict(zip(headers, row))

def normalize_header(val: str | None) -> str:
    if not val:
        return ""
    import unicodedata
    val = unicodedata.normalize("NFKD", str(val)).encode("ascii", "ignore").decode()
    return val.strip().lower().replace(" ", "_")
```

**Auto-detección de columnas:** mapa de alias → campo canonical, normalizado sin tildes:

```python
COLUMN_ALIASES = {
    "customer_name": ["name", "cliente", "customer", "nombre", "razon_social"],
    "address": ["address", "direccion", "domicilio", "dir"],
    "lat": ["lat", "latitude", "latitud"],
    "lng": ["lng", "lon", "longitude", "longitud"],
    "vehicle_plate": ["matricula", "plate", "vehiculo", "vehicle", "mat"],
    "day_of_week": ["dia", "day", "dia_semana", "weekday"],
    # ...
}
```

**Resolución de días en español:**

```python
DAY_NAMES_ES = {
    "lunes": 1, "martes": 2, "miercoles": 3, "jueves": 4,
    "viernes": 5, "sabado": 6, "domingo": 7,
    # inglés también
    "monday": 1, "tuesday": 2, "wednesday": 3, "thursday": 4,
    "friday": 5, "saturday": 6, "sunday": 7,
}
```

**Sin geocodificación externa en Tipo B:** las rutas de verano/invierno del usuario ya tienen clientes reales en la DB con coordenadas. La resolución es por nombre → `customers.name ILIKE %name%` → si hay match único, usar `lat/lng` del cliente. Mucho más rápido y sin coste de API.

---

## 4. Adaptaciones de UI dashboard inspiradas en Routific

Más allá del XLSX, estos cambios de UI mejoran la experiencia operativa:

| Elemento Routific | Estado CorteCero | Adaptación recomendada |
|-------------------|-----------------|------------------------|
| **Route templates como entidad de primera clase** | No existe | Añadir sección "Plantillas" en sidebar; listar por temporada |
| **Optimization Preferences en UI** | Hardcoded | Añadir panel de configuración en Settings workspace |
| **Panel de creación de ruta con campos explícitos** | Gestión form de 4 pasos | Añadir campo "Número de rutas" para expansión automática |
| **"Exclude ferry routes" toggle** | Sin UI | Crítico para Mallorca — añadir a preferencias de optimización |
| **Insights básico (4 KPIs)** | No existe | 4 cards mínimas: rutas completadas, entregas, km totales, tiempo medio |
| **Export de datos por rango de fechas** | No existe | Añadir cuando haya datos reales de producción |
| **Notificaciones al cliente** | D1 congelado | Desbloquear con Resend/Postmark cuando se decida proveedor |

---

## 5. Gaps críticos a declarar (no sobreafirmar)

Antes de cualquier demo comparativa con Routific:

- **Importación XLSX** no existe en CorteCero → no presentar como capacidad hasta implementar
- **Insights** no existe en CorteCero → no mostrar analítica
- **Notificaciones al cliente** congeladas → no prometer en demo
- **Route templates** no formalizados como entidad → las rutas del seed no son plantillas reutilizables
- **Multi-workspace** no existe en CorteCero → si el cliente tiene múltiples zonas, necesita multi-tenant separado

---

*Documento generado tras análisis quirúrgico completo de Routific Beta (2026-04-20). Todas las capturas de pantalla son del workspace de Santiago Ospina en beta.routific.com. El análisis cubre: Orders, Customers, Routes (Plan Routes, Create Route, Templates), Drivers, Insights (4 KPIs + Driver stats drill-down), Settings (Templates, Preferences, Customer Notifications) y Company Settings (Company profile, Workspaces, Team, Routific API).*
