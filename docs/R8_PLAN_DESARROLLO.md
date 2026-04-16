# CorteCero — Plan de Desarrollo R8: Producto Polpoo-completo

> Fecha: 2026-04-15  
> Objetivo: Construir el producto completo equivalente a Polpoo 2.0  
> Base técnica: CorteCero R7 verificado en CI  
> Referencia de mapas: https://github.com/googlemaps/js-route-optimization-app  

---

## Principios de ejecución

- Un bloque por vez, tipo declarado, cierre verificado
- Cada bloque añade una capacidad demostrable, no código sin evidencia
- Invariantes R1-R7 intactos en todo momento (multi-tenant, RBAC, contrato de errores)
- Ningún bloque se declara cerrado sin test green + evidence green donde aplique
- El mapa usa Google Maps JS SDK (misma cuenta GCP que Route Optimization)

---

## Estado de partida verificado (R7)

| Capacidad | Estado |
|---|---|
| Flujo dispatcher: plan → dispatch → optimize → move-stop | VERIFICADO |
| PWA conductor: arrive / complete / fail / skip / incidencias | VERIFICADO |
| Google Route Optimization integrado | PARCIAL (smoke pendiente) |
| Customer con lat/lng en DB | VERIFICADO |
| CustomerOperationalProfile con window_start/window_end | VERIFICADO |
| RouteStop con estimated_arrival_at | VERIFICADO |
| Colas, dashboard, auditoría, admin | VERIFICADO |

---

## Fases y bloques

---

### FASE A — Núcleo visual demostrable
> Objetivo: tener una demo que muestre mapa + optimización + firma. Sin esto no hay producto.

---

#### BLOQUE A1 — Mapa de ruta en dispatcher (MAP-001)
**Tipo:** IMPLEMENTATION  
**Objetivo:** El dispatcher ve las paradas de una ruta en un mapa Google Maps interactivo. Sin GPS en tiempo real todavía — solo posición estática de paradas según lat/lng del cliente.

**Prerequisito:** Activar Google Maps JavaScript API en proyecto GCP `samurai-system`. Crear API Key restringida a `http://localhost:3000` y al dominio de producción.

**DB:** Ningún cambio. `customers.lat/lng` ya existe.

**Backend:**
- `GET /routes/{routeId}/map-data` → devuelve array de `{stop_sequence, lat, lng, customer_name, status, estimated_arrival_at}` para todas las paradas de la ruta. Solo lecturas, sin side effects.

**Frontend:**
- Instalar `@googlemaps/react-wrapper` (o Mapbox GL JS si se prefiere)
- Referencia de implementación: https://github.com/googlemaps/js-route-optimization-app (ver `/src/components/Map`)
- Nuevo componente `RouteMapCard` en `frontend/components/`
- Integrar en `DispatcherRoutingCard`: tab "Lista" (actual) + tab "Mapa"
- Marcadores por estado: naranja = pending, azul = en_route, verde = completed, rojo = failed
- Línea de ruta en orden de secuencia (polyline)
- Popup por marcador: nombre cliente, ETA, estado

**Tests:**
- Backend: test que verifica que map-data devuelve paradas ordenadas por secuencia
- Frontend: test que verifica render del componente con datos mock

**Definition of done:** El dispatcher puede abrir una ruta y ver las paradas en el mapa con su estado en tiempo real (polling cada 30s).

---

#### BLOQUE A2 — Firma digital / Prueba de entrega (POD-001)
**Tipo:** IMPLEMENTATION  
**Objetivo:** El conductor captura firma del cliente al completar una parada. La firma se almacena vinculada al stop y es consultable desde el dispatcher.

**DB — Migration 020:**
```sql
CREATE TABLE IF NOT EXISTS stop_proofs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  route_stop_id UUID NOT NULL,
  route_id UUID NOT NULL,
  proof_type TEXT NOT NULL CHECK (proof_type IN ('signature', 'photo', 'both')),
  signature_data TEXT,        -- base64 PNG de la firma
  photo_url TEXT,             -- URL a S3/storage (fase posterior)
  signed_by TEXT,             -- nombre del receptor
  captured_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  FOREIGN KEY (route_stop_id, tenant_id) REFERENCES route_stops(id, tenant_id) ON DELETE CASCADE,
  FOREIGN KEY (route_id, tenant_id) REFERENCES routes(id, tenant_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_stop_proofs_stop ON stop_proofs(route_stop_id);
```

**Backend:**
- `POST /stops/{stopId}/proof` — acepta `{proof_type, signature_data, signed_by}`. Solo callable por driver autenticado. Valida que el stop esté en estado `arrived` o `completed` del mismo route del driver.
- `GET /stops/{stopId}/proof` — accesible por dispatcher y driver. Devuelve datos de la prueba.
- Modificar `POST /stops/{stopId}/complete` para que opcionalmente acepte proof en el mismo request.

**Frontend (PWA conductor - DriverRoutingCard):**
- Canvas de firma en pantalla táctil con `react-signature-canvas`
- Botón "Firmar y completar" como alternativa a "Completar sin firma"
- Campo nombre del receptor (opcional)
- Preview de la firma antes de enviar

**Frontend (Dispatcher):**
- En el detalle de ruta, cada parada completada muestra icono "Ver albarán"
- Modal con la firma y nombre del receptor + timestamp

**Tests:**
- Backend: happy path firma, intento desde driver no asignado (403), stop en estado incorrecto (409)
- Frontend: render canvas, captura, envío

