# CorteCero — Dominio operativo

## Entidades core

| Entidad | Descripción |
|---------|-------------|
| `Tenant` | Empresa distribuidora. Todo está scoped a tenant. |
| `User` | Usuario del sistema. Roles: admin, logistics, office, driver |
| `Driver` | Perfil de conductor. Vinculado a User via `user_id` (FK explícita desde migration 018) |
| `Vehicle` | Vehículo de reparto. Asociado a zona/plan |
| `Zone` | Zona geográfica de reparto con cut-off propio |
| `Customer` | Cliente receptor de pedidos. Tiene perfil operativo y excepciones |
| `Order` | Pedido a entregar. Tiene `service_date`, `zone_id`, estado operativo |
| `Plan` | Plan diario por zona/fecha. Estados: draft → locked |
| `Route` | Ruta asignada a un vehículo/conductor para una fecha. Estados: draft → planned → dispatched → completed |
| `RouteStop` | Parada dentro de una ruta. Vinculada a Order |
| `ExceptionItem` | Pedido tardío o problemático gestionado fuera del flujo normal |
| `AuditEvent` | Evento inmutable de auditoría |

## Flujo operativo core

```
Ingestión de pedido
    → Cola pendiente (pending-queue)
    → Evaluación operativa
    → Cola operativa (operational-queue) o excepciones
    → Planificación (Plan por zona/fecha)
    → Lock del plan
    → Creación de ruta (Route + RouteStops)
    → Optimización (Google Route Optimization)
    → Despacho al conductor (dispatched)
    → Ejecución: arrive → complete/fail/skip
    → Incidencias en ruta
```

## Semántica de cut-off

Un pedido es **tardío** si: `created_at > effective_cutoff_at`

`effective_cutoff_at` se resuelve por prioridad:
1. Override de cliente
2. Cut-off de zona
3. Cut-off por defecto del tenant

## Invariantes de dominio

- Todo pedido pertenece a exactamente un tenant
- Un plan es por (tenant, zone_id, service_date) único
- Un plan locked no acepta pedidos sin excepción aprobada
- Una ruta es por (plan_id, vehicle_id)
- Los eventos de auditoría son append-only, nunca modificables
- El conductor solo ve y actúa sobre sus rutas asignadas

## Nomenclatura

- **CorteCero**: nombre público del repo y producto
- **Kelko**: nombre interno de cliente — nunca en código, commits ni docs versionados
