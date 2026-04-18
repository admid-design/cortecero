# CorteCero

Sistema operativo para gestión de pedidos, planificación, excepciones y control operativo.

CorteCero unifica **backend**, **frontend**, **base de datos**, **contrato OpenAPI** y una capa explícita de **gobernanza documental** para reducir improvisación, aumentar trazabilidad y cerrar bloques con evidencia real.

---

## What it is

CorteCero está diseñado para operar el flujo de pedido a despacho con foco en:

- gestión de pedidos
- planificación operativa
- colas y resolución operativa
- excepciones y snapshots
- ejecución de rutas
- administración operativa y trazabilidad

Hoy el repositorio ya incluye superficie funcional en backend, frontend y contrato API para operación, administración y routing.

---

## What it solves

CorteCero reduce fricción operativa en tres frentes:

- coordinación entre pedido, planificación y ejecución de ruta en un flujo único
- consistencia contractual entre backend, frontend y OpenAPI
- cierre de bloques con evidencia verificable, evitando “funciona solo en narrativa”

---

## Current status

**Estado de fases (resumen)**
- R1–R7: cerradas
- R8: activa — Mapas, Realtime y Operaciones avanzadas (casi completa)

**Estado técnico actual**
- backend: FastAPI + SQLAlchemy + JWT — 283 tests en verde
- frontend: Next.js — 26 tests en verde, CI build en verde
- OpenAPI versionado y validado en CI
- CI/CD GitHub Actions → Vercel operativo en `main` (frontend + backend)
- smoke Google Route Optimization: HTTP 200 verificado con ETAs reales
- SSE (Server-Sent Events) en producción — hook `useRouteStream` PROMULGADO
- gobernanza de agentes y contratos versionada en repo

---

## Quick start

### Prerequisites

- Docker + Docker Compose
- Node.js 18+
- Python 3.13

### Variables de entorno

Crea `backend/.env` antes de arrancar:

```env
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/cortecero
JWT_SECRET_KEY=<secret>
CORS_ORIGINS=http://localhost:3000
```

Para Google Maps en frontend, crea `frontend/.env.local`:

```env
NEXT_PUBLIC_GOOGLE_MAPS_API_KEY=<tu api key>
```

Para Google Route Optimization (opcional — sin esto usa mock provider):

```env
GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcp/route-optimization-sa.json
GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID=<tu proyecto>
```

### Fast boot (local)

```bash
# 1) levantar stack completo (postgres + backend + migraciones + seed)
docker compose up -d --build

# 2) frontend local
cd frontend && npm install && npm run dev
# → http://localhost:3000

# 3) verificación rápida
docker compose run --rm backend pytest -q
cd frontend && npm test && npm run build
```

### Scripts de un comando

```bash
./scripts/backend-check.sh    # tests + linting backend
./scripts/frontend-check.sh   # build + tests frontend
./scripts/test.sh              # suite completa
```

### Google optimization smoke

```bash
# Preparar dataset geo-ready
python3 backend/scripts/prepare_google_smoke_dataset.py

# Ejecutar smoke contra Google real
CORTECERO_ROUTE_ID=<uuid> \
GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcp/route-optimization-sa.json \
GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID=<proyecto> \
python3 backend/scripts/smoke_google_optimization.py
```

La validación real requiere credenciales fuera del repo. Sin ellas, el stack usa mock provider automáticamente.

---

## Architecture

### Backend

- FastAPI
- SQLAlchemy
- Pydantic
- JWT auth
- routers por dominio operativo y admin

### Database

- PostgreSQL
- migraciones versionadas en `db/migrations/`
- constraints y vocabularios explícitos donde aplica

### Frontend

- Next.js
- cliente tipado contra backend
- componentes operativos y administrativos
- panel dispatcher
- flujo driver / PWA

### API contract

- OpenAPI versionado en `openapi/openapi-v1.yaml`

### CI / validation

- backend tests
- frontend smoke/build
- validación OpenAPI

---

## Current capabilities

A nivel funcional, el repo cubre actualmente:

**Core operativo**
- autenticación JWT multi-tenant (roles: admin, logistics, office, driver)
- ingestión de pedidos
- colas operativas, de resolución y snapshots
- planificación por zona/fecha con auto-lock
- excepciones operativas
- dashboard operativo
- export y auditoría append-only
- administración: zonas, clientes, usuarios, productos, tenant settings