**Definition of done:** Driver captura firma en pantalla, dispatcher la ve en detalle de ruta.

---

#### BLOQUE A3 — Posición GPS del conductor (GPS-001)
**Tipo:** IMPLEMENTATION  
**Objetivo:** La app del conductor envía su posición periódicamente al backend. El backend la almacena. El dispatcher puede ver la última posición conocida en el mapa (sin streaming en tiempo real todavía).

**DB — Migration 021:**
```sql
CREATE TABLE IF NOT EXISTS driver_positions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  driver_id UUID NOT NULL,
  route_id UUID NOT NULL,
  lat NUMERIC(9,6) NOT NULL,
  lng NUMERIC(9,6) NOT NULL,
  accuracy_m NUMERIC(8,2),
  speed_kmh NUMERIC(6,2),
  heading NUMERIC(5,2),
  recorded_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  FOREIGN KEY (driver_id, tenant_id) REFERENCES drivers(id, tenant_id) ON DELETE CASCADE,
  FOREIGN KEY (route_id, tenant_id) REFERENCES routes(id, tenant_id) ON DELETE CASCADE
);
-- Solo guardamos la última posición consultable eficientemente
CREATE INDEX IF NOT EXISTS idx_driver_positions_driver_recent 
  ON driver_positions(driver_id, recorded_at DESC);
-- Retención: 7 días. Partición o job de limpieza en fase posterior.
```

**Backend:**
- `POST /driver/location` — acepta `{route_id, lat, lng, accuracy_m, speed_kmh, heading, recorded_at}`. Solo callable por driver autenticado con ruta activa. Idempotente por `recorded_at`.
- `GET /routes/{routeId}/driver-position` — devuelve la última posición del driver de esa ruta. Accesible por dispatcher.
- `GET /routes/active-positions` — devuelve última posición de todos los drivers con rutas `in_progress` del tenant. Para fleet view.

**Frontend (PWA conductor):**
- `navigator.geolocation.watchPosition()` con intervalo 30s mientras ruta `in_progress`
- Envío silencioso en background, sin UI visible al conductor
- Solo activo cuando hay ruta en estado `in_progress` asignada al driver

**Frontend (Dispatcher - Mapa):**
- Polling `GET /routes/{routeId}/driver-position` cada 30s en la vista de mapa del bloque A1
- Marcador de camión en posición actual del conductor (diferenciado de marcadores de paradas)

**Tests:**
- Backend: post de posición, consulta de última posición, acceso por driver ajeno (403)

**Definition of done:** El conductor envía posición, el dispatcher ve el camión en el mapa actualizado cada 30s.

---

#### BLOQUE A4 — Smoke Google Route Optimization con evidencia (DEMO-OPT-001)
**Tipo:** DEMO  
**Objetivo:** Cerrar el bloque pendiente de R7. Producir evidencia 200 de optimize con dataset geo-ready.

**Prerequisito:** Dataset con clientes que tengan lat/lng reales. Usar `prepare_google_smoke_dataset.py`.

**Acciones:**
1. Ejecutar `prepare_google_smoke_dataset.py` en el tenant demo
2. Verificar que las órdenes tienen lat/lng en sus clientes
3. Ejecutar smoke con `SMOKE_CREATE_ROUTE=1`
4. Documentar output real (response JSON de Google)

**Definition of done:** Smoke ejecutado con respuesta 200. Output guardado en `docs/evidence/DEMO-OPT-001.json`.

---

### FASE B — Seguimiento operativo en tiempo real

---

#### BLOQUE B1 — WebSocket / SSE para tracking en vivo (REALTIME-001)
**Tipo:** IMPLEMENTATION  
**Objetivo:** El dispatcher ve la posición del conductor y el estado de las paradas actualizarse en tiempo real, sin hacer polling manual.

**Decisión técnica:** Server-Sent Events (SSE) sobre WebSocket. SSE es más simple, unidireccional (server → client), compatible con FastAPI sin dependencias extra, y suficiente para el caso de uso (el cliente no necesita enviar datos por el mismo canal).

**Backend:**
- `GET /routes/{routeId}/stream` — endpoint SSE. Emite eventos cada vez que:
  - Cambia el estado de una parada (stop_status_changed)
  - Llega nueva posición del driver (driver_position_updated)
  - Se reporta una incidencia (incident_reported)
- Formato: `data: {event_type, payload}\n\n`
- Requiere autenticación por query param `?token=<jwt>` (SSE no soporta headers custom en browser)

**Frontend (Dispatcher):**
- `EventSource` conectado al stream de la ruta activa abierta en el mapa
- Actualización reactiva del mapa sin polling

**Tests:**
- Backend: test que el endpoint SSE emite el evento correcto al cambiar estado de stop
- Frontend: mock de EventSource, verificar que el mapa reacciona al evento

**Definition of done:** Dispatcher abre mapa de ruta activa y ve cambios de estado y posición del conductor sin refrescar.

---

#### BLOQUE B2 — ETA dinámica y alerta de retraso (ETA-001)
**Tipo:** IMPLEMENTATION  
**Objetivo:** El sistema calcula la ETA actualizada de cada parada basándose en la posición actual del conductor y emite alerta si se detecta retraso sobre el plan.

