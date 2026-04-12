# Reglas — Tests

Aplica cuando escribes o modificas tests.

## Backend tests

- Framework: pytest
- Corren en Docker contra PostgreSQL real
- Configuración: `backend/pytest.ini`
- DB de test: limpia por sesión (ver `conftest.py`)
- Naming: `test_<área>_<concepto>.py`

### Cómo correr

```bash
# Todos
docker compose run --rm backend pytest -q

# Archivo específico
docker compose run --rm backend pytest -q tests/test_routing_bloque_c.py

# Con output detallado
docker compose run --rm backend pytest -v tests/test_routing_bloque_c.py::test_nombre_especifico
```

### Driver user en tests

Desde PILOT-HARDEN-001, los helpers que crean conductores en tests deben usar el patrón:
```python
user = User(id=uuid.uuid4(), ..., role=UserRole.driver)
db.add(user); db.flush()
driver = Driver(id=uuid.uuid4(), user_id=user.id, ...)
db.add(driver); db.commit()
```
No uses `Driver.id == User.id` — ese patrón fue eliminado.

### Tests que fallan en CI sin credenciales Google

`test_routing_bloque_e.py` requiere `GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID`.
Sin él, los 5 tests de ese archivo fallan. Eso es esperado y conocido.
No añadas ese archivo a CI sin resolver DEMO-OPT-001.

## Frontend tests

- Framework: vitest
- Naming: `<component>.test.tsx`
- Corren localmente: `cd frontend && npm test`

```bash
cd frontend
npm test                          # todos
npm test tests/dispatcher-routing-card.test.tsx  # uno específico
```

## Reglas generales

- Un test falla por una razón clara, no por side effects acumulados
- No testees comportamiento de otros bloques en el test del bloque activo
- Si añades un endpoint nuevo, añade al menos un test de happy path y uno de error esperado
- No mockees la DB en backend tests — usa la DB real de test (ya está configurada en conftest)
- Los tests deben ser reproducibles: sin dependencia de orden de ejecución ni de estado externo

## Test green vs Evidence green

Test green: los tests del bloque pasan en CI.
Evidence green: hay salida real verificable del flujo (smoke, demo, output observable).

**No declares un bloque DEMO cerrado con solo test green.**