**Routing y ejecución (R7–R8)**
- flujo dispatcher completo: plan → dispatch → optimize → paradas
- ejecución conductor PWA: arrive / complete / fail / skip / incidencias
- optimización de rutas con Google Route Optimization API (mock sin credenciales)
- GPS tracking del conductor durante ruta in_progress
- mapa de ruta con marcadores por estado + marcador conductor (Google Maps JS API)
- SSE en tiempo real: eventos de ruta push al dispatcher (reemplaza polling)
- ETA dinámico con recálculo haversine + alertas de retraso (≥15 min)
- chat interno dispatcher ↔ conductor en ruta
- edición en vivo de ruta in_progress (add / remove / move stop)
- devolución a planificación de pedidos fallidos
- proof of delivery con firma canvas
- fleet view: panel OpsMapDashboard con posición de flota

**Constraints de optimización (R8-F)**
- time windows por cliente
- capacidad de vehículo (kg)
- doble viaje por día
- mercancías peligrosas ADR
- zonas de bajas emisiones ZBE

**Lo que NO existe aún**
- proof of delivery: foto (storage pendiente)
- notificaciones push/email a cliente (proveedor pendiente)
- asistente IA en ninguna capa

---

## Repository structure

```text
cortecero/
├── backend/
│   ├── app/
│   │   ├── routers/          # endpoints por dominio
│   │   ├── optimization/     # google_provider.py, mock_provider.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── realtime.py       # RouteEventBus (SSE)
│   │   └── seed.py
│   ├── scripts/              # smoke, prepare_dataset
│   └── tests/                # pytest — un archivo por bloque
├── frontend/
│   ├── app/
│   ├── components/
│   └── lib/
│       ├── api.ts            # cliente tipado — fuente de verdad de paths
│       └── useRouteStream.ts # hook SSE
├── db/
│   └── migrations/           # SQL 001–026, idempotentes
├── openapi/
│   └── openapi-v1.yaml       # contrato API vivo
├── docs/
│   ├── as-is.md              # estado real verificado del repo
│   ├── R8_BACKLOG.md         # backlog activo
│   ├── contracts/
│   ├── domain/
│   └── evidence/             # outputs de smoke verificados
├── scripts/                  # backend-check.sh, frontend-check.sh, test.sh
├── .claude/
│   ├── rules/                # reglas escopadas por contexto
│   └── commands/
├── AGENTS.md                 # contrato operativo de agentes
├── CLAUDE.md                 # memoria de Claude — stack, invariantes, comandos
└── README.md
```

---

## Documentation

### Start here

Si vas a trabajar en este repo, entra en este orden:

1. `README.md`
2. `docs/as-is.md`
3. `docs/contracts/`
4. `docs/domain/cortecero/`
5. `CLAUDE.md`
6. `AGENTS.md`

### Source of truth

**Baseline factual**

- `docs/as-is.md`

**Contracts**

- `docs/contracts/`

**Domain**

- `docs/domain/cortecero/`

**Agent governance**

- `CLAUDE.md`
- `.claude/`
- `AGENTS.md`

### Scope of this README

Este README cubre:

- qué es el proyecto
- estado actual
- quick start
- arquitectura general
- mapa del repositorio
- documentación de entrada
- modelo de trabajo

No cubre:

- backlog completo por fase
- detalle exhaustivo de endpoints
- matrices completas de decisión
- diseño TO-BE no promulgado
- work in progress no consolidado

Para eso, usar `docs/`.

---

## Working model

El método de trabajo es explícito y orientado a cierre verificable:

- un bloque por vez, cambio mínimo suficiente, sin mezclar tickets
- usuario/revisor marca prioridad y gate; implementación por evidencia
- no se declara cierre sin validación ejecutada y estado final explícito

Detalle contractual completo en `AGENTS.md`, `CLAUDE.md` y `docs/contracts/`.

---

## Contributing

Antes de tocar código o contratos:

1. revisa `docs/as-is.md`
2. revisa `docs/contracts/`
3. valida invariantes y gates
4. limítate al bloque activo
5. declara evidencia, riesgos y estado al cerrar

---

## Releases

- Tags publicados: `v0.2.0`, `v0.3.0`, `v0.4.0`, `v0.5.0`
- Historial completo: `https://github.com/admid-design/cortecero/releases`

---

## License

Actualmente este repositorio no incluye archivo `LICENSE`.

---

## Final note

CorteCero no debe evolucionar por acumulación de parches.

Cuando falte diseño, contrato o gate, la acción correcta no es improvisar: **bloquear, documentar y decidir explícitamente**.