**Backend:**
- Nuevo módulo `backend/app/eta/calculator.py`
- `_calculate_eta(current_lat, current_lng, stop_lat, stop_lng, average_speed_kmh=40)` — estimación simple basada en distancia euclidiana + velocidad media. En fases posteriores, sustituir por Google Distance Matrix API.
- `POST /routes/{routeId}/recalculate-eta` — dispara recálculo de ETAs de paradas pendientes. Guarda `estimated_arrival_at` actualizado en `route_stops`. Emite evento SSE `eta_updated`.
- Threshold de alerta: si ETA recalculada supera `estimated_arrival_at` original en > 15 min → crear `RouteEvent` tipo `delay_alert` con metadata.
- `GET /routes/{routeId}/delay-alerts` — lista alertas de retraso de una ruta.

**Frontend:**
- En mapa dispatcher: paradas con retraso detectado muestran icono de alerta
- Banner en `DispatcherRoutingCard` cuando hay delays activos en ruta
- En detalle de parada: ETA original vs ETA actualizada

**Tests:**
- Calculator: test con distancias conocidas
- Backend: post recalculate-eta genera alerts cuando corresponde

---

#### BLOQUE B3 — Chat interno dispatcher ↔ conductor (CHAT-001)
**Tipo:** IMPLEMENTATION  
**Objetivo:** El dispatcher puede enviar mensajes al conductor y viceversa, vinculados a una ruta activa.

**DB — Migration 022:**
```sql
CREATE TABLE IF NOT EXISTS route_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  route_id UUID NOT NULL,
  sender_id UUID NOT NULL,
  sender_role TEXT NOT NULL CHECK (sender_role IN ('dispatcher', 'driver')),
  body TEXT NOT NULL,
  sent_at TIMESTAMPTZ NOT NULL,
  read_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL,
  FOREIGN KEY (route_id, tenant_id) REFERENCES routes(id, tenant_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_route_messages_route ON route_messages(route_id, sent_at DESC);
```

**Backend:**
- `POST /routes/{routeId}/messages` — enviar mensaje. Actor: dispatcher o driver autenticado.
- `GET /routes/{routeId}/messages` — listar mensajes de la ruta (paginado).
- `POST /routes/{routeId}/messages/{messageId}/read` — marcar como leído.
- SSE (B1): añadir evento `message_sent` al stream de la ruta.

**Frontend:**
- Dispatcher: panel de chat en sidebar del detalle de ruta
- Conductor (PWA): panel de mensajes en `DriverRoutingCard`, notificación de mensaje nuevo

---

#### BLOQUE B4 — Modificación de ruta en vivo desde dispatcher (LIVE-EDIT-001)
**Tipo:** IMPLEMENTATION  
**Objetivo:** El dispatcher puede reordenar paradas y mover stops entre rutas desde el mapa, con el conductor viendo los cambios en tiempo real.

**Backend:** `POST /routes/{routeId}/move-stop` ya existe. Añadir:
- `POST /routes/{routeId}/reorder-stops` — acepta nuevo orden de sequence_numbers. Recalcula ETAs. Emite SSE `route_reordered`.
- SSE emite `stop_moved` cuando move-stop o reorder ocurre.

**Frontend (Dispatcher):**
- En mapa: drag-and-drop de marcadores para reordenar (o lista ordenable junto al mapa)
- Botón "Aplicar nuevo orden" → confirma y llama reorder-stops

**Frontend (Conductor):**
- SSE en DriverRoutingCard: cuando `route_reordered` llega, refrescar listado de paradas automáticamente con indicación visual de cambio

---

### FASE C — Trazabilidad completa de la entrega

---

#### BLOQUE C1 — Devoluciones estructuradas (RETURNS-001)
**Tipo:** IMPLEMENTATION  
**Objetivo:** El conductor registra devoluciones con tipo, cantidad y motivo formal. El dispatcher las ve en el panel y en informes.

**DB — Migration 023:**
```sql
CREATE TABLE IF NOT EXISTS stop_returns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  route_stop_id UUID NOT NULL,
  route_id UUID NOT NULL,
  driver_id UUID NOT NULL,
  sku TEXT,
  product_name TEXT,
  qty NUMERIC(14,3) NOT NULL,
  return_reason TEXT NOT NULL CHECK (return_reason IN (
    'customer_absent', 'customer_rejected', 'damaged', 'wrong_product', 'expired', 'other'
  )),
  notes TEXT,
  recorded_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  FOREIGN KEY (route_stop_id, tenant_id) REFERENCES route_stops(id, tenant_id) ON DELETE CASCADE
);
```

**Backend:**
- `POST /stops/{stopId}/returns` — registrar devolución. Emite `RouteEvent` tipo `return_recorded`.
- `GET /stops/{stopId}/returns` — listar devoluciones de una parada.
- `GET /routes/{routeId}/returns` — todas las devoluciones de una ruta.

**Frontend (Conductor):**
- En flujo "Completar parada": sección opcional "Registrar devolución" con form: SKU/producto, cantidad, motivo.
- Permite múltiples devoluciones por parada.

**Frontend (Dispatcher):**
- Indicador visual en paradas con devoluciones (icono de caja)
- Panel de devoluciones de la ruta

---

#### BLOQUE C2 — Control de cobro en parada (PAYMENT-001)
**Tipo:** IMPLEMENTATION  
**Objetivo:** El conductor registra si cobró en efectivo o si el pago queda pendiente, vinculado a cada parada.

