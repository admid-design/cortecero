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
- R1–R6: cerradas
- R7: abierta

**Estado técnico actual**
- backend operativo con FastAPI + SQLAlchemy + JWT
- frontend en Next.js con vistas operativas y administrativas
- OpenAPI versionado
- smoke Google Route Optimization integrado al flujo de validación
- gobernanza de agentes y contratos ya versionada en repo

---

## Quick start

### Fast boot (local)

Prerequisites: Docker/Compose, Node.js y Python.

```bash
# 1) levantar stack
docker compose up -d --build

# 2) frontend local
cd frontend && npm install && npm run dev

# 3) chequeo mínimo rápido
docker compose run --rm backend pytest -q
cd frontend && npm test && npm run build
```

### Google optimization smoke

El repositorio incluye smoke de validación real para Route Optimization y soporte para preparar dataset demo geo-ready dentro del propio flujo de smoke. La validación real sigue dependiendo de credenciales privadas fuera del repo.

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

- autenticación
- ingestión de pedidos
- colas operativas
- colas de resolución
- snapshots operativos
- planificación
- excepciones
- dashboard
- export operativo
- auditoría
- administración de zonas
- administración de clientes
- administración de usuarios
- administración de tenant settings
- administración de productos
- routing dispatcher
- ejecución de conductor
- incidencias en ruta
- optimización de rutas con proveedor Google / mock según entorno

---

## Repository structure

```text
cortecero/
├── backend/
├── frontend/
├── db/
├── openapi/
├── docs/
│   ├── as-is.md
│   ├── contracts/
│   └── domain/
├── .claude/
├── AGENTS.md
├── CLAUDE.md
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
