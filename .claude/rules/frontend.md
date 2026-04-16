# Reglas — Frontend

Aplica cuando trabajas en `frontend/`.

## Stack

- Next.js + TypeScript
- Cliente tipado en `frontend/lib/api.ts`
- Tests con vitest (`npm test`)
- Build: `npm run build`

## Principio central

**El frontend representa; el backend decide.**

No recalcules prioridad, semántica ni estados en el frontend.
No inventes fallbacks que disimulen errores del backend.
Muestra los límites reales del sistema con claridad.

## Reglas de contrato

### api.ts es la fuente de verdad de paths frontend

Cuando un path de backend cambia:
1. Actualiza `frontend/lib/api.ts` — el path en la llamada `request()`
2. Verifica que el path en `api.ts` coincida exactamente con el path en `openapi/openapi-v1.yaml` y con `backend/app/routers/*.py`

### Tipos

- No uses `any` para respuestas de API
- Los tipos deben reflejar el schema real del backend
- Si el schema cambia en backend, actualiza el tipo en frontend en el mismo commit

## Tests

- Un archivo de test por componente en `frontend/tests/`
- Tests focalizados: comprueban comportamiento del bloque, no toda la app
- Naming: `<component-name>.test.tsx`
- Ejecutar con: `cd frontend && npm test`

## Componentes actuales

| Componente | Área |
|------------|------|
| `DispatcherRoutingCard` | Panel dispatcher — rutas, despacho, optimización |
| `DriverRoutingCard` | PWA conductor — arrive/complete/fail/skip/incidencias |
| `OperationalQueueCard` | Cola operativa |
| `PendingQueueCard` | Cola pendiente |
| `OperationalResolutionQueueCard` | Cola de resolución |
| `OrderOperationalSnapshotsCard` | Snapshots de pedido |
| `AdminProductsCard` | Administración de productos |

## Qué SÍ existe en frontend (R8)

- `RouteMapCard.tsx` — Google Maps JS API, marcadores por estado, marcador conductor (polling 30 s); requiere `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`
- Modal firma en `DriverRoutingCard` — canvas para proof of delivery (POD-001)
- Hook `useGpsTracking` en `DriverRoutingCard` — publica posición durante ruta in_progress (GPS-001)

## Qué NO existe en frontend

- Fleet view (visualización de flota completa en mapa)
- Seguimiento GPS en tiempo real (SSE/push) — solo polling 30 s
- Proof of delivery: foto (schema preparado, UI no implementada)
- Notificaciones push operativas

No insinúes estas capacidades en UI ni en comentarios de código.

## Comandos útiles

```bash
cd frontend

npm test                    # vitest
npm run build               # build de producción
npm run dev                 # servidor local localhost:3000
npm run type-check          # tsc --noEmit si existe script
```