**DB — Migration 024:**
```sql
DO $$ BEGIN
  ALTER TABLE route_stops ADD COLUMN payment_status TEXT 
    CHECK (payment_status IN ('not_applicable', 'collected_cash', 'pending', 'credit'));
  ALTER TABLE route_stops ADD COLUMN payment_amount NUMERIC(14,2);
  ALTER TABLE route_stops ADD COLUMN payment_notes TEXT;
  ALTER TABLE route_stops ADD COLUMN payment_recorded_at TIMESTAMPTZ;
EXCEPTION WHEN duplicate_column THEN NULL; END $$;
```

**Backend:**
- `POST /stops/{stopId}/payment` — registrar estado de cobro. Actor: driver. Callable en estado `arrived` o `completed`.

**Frontend (Conductor):**
- En flujo completar parada: selector "Cobro" con opciones: No aplica / Cobrado en efectivo (+ importe) / Pendiente / Crédito

---

#### BLOQUE C3 — Actualización de datos del cliente por conductor (CLIENT-UPDATE-001)
**Tipo:** IMPLEMENTATION  
**Objetivo:** El conductor puede corregir el horario o teléfono de un cliente directamente desde la app durante el reparto. El cambio se guarda como sugerencia y se aplica en el perfil del cliente.

**Backend:**
- `POST /stops/{stopId}/client-update` — acepta `{field: 'window_start'|'window_end'|'phone', value}`. Guarda la sugerencia en `customer_operational_profiles` o en tabla de sugerencias pendientes de validación por admin.
- Decision: aplicar directamente a `CustomerOperationalProfile.window_start/window_end` con log de auditoría, o crear tabla `client_update_suggestions`. Recomendado: aplicar directamente + log.

**Frontend (Conductor):**
- En detalle de parada: "Actualizar horario" → form con hora apertura/cierre del cliente
- Botón "Actualizar teléfono"

---

### FASE D — Notificaciones y visibilidad externa

---

#### BLOQUE D1 — Notificación de ETA por email al cliente (NOTIFY-EMAIL-001)
**Tipo:** IMPLEMENTATION  
**Objetivo:** Cuando una ruta se despacha, el sistema envía un email a cada cliente con la ETA estimada de su entrega. Cuando la entrega se completa, envía confirmación con link al albarán.

**Prerequisito:** Credencial SMTP (SendGrid recomendado, o cualquier SMTP). Variable de entorno `SENDGRID_API_KEY` o `SMTP_*`.

**DB — Migration 025:**
```sql
CREATE TABLE IF NOT EXISTS notification_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  entity_type TEXT NOT NULL,  -- 'route_stop', 'route'
  entity_id UUID NOT NULL,
  channel TEXT NOT NULL,      -- 'email', 'whatsapp', 'sms'
  recipient TEXT NOT NULL,
  template TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('sent', 'failed', 'skipped')),
  provider_response TEXT,
  sent_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);
```

**Backend:**
- Nuevo módulo `backend/app/notifications/email.py`
- `send_eta_notification(customer, stop)` — enviado al despachar ruta
- `send_delivery_confirmation(customer, stop, proof)` — enviado al completar parada
- Hook en `POST /routes/{routeId}/dispatch` → disparar emails de ETA
- Hook en `POST /stops/{stopId}/complete` → disparar email de confirmación

**Frontend (Admin):**
- Configuración de tenant: activar/desactivar notificaciones por email, plantilla personalizable

---

#### BLOQUE D2 — Notificaciones WhatsApp (NOTIFY-WA-001)
**Tipo:** IMPLEMENTATION  
**Objetivo:** Enviar mensajes WhatsApp al cliente sobre estado del pedido, ETA y confirmación de entrega, usando Twilio WhatsApp Business API.

**Prerequisito:** Cuenta Twilio, número WhatsApp Business aprobado. Variable `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`.

**Backend:**
- Nuevo módulo `backend/app/notifications/whatsapp.py`
- Templates: `eta_preview`, `delivery_confirmed`, `incident_alert`, `delay_warning`
- Mismos hooks que D1 + hook en `delay_alert` de ETA-001

**Frontend (Admin):**
- Toggle por tenant: WhatsApp activado/desactivado
- Campo en perfil de cliente: `whatsapp_number` (si difiere del teléfono principal)

---

#### BLOQUE D3 — Portal de tracking para cliente final (TRACKING-001)
**Tipo:** IMPLEMENTATION  
**Objetivo:** Cada pedido tiene un link público de tracking que el cliente puede abrir en el navegador para ver el estado de su entrega y la posición aproximada del conductor.

**Backend:**
- `GET /public/track/{token}` — endpoint público (sin auth JWT). El `token` es un JWT de un solo uso con `{order_id, tenant_id, exp}` generado al despachar la ruta.
- Devuelve: estado de la parada, ETA, posición del conductor (con resolución reducida a 1km para privacidad), nombre del conductor.
- `POST /routes/{routeId}/dispatch` → genera tokens y los guarda en `route_stops.tracking_token`.

**Frontend:**
- Nueva página `frontend/app/track/[token]/page.tsx` — pública, sin login
- Mapa con posición aproximada del conductor
- Estado de la entrega (en camino / entregado / fallido)
- ETA actualizada

---

### FASE E — Métricas, informes y control de costes

---

#### BLOQUE E1 — Métricas operativas por cliente y conductor (METRICS-001)
**Tipo:** IMPLEMENTATION  
**Objetivo:** Panel de métricas con datos reales de operación: cumplimiento por cliente, retrasos, devoluciones por conductor, rutas completadas vs fallidas.

