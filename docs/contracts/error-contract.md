# Error Contract

Todos los errores del backend siguen este formato JSON:

```json
{
  "detail": {
    "code": "ERROR_CODE",
    "message": "Descripción legible"
  }
}
```

## Reglas

- `code` es una cadena en UPPER_SNAKE_CASE, estable, usable por clientes para lógica
- `message` es legible por humanos, puede cambiar sin romper contrato
- HTTP status code refleja la categoría del error (400, 401, 403, 404, 409, 422, 500)
- Los errores de validación de FastAPI/Pydantic mantienen este envelope cuando es posible

## Códigos de error documentados

| Código | Status | Descripción |
|--------|--------|-------------|
| `INVALID_CREDENTIALS` | 401 | Credenciales incorrectas |
| `TENANT_NOT_FOUND` | 404 | Tenant slug no existe |
| `INSUFFICIENT_PERMISSIONS` | 403 | Rol no autorizado para la operación |
| `DRIVER_NOT_LINKED` | 403 | Usuario con rol driver sin registro Driver activo |
| `ENTITY_NOT_FOUND` | 404 | Entidad no encontrada en el tenant |
| `DUPLICATE_ENTITY` | 409 | Conflicto de unicidad |
| `PLAN_LOCKED` | 409 | Operación no permitida sobre plan bloqueado |
| `INVALID_PLAN` | 422 | plan_id o service_date inválido |
| `INVALID_ROUTE` | 422 | Parámetros de ruta inválidos |
| `ROUTE_ALREADY_DISPATCHED` | 409 | Ruta ya despachada |
| `OPTIMIZATION_FAILED` | 500 | Error en provider de optimización |

## Invariante

El contrato de error nunca debe cambiar su estructura (`detail.code` / `detail.message`) sin un bloque de breaking change explícito y version bump en OpenAPI.
