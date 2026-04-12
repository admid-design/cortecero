# Reglas — Backend

Aplica cuando trabajas en `backend/`.

## Stack

- FastAPI + SQLAlchemy + Pydantic + JWT
- Python 3.13, venv en `.venv/`
- Tests con pytest en Docker (`docker compose run --rm backend pytest`)

## Reglas obligatorias

### Multi-tenant

Toda query a la DB debe incluir `WHERE tenant_id = current.tenant_id`.
Nunca hagas una query que pueda devolver datos de otro tenant, aunque sea "solo para tests".

### Errores

Usa siempre el envelope estándar: `{ detail: { code, message } }`.
Usa las funciones helper de `app/errors.py`: `not_found()`, `forbidden()`, `unprocessable()`, etc.
No lances excepciones HTTP crudas de FastAPI si hay helper equivalente.

### Router inclusion order

El orden en `app/main.py` importa para resolución de rutas.
Si añades paths estáticos que puedan competir con paths dinámicos de otro router (e.g. `/orders/{id}`),
ponlos en un namespace diferente o en un router que se incluya primero.
Lección: `BUG-ROUTING-READY-DISPATCH-001` — `/orders/ready-to-dispatch` colisionó con `/orders/{order_id}`.

### Driver auth

Desde migration 018, el vínculo conductor-usuario es `Driver.user_id == current.id`.
No uses `Driver.id == current.id` — ese era el patrón pre-PILOT-HARDEN-001.

### Migraciones

- Numeradas con prefijo `NNN_nombre.sql`, lexicográficas
- Idempotentes (`CREATE TABLE IF NOT EXISTS`, `DO $$ BEGIN ... EXCEPTION WHEN duplicate_column...`)
- No alterar datos de migrations anteriores sin bloque explícito
- El runner aplica todas las migraciones en orden al arrancar

### Tests

- Un archivo de test por área/bloque
- Los tests se corren en Docker contra DB real (no mock de DB)
- `conftest.py` gestiona la sesión de DB de test
- Nomenclatura: `test_<área>_<bloque_o_concepto>.py`

### OpenAPI

Cuando cambies un endpoint (path, método, parámetros, schema):
1. Actualiza `openapi/openapi-v1.yaml` en el mismo commit
2. Si el path cambia, actualiza también `frontend/lib/api.ts`

## Comandos útiles

```bash
# Tests completos backend
docker compose run --rm backend pytest -q

# Tests de un archivo
docker compose run --rm backend pytest -q tests/test_routing_bloque_c.py

# Acceso a shell backend
docker compose run --rm backend bash

# Ver logs del backend corriendo
docker compose logs -f backend
```