**Backend:**
- `GET /metrics/customers` — por cliente: total entregas, tasa éxito, retrasos, devoluciones, tiempo medio de servicio. Filtros: `date_from`, `date_to`, `zone_id`.
- `GET /metrics/drivers` — por conductor: rutas completadas, paradas/día, incidencias, tiempo medio por parada.
- `GET /metrics/routes` — por ruta: km planificados vs reales (cuando tengamos GPS), tiempo planificado vs real, paradas completadas/fallidas/skipped.
- Estos endpoints hacen queries sobre tablas existentes (`route_stops`, `routes`, `incidents`, `stop_returns`).

**Frontend:**
- Nuevo tab "Métricas" en la navegación principal
- Tarjetas KPI + tabla por cliente/conductor con filtros de fecha
- Exportar a CSV

---

#### BLOQUE E2 — Informe de ruta y envío a comerciales (REPORTS-001)
**Tipo:** IMPLEMENTATION  
**Objetivo:** Al cerrar una ruta, el sistema genera automáticamente un informe en PDF con el resumen de la operación y lo envía por email a los usuarios con rol `office`.

**Backend:**
- `GET /routes/{routeId}/report` — genera informe de ruta en JSON (paradas, estados, tiempos, incidencias, devoluciones, cobros).
- `GET /routes/{routeId}/report/pdf` — genera y descarga PDF del informe. Usar `reportlab` o `weasyprint`.
- Hook en `route_completed` → enviar PDF por email a usuarios `office` del tenant.

**Frontend:**
- Botón "Descargar informe" en detalle de ruta cerrada
- Vista previa del informe antes de descargar

---

#### BLOQUE E3 — Control de costes por ruta (COSTS-001)
**Tipo:** IMPLEMENTATION  
**Objetivo:** Registrar y visualizar costes operativos por ruta: combustible, tiempo de conductor, coste estimado por km.

**DB — Migration 026:**
```sql
CREATE TABLE IF NOT EXISTS route_costs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  route_id UUID NOT NULL,
  cost_type TEXT NOT NULL CHECK (cost_type IN ('fuel', 'driver_time', 'vehicle', 'tolls', 'other')),
  amount NUMERIC(14,2) NOT NULL,
  currency TEXT NOT NULL DEFAULT 'EUR',
  notes TEXT,
  recorded_by UUID,
  recorded_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  FOREIGN KEY (route_id, tenant_id) REFERENCES routes(id, tenant_id) ON DELETE CASCADE
);
```

**Backend:**
- `POST /routes/{routeId}/costs` — registrar coste. Actor: logistics o admin.
- `GET /routes/{routeId}/costs` — listar costes de una ruta.
- `GET /metrics/costs` — resumen de costes por fecha, zona, vehículo, conductor.

**Frontend:**
- En detalle de ruta: sección "Costes" con form de registro y resumen
- En métricas: panel de costes con gráficas de evolución

---

#### BLOQUE E4 — Análisis IA: detección de anomalías y recomendaciones (AI-001)
**Tipo:** IMPLEMENTATION  
**Objetivo:** Analizar datos históricos para detectar patrones anómalos (cliente con retrasos repetidos, ruta ineficiente, conductor con alta tasa de fallos) y generar recomendaciones.

**Prerequisito:** Mínimo 30 días de datos operativos reales. No implementar antes.

**Backend:**
- `GET /analytics/anomalies` — detecta: clientes con retrasos > umbral en últimas 4 semanas, conductores con tasa de fallo > 10%, rutas con km > 20% sobre la media de zona.
- `GET /analytics/recommendations` — sugiere: mover cliente X a ruta Y (por proximidad + historial), ajustar hora de salida de ruta Z (por historial de retrasos en primer tramo).
- Implementación inicial: SQL analítico puro sobre tablas existentes, sin modelos ML. Los modelos ML vienen en una fase posterior cuando haya suficientes datos.

**Frontend:**
- Panel "Alertas de inteligencia" en dashboard del dispatcher
- Cards de recomendación con botón "Aplicar" (llama a endpoint de acción correspondiente)

---

### FASE F — Planificador avanzado (constraints completos)

---

#### BLOQUE F1 — Time windows por cliente en optimizer (TW-001)
**Tipo:** IMPLEMENTATION  
**Objetivo:** El optimizer de Google recibe las franjas horarias de entrega de cada cliente (`window_start`/`window_end` de `CustomerOperationalProfile`) y las respeta en la optimización.

**Backend:** `CustomerOperationalProfile.window_start/window_end` ya existe en DB.
- Modificar `GoogleRouteOptimizationProvider._build_shipments()` para incluir `timeWindows` por parada cuando el cliente tenga perfil con ventana definida.

**Tests:**
- Test unitario: verificar que el payload a Google incluye `timeWindows` cuando el perfil tiene ventana.

---

#### BLOQUE F2 — Capacidad de vehículo en optimizer (CAPACITY-001)
**Tipo:** IMPLEMENTATION  
**Objetivo:** El optimizer respeta la capacidad de carga del vehículo (`vehicles.capacity_kg`) y el peso de los pedidos (`orders.total_weight_kg`).

**Backend:**
- `Vehicle.capacity_kg` ya existe.
- `Order.total_weight_kg` ya existe.
- Modificar `GoogleRouteOptimizationProvider` para incluir `loadLimits` en el vehículo y `loadDemands` por parada.

---

