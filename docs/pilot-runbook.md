# Runbook de piloto — CorteCero / Kelko Route Optimizer

**PILOT-HARDEN-001** · Documento operativo. No es documentación de producto.

Audiencia: operador técnico ejecutando la primera validación real en entorno de piloto.

---

## Paso 1 — Preparar el conductor

El conductor necesita una cuenta de acceso (User) y una ficha operativa (Driver) vinculada.

### 1a. Crear la cuenta de acceso (User con role=driver)

```http
POST /admin/users
Authorization: Bearer {admin_token}
Content-Type: application/json

{
  "email": "conductor@ejemplo.com",
  "full_name": "Nombre Conductor",
  "password": "password-seguro",
  "role": "driver",
  "is_active": true
}
```

Anotar el `id` del User creado → `USER_ID`.

### 1b. Crear la ficha operativa (Driver) y vincularla

```http
POST /drivers
Authorization: Bearer {logistics_token}
Content-Type: application/json

{
  "name": "Nombre Conductor",
  "phone": "+34600000001",
  "vehicle_id": "UUID_DEL_VEHICULO"
}
```

Anotar el `id` del Driver creado → `DRIVER_ID`.

### 1c. Vincular Driver con User (operación directa en BD)

> La API actual no expone `user_id` en `PATCH /drivers`. El vínculo se establece directamente:

```sql
UPDATE drivers
SET user_id = 'USER_ID'
WHERE id = 'DRIVER_ID' AND tenant_id = 'TENANT_ID';
```

Verificar: `SELECT id, user_id, name FROM drivers WHERE id = 'DRIVER_ID';`

---

## Paso 2 — Verificar cliente con coordenadas

Los clientes deben tener `lat`, `lng`, y `delivery_address` para que la optimización
Google use rutas reales. Sin coordenadas, el optimizador usa orden original.

```http
GET /admin/customers/{customer_id}
Authorization: Bearer {admin_token}
```

Verificar que `lat` y `lng` no sean `null`. Si son `null`:

```http
PATCH /admin/customers/{customer_id}
Authorization: Bearer {admin_token}
Content-Type: application/json

{
  "lat": 39.5714,
  "lng": 2.6533,
  "delivery_address": "Carrer de la Pau 5, 07001 Palma"
}
```

---

## Paso 3 — Crear ruta

### 3a. Listar pedidos listos para asignar

```http
GET /orders/ready-to-dispatch?service_date=YYYY-MM-DD
Authorization: Bearer {logistics_token}
```

### 3b. Listar vehículos disponibles

```http
GET /vehicles/available?service_date=YYYY-MM-DD
Authorization: Bearer {logistics_token}
```

### 3c. Planificar ruta

```http
POST /routes/plan
Authorization: Bearer {logistics_token}
Content-Type: application/json

{
  "plan_id": "UUID_DEL_PLAN",
  "routes": [
    {
      "vehicle_id": "UUID_VEHICULO",
      "driver_id": "DRIVER_ID",
      "order_ids": ["UUID_ORDER_1", "UUID_ORDER_2"]
    }
  ]
}
```

Anotar el `id` de la ruta creada → `ROUTE_ID`.

---

## Paso 4 — Optimizar

```http
POST /routes/{ROUTE_ID}/optimize
Authorization: Bearer {logistics_token}
```

Si `GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID` está configurado → llamada real a Google API.
Si está vacío → mock (orden original, sin optimización).

Verificar que `optimization_request_id` no sea null en la respuesta para confirmar llamada real.

---

## Paso 5 — Despachar

```http
POST /routes/{ROUTE_ID}/dispatch
Authorization: Bearer {logistics_token}
```

El estado de la ruta pasa a `dispatched`. El conductor ya puede verla en la PWA.

---

## Paso 6 — Ejecutar desde driver PWA

El conductor abre la PWA (`/`), se autentica con las credenciales del Paso 1.

Flujo en PWA:

1. Seleccionar ruta del día en "Mis rutas de hoy"
2. Ver "Siguiente parada" con datos de la primera parada pendiente
3. En cada parada:
   - Pulsar **Llegar** al acercarse al punto (`POST /stops/{stop_id}/arrive`)
   - Pulsar **Completar** al entregar (`POST /stops/{stop_id}/complete`)
   - O **Fallar** si no se puede entregar (campo de razón obligatorio)
   - O **Omitir** si se reordena en campo

La ruta avanza automáticamente al estado `in_progress` en la primera acción del conductor.

---

## Paso 7 — Registrar incidencia

Si surge un problema durante la ejecución:

```http
POST /incidents
Authorization: Bearer {driver_token}
Content-Type: application/json

{
  "route_id": "ROUTE_ID",
  "route_stop_id": "STOP_ID",
  "type": "customer_absent",
  "severity": "medium",
  "description": "Cliente no encontrado en dirección. Vecino confirma que salió."
}
```

Tipos válidos: `access_blocked`, `customer_absent`, `customer_rejected`,
`vehicle_issue`, `wrong_address`, `damaged_goods`, `other`.

---

## Paso 8 — Revisar resultado

### Estado final de la ruta

```http
GET /routes/{ROUTE_ID}
Authorization: Bearer {logistics_token}
```

Verificar:
- `status: "completed"` cuando todas las paradas son terminales
- Timestamps de cada parada (`arrived_at`, `completed_at`, `failed_at`)

### Incidencias registradas

```http
GET /incidents?route_id={ROUTE_ID}
Authorization: Bearer {logistics_token}
```

### Log de eventos

```http
GET /routes/{ROUTE_ID}/events
Authorization: Bearer {logistics_token}
```

El log es append-only. Muestra secuencia completa de acciones con actor y timestamp.

---

## Indicadores de éxito del piloto

| Indicador | Verificación |
|-----------|-------------|
| Driver puede autenticarse | JWT con role=driver devuelto por `/auth/login` |
| Driver ve sus rutas | `GET /driver/routes` retorna rutas asignadas |
| Driver ejecuta paradas | `arrive → complete` sin 4xx |
| Incidencia registrada | `POST /incidents` → 201 |
| Ruta completada | `route.status == "completed"` |
| Tenant isolation | Driver de otro tenant → 404 en paradas ajenas |
| Sin datos reales en repo | `git grep -i "password\|secret\|credential" -- .env*` sin resultados |
