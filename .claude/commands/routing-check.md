# /routing-check

Verifica el estado actual del módulo de routing.

## Instrucciones

Ejecuta estas comprobaciones en orden y reporta cada resultado:

### 1. Alineación de paths

Verifica que estos tres apuntan al mismo path:

```bash
# Backend
grep -n "ready-to-dispatch\|@router\." backend/app/routers/routing.py | head -20

# OpenAPI
grep -n "ready-to-dispatch\|/routes\|/planning\|/vehicles\|/stops\|/driver" openapi/openapi-v1.yaml | head -30

# Frontend api.ts
grep -n "ready-to-dispatch\|routes\|planning\|vehicles\|stops\|driver" frontend/lib/api.ts | head -20
```

### 2. Driver auth

```bash
grep -n "user_id\|Driver.id" backend/app/routers/routing.py | grep -A2 "resolve_current_driver"
```

Esperado: `Driver.user_id == current.id` (no `Driver.id == current.id`)

### 3. Google provider — timestamp

```bash
grep -n "_to_rfc3339_utc\|microsecond" backend/app/optimization/google_provider.py
```

Esperado: `.replace(microsecond=0)` presente

### 4. Tests de routing

```bash
docker compose run --rm backend pytest -q \
  tests/test_routing_bloque_c.py \
  tests/test_routing_bloque_d.py \
  tests/test_routing_bloque_e2.py \
  tests/test_routing_driver_auth_d2.py
```

Nota: `test_routing_bloque_e.py` falla sin Google credentials — es esperado.

### 5. Estado del smoke

```bash
SMOKE_LIST_ROUTES=1 python3 backend/scripts/smoke_google_optimization.py 2>&1 | tail -20
```

## Output esperado

```
Paths alineados (backend/openapi/frontend): OK / PROBLEMA — <detalle>
Driver auth (user_id): OK / PROBLEMA
Timestamp microsecond=0: OK / PROBLEMA
Tests routing (sin bloque_e): <N> passed, <M> failed
Smoke list routes: OK / BLOQUEADO — <razón>
Estado DEMO-OPT-001: ABIERTO / CERRADO
```