#### BLOQUE F3 — Multi-vehicle en un plan (MULTIVEHICLE-001)
**Tipo:** IMPLEMENTATION  
**Objetivo:** Un plan puede tener múltiples rutas (múltiples vehículos). El dispatcher gestiona y visualiza todas en el mapa simultáneamente.

**DB:** El modelo ya soporta múltiples routes por plan. La limitación es en UI.

**Frontend:**
- Fleet view: mapa con TODAS las rutas activas del día, conductores con colores distintos por ruta
- `GET /routes/active-positions` (creado en A3) alimenta este mapa

---

#### BLOQUE F4 — Doble viaje por jornada (DOUBLE-TRIP-001)
**Tipo:** IMPLEMENTATION  
**Objetivo:** Un conductor puede completar dos rutas en una misma jornada (mañana + tarde), con recarga en depósito entre viajes. El optimizer planifica ambos viajes respetando tiempos de descanso y ventana horaria de cada tramo.

**Origen:** Mind map logística — "Soporte doble viaje por jornada"

**DB — Migration 028:**
```sql
DO $$ BEGIN
  ALTER TABLE routes ADD COLUMN trip_number SMALLINT NOT NULL DEFAULT 1
    CHECK (trip_number IN (1, 2));
  ALTER TABLE routes ADD COLUMN reload_at TIMESTAMPTZ;
EXCEPTION WHEN duplicate_column THEN NULL; END $$;
```

**Backend:**
- `Route.trip_number` (1 o 2) identifica el tramo dentro de la jornada del conductor.
- `Route.reload_at` — hora estimada de regreso a depósito para recarga entre viajes.
- `POST /routes/plan` — acepta parámetro `trip_number` (default 1). Validar que el conductor no tenga ya dos rutas en el mismo día del mismo tenant.
- `GET /routes/{routeId}/reload-window` — devuelve la ventana disponible para el segundo viaje (después de `reload_at` + tiempo de carga estándar del tenant).
- Optimizer (F1-F2): cuando hay doble viaje, enviar dos vehículos lógicos al payload de Google con sus `startTimeWindows` diferenciados.

**Frontend (Dispatcher):**
- Al planificar: toggle "Segundo viaje" en el formulario de ruta, con selector de hora de inicio del tramo 2.
- Vista de ruta: badge "Viaje 1 / 2" junto al nombre del conductor.
- Timeline de jornada: bloque visual con viaje 1 → recarga → viaje 2.

**Tests:**
- Backend: dos rutas mismo conductor mismo día → segunda crea con `trip_number=2`; tercera → 409.
- Backend: conductor con `trip_number=2` respeta `startTimeWindow` posterior a recarga.

**Definition of done:** Dispatcher puede planificar dos rutas para un conductor en la misma jornada con ventanas horarias diferenciadas; el optimizer las trata como vehículos distintos con restricciones de tiempo correctas.

---

#### BLOQUE F5 — Restricciones ADR: materiales peligrosos (ADR-001)
**Tipo:** IMPLEMENTATION  
**Objetivo:** Los pedidos que contienen materiales peligrosos (clase ADR) solo pueden asignarse a vehículos con certificación ADR. El optimizer no asigna pedidos ADR a vehículos no habilitados.

**Origen:** Mind map logística — "Restricciones ADR · materiales peligrosos"

**DB — Migration 029:**
```sql
-- Pedido con carga ADR
DO $$ BEGIN
  ALTER TABLE orders ADD COLUMN is_adr BOOLEAN NOT NULL DEFAULT FALSE;
  ALTER TABLE orders ADD COLUMN adr_class TEXT;  -- e.g. '3', '8', '9' (clases ADR EU)
EXCEPTION WHEN duplicate_column THEN NULL; END $$;

-- Vehículo habilitado para ADR
DO $$ BEGIN
  ALTER TABLE vehicles ADD COLUMN has_adr_cert BOOLEAN NOT NULL DEFAULT FALSE;
  ALTER TABLE vehicles ADD COLUMN adr_cert_expiry DATE;
EXCEPTION WHEN duplicate_column THEN NULL; END $$;
```

**Backend:**
- `Order.is_adr`, `Order.adr_class` — marcado al ingerir el pedido (o editable por admin).
- `Vehicle.has_adr_cert`, `Vehicle.adr_cert_expiry` — gestionable desde admin de vehículos.
- `POST /routes/plan` — validar: si algún pedido de la ruta es ADR, el vehículo asignado debe tener `has_adr_cert=true` y certificado vigente. Error: `VEHICLE_ADR_REQUIRED`.
- `POST /routes/{routeId}/optimize` — el provider excluye automáticamente paradas ADR de vehículos sin certificación. Si todas las paradas ADR quedan sin vehículo válido → error `ADR_VEHICLE_NOT_AVAILABLE`.

**Frontend (Admin):**
- Vehículos: campo "Certificación ADR" + fecha de caducidad.
- Órdenes: badge ADR con clase en listados de pedidos y colas.

**Frontend (Dispatcher):**
- Al planificar: alerta visual si se intenta asignar pedidos ADR a vehículo sin certificación.
- En detalle de ruta: banner "Ruta con carga ADR" si alguna parada tiene `is_adr=true`.

**Tests:**
- Backend: plan con pedido ADR + vehículo sin cert → 409 VEHICLE_ADR_REQUIRED.
- Backend: plan con pedido ADR + vehículo con cert vigente → 201.
- Backend: plan con vehículo con cert caducada → 409.

---

