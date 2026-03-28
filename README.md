# CorteCero R1 Skeleton

Skeleton funcional del MVP R1:

- Backend `FastAPI + SQLAlchemy + PostgreSQL`.
- Frontend `Next.js` operativo (login, planes, pedidos, excepciones).
- Migración SQL inicial `001_init.sql`.
- Seed demo con tenant, usuarios, zonas, clientes, pedidos, planes y excepciones.

## Estructura

- `openapi/openapi-v1.yaml`: contrato API v1.
- `db/migrations/001_init.sql`: esquema PostgreSQL inicial.
- `backend/`: API, reglas de negocio, auth/RBAC, seed y scripts.
- `frontend/`: panel operativo.
- `ANTIGRAVITY_CONTEXT_MASTER.md`: contexto maestro de producto y ejecución.

## Arranque rápido (Docker)

Desde `/Users/samurai_systems/scrapy_databank/cortecero`:

```bash
docker compose up --build
```

Servicios:

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- Frontend: `http://localhost:3000`
- PostgreSQL: `localhost:5432`

El backend arranca con:

1. `scripts/apply_migration.py`
2. `python -m app.seed`
3. `uvicorn app.main:app`

## Credenciales demo

- `office@demo.local / office123`
- `logistics@demo.local / logistics123`
- `admin@demo.local / admin123`

## Smoke test API

```bash
# Login
TOKEN=$(curl -sS -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"logistics@demo.local","password":"logistics123"}' | jq -r .access_token)

# Health
curl -sS http://localhost:8000/health

# Resumen diario (ajusta fecha)
curl -sS "http://localhost:8000/dashboard/daily-summary?service_date=$(date +%F)" \
  -H "Authorization: Bearer $TOKEN"

# Pedidos
curl -sS "http://localhost:8000/orders?service_date=$(date +%F)" \
  -H "Authorization: Bearer $TOKEN"
```

## Notas de alcance

- MVP cubre `cut-off`, `late`, `plan lock`, excepciones y auditoría.
- No incluye optimización de rutas, WMS ni tracking en tiempo real.
- Todo el modelo es multi-tenant (`tenant_id` en entidades core).