#### BLOQUE F6 — Restricciones ZBE: Zona de Bajas Emisiones Palma (ZBE-001)
**Tipo:** IMPLEMENTATION  
**Objetivo:** Los vehículos sin etiqueta ambiental suficiente no pueden entrar en la ZBE de Palma de Mallorca. El optimizer evita asignar paradas dentro de la ZBE a vehículos no habilitados, o alerta al dispatcher cuando no hay alternativa.

**Origen:** Mind map logística — "Restricciones ZBE · Palma ciudad"

**Contexto:** La ZBE de Palma (Zona de Bajas Emisiones, en vigor desde 2023) restringe el acceso de vehículos diésel anteriores a Euro 6 y gasolina anteriores a Euro 4 en el núcleo urbano. Referencia: Ajuntament de Palma, Ordenança de Mobilitat Urbana Sostenible.

**DB — Migration 030:**
```sql
-- Clasificación ambiental del vehículo
DO $$ BEGIN
  ALTER TABLE vehicles ADD COLUMN emission_label TEXT
    CHECK (emission_label IN ('zero', 'eco', 'c', 'b', 'none'));
  ALTER TABLE vehicles ADD COLUMN can_enter_zbe BOOLEAN GENERATED ALWAYS AS
    (emission_label IN ('zero', 'eco', 'c')) STORED;
EXCEPTION WHEN duplicate_column THEN NULL; END $$;

-- Cliente o zona marcada como dentro de ZBE
DO $$ BEGIN
  ALTER TABLE customers ADD COLUMN in_zbe BOOLEAN NOT NULL DEFAULT FALSE;
EXCEPTION WHEN duplicate_column THEN NULL; END $$;
```

**Backend:**
- `Vehicle.emission_label` — etiqueta DGT: `zero`, `eco`, `c`, `b`, `none`.
- `Vehicle.can_enter_zbe` — columna generada: solo `zero`, `eco`, `c` pueden entrar.
- `Customer.in_zbe` — marcado manual por admin, o determinado por bounding box geográfico de la ZBE de Palma (implementación futura).
- `POST /routes/plan` — advertencia (no bloqueante en v1): si la ruta tiene paradas `in_zbe=true` y el vehículo tiene `can_enter_zbe=false` → incluir `warnings: ['ZBE_RESTRICTION']` en la respuesta.
- `POST /routes/{routeId}/optimize` — el provider pasa `routeModifiers.avoidTolls=false` pero añade nota de ZBE en el resultado. En v2: usar `avoid_indoor` o zonas de exclusión de Google Route Optimization cuando la API lo soporte.

**Frontend (Admin):**
- Vehículos: selector de etiqueta ambiental con colores DGT (verde = zero/eco, amarillo = c, naranja = b, sin etiqueta = gris).
- Clientes: toggle "Dentro de ZBE" en ficha de cliente.

**Frontend (Dispatcher):**
- Al planificar o despachar: alerta si hay conflicto ZBE. El dispatcher puede confirmar igualmente (v1 es warning, no bloqueo).
- En detalle de parada: icono ZBE si `customer.in_zbe=true`.

**Tests:**
- Backend: plan con parada ZBE + vehículo `can_enter_zbe=false` → respuesta 201 con `warnings: ['ZBE_RESTRICTION']`.
- Backend: plan con parada ZBE + vehículo `emission_label='zero'` → sin warnings.

---

### FASE G — Automatización de planificación

---

#### BLOQUE G1 — Scheduler: rutas generadas antes de las 9am (SCHEDULER-001)
**Tipo:** IMPLEMENTATION  
**Objetivo:** El sistema genera automáticamente el plan del día cada mañana a una hora configurable (default 7:30am), tomando todos los pedidos `ready_to_dispatch` para la fecha de servicio, asignándolos a vehículos disponibles según zona, y lanzando optimize. El encargado llega a las 9am y encuentra las rutas listas para revisar y aprobar.

**Origen:** Mind map logística — "Rutas listas antes de las 9am" + "Enc. rutas revisa y aprueba"

**Prerequisito técnico:** Celery + Redis, o APScheduler dentro del proceso FastAPI. Recomendado para v1: APScheduler (sin infraestructura adicional). Para producción: Celery + Redis (más robusto).

**DB — Migration 031:**
```sql
CREATE TABLE IF NOT EXISTS schedule_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  job_type TEXT NOT NULL CHECK (job_type IN ('daily_planning', 'eta_recalc', 'report_send')),
  scheduled_time TIME NOT NULL DEFAULT '07:30',
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  last_run_at TIMESTAMPTZ,
  last_run_status TEXT CHECK (last_run_status IN ('ok', 'partial', 'failed')),
  last_run_summary JSONB,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_schedule_jobs_tenant ON schedule_jobs(tenant_id, job_type);
```

**Backend:**
- Módulo `backend/app/scheduler/daily_planning.py`:
  - `run_daily_planning(tenant_id, service_date)` — función pura ejecutable manual o vía scheduler.
  - Pasos: 1) obtener pedidos `ready_to_dispatch` para `service_date`; 2) agrupar por zona; 3) asignar a vehículos disponibles (mismo algoritmo que `POST /routes/plan` existente); 4) llamar a `optimize` por cada ruta creada; 5) registrar resultado en `schedule_jobs.last_run_summary`.
- `POST /scheduler/run-now` — disparo manual desde el dispatcher. Útil para re-ejecutar si algo falló.
- `GET /scheduler/jobs` — listar jobs configurados del tenant.
- `PATCH /scheduler/jobs/{jobId}` — configurar hora de ejecución, activar/desactivar.
- APScheduler integrado en `lifespan` de FastAPI: carga los jobs activos al arrancar y los programa.

**Frontend (Admin / Dispatcher):**
- Panel "Automatización" en configuración del tenant:
  - Toggle "Planificación automática" ON/OFF.
  - Selector de hora de ejecución.
  - Historial de ejecuciones con resultado y resumen (cuántas rutas creadas, cuántos pedidos asignados, errores).
- Botón "Ejecutar ahora" para disparo manual.
- Al llegar el dispatcher a las 9am: las rutas aparecen en estado `draft`, listas para revisar, aprobar y despachar con un clic.

**Tests:**
- Backend: `run_daily_planning` con pedidos existentes → crea rutas y las optimiza (mock provider).
- Backend: sin pedidos → resultado vacío, no crea rutas.
- Backend: scheduler job desactivado → `run_daily_planning` no se ejecuta automáticamente.

**Definition of done:** Con el scheduler activo, al llegar el encargado a las 9am encuentra las rutas del día creadas, optimizadas y listas para aprobar en el panel dispatcher.

---

## Prerequisitos técnicos globales

| Prerequisito | Bloque que lo necesita | Acción |
|---|---|---|
| Google Maps JS API Key (Maps JavaScript API activada) | A1, A3, B1, D3 | Crear API Key en GCP, variable `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` |
| `@googlemaps/react-wrapper` o `@vis.gl/react-google-maps` | A1 | `npm install @vis.gl/react-google-maps` |
| `react-signature-canvas` | A2 | `npm install react-signature-canvas` |
| Almacenamiento de imágenes (fase posterior para fotos) | A2 (fotos) | S3 / Google Cloud Storage |
| SSE nativo en FastAPI | B1 | `from fastapi.responses import StreamingResponse` — nativo, sin deps |
| SendGrid o SMTP | D1 | `pip install sendgrid` |
| Twilio WhatsApp | D2 | `pip install twilio` |
| WeasyPrint o ReportLab | E2 | `pip install weasyprint` |
| Mínimo 30 días de datos reales | E4 | Operación real del sistema |
| APScheduler (v1 scheduler) | G1 | `pip install apscheduler` |
| Celery + Redis (v2 scheduler, producción) | G1 | Infraestructura adicional — posponer |

---

## Migraciones DB en orden

| Migración | Bloque | Contenido |
|---|---|---|
| 020 | A2 | `stop_proofs` |
| 021 | A3 | `driver_positions` |
| 022 | B3 | `route_messages` |
| 023 | C1 | `stop_returns` |
| 024 | C2 | Columnas de cobro en `route_stops` |
| 025 | D1 | `notification_log` |
| 026 | E3 | `route_costs` |
| 027 | D3 | `tracking_token` en `route_stops` |
| 028 | F4 | `trip_number`, `reload_at` en `routes` |
| 029 | F5 | `is_adr`, `adr_class` en `orders`; `has_adr_cert`, `adr_cert_expiry` en `vehicles` |
| 030 | F6 | `emission_label`, `can_enter_zbe` en `vehicles`; `in_zbe` en `customers` |
| 031 | G1 | `schedule_jobs` |

---

## Orden de ejecución recomendado

```
A4 → A1 → A2 → A3 → B1 → B2 → F1 → F2 → F4 → F5 → F6 → B3 → B4 → C1 → C2 → C3 → D1 → D2 → D3 → E1 → E2 → E3 → F3 → G1 → E4
```

Justificación del orden:
- A4 primero: cierra deuda técnica de R7 y valida que Google Optimize funciona antes de construir UI sobre él
- A1-A3: el mapa es el cambio más visible y desbloquea todas las demos
- B1-B2: el tiempo real sobre el mapa ya construido
- F1-F2: mejoran el optimizer, no requieren UI nueva
- F4-F6: constraints de operación real (doble viaje, ADR, ZBE) — van después de tener el optimizer validado
- C1-C3: trazabilidad completa de la entrega, natural siguiente a la PWA del conductor
- D1-D3: notificaciones externas, requieren C terminado (necesitan que haya proof y estado real)
- E: métricas e informes, requieren datos reales acumulados de A-D
- G1 (scheduler) después de E1: la automatización tiene sentido cuando ya hay métricas que confirman que la planificación manual funciona bien

---

## Capacidades demostrables al completar cada fase

| Al terminar | Se puede demostrar |
|---|---|
| Fase A | Mapa con paradas, firma digital, conductor visible en mapa, optimize con evidencia |
| Fase B | Tracking en tiempo real, ETA dinámica, chat, modificar ruta en vivo |
| Fase C | Devoluciones, cobros, actualización de datos de cliente |
| Fase D | Cliente recibe ETA por email/WhatsApp, portal de tracking |
| Fase E | Panel de métricas, informes PDF, control de costes, alertas IA |
| Fase F | Optimizer con time windows + capacidad + múltiples vehículos + doble viaje + ADR + ZBE |
| Fase G | Planificación automática: encargado llega a las 9am y las rutas están listas para aprobar |

---

## Lo que NO entra en este plan

- Integración con ERP de terceros (Telynet, SAP, Sage, etc.) — requiere análisis específico por ERP
- Venta de terminales / MDM — hardware, fuera del scope de software
- Hub de tacógrafos / sensores de temperatura — requiere hardware y protocolos específicos
- App nativa iOS/Android — la PWA es el objetivo; app nativa es una fase posterior
