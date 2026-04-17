# CorteCero — Claude Code Memory

> Entrypoint de memoria para Claude Code.
> Este archivo no reemplaza a `AGENTS.md`; lo complementa con contexto de navegación,
> stack-specific y reglas de comportamiento propias de Claude Code.

---

## Imports automáticos

@AGENTS.md
@docs/as-is.md

---

## Identidad del repositorio

**Nombre**: CorteCero
**Tipo**: SaaS B2B — gestión de pedidos, planificación y ejecución de rutas para distribuidores con flota propia
**Kelko**: nombre interno de cliente — nunca en commits, archivos, prompts reutilizables ni docs versionados

---

## Fuentes de verdad (orden de autoridad)

1. Instrucciones directas del usuario en la conversación
2. `AGENTS.md` — contrato operativo completo para todos los agentes
3. `docs/as-is.md` — baseline factual del estado del repo
4. `docs/contracts/` — contratos de error y dominio
5. `openapi/openapi-v1.yaml` — contrato API vivo
6. Este archivo

**Regla:** ante conflicto entre fuentes, el orden de prioridad es el de arriba. Nunca uses inferencia propia para resolver conflictos contractuales.

---

## Mapa del repositorio

```
cortecero/
├── backend/
│   ├── app/
│   │   ├── routers/          # endpoints por dominio
│   │   ├── optimization/     # providers: google_provider.py, mock
│   │   ├── models.py         # SQLAlchemy models
│   │   ├── schemas.py        # Pydantic schemas
│   │   ├── main.py           # router inclusion order — crítico
│   │   └── seed.py           # seed reproducible
│   ├── scripts/
│   │   ├── smoke_google_optimization.py   # smoke e2e Google
│   │   └── prepare_google_smoke_dataset.py
│   └── tests/                # pytest — un archivo por bloque/área
├── frontend/
│   ├── app/page.tsx          # entry point — todos los cards
│   ├── components/           # DispatcherRoutingCard, DriverRoutingCard, etc.
│   ├── lib/api.ts            # cliente tipado — fuente de verdad de paths frontend
│   └── tests/                # vitest
├── db/migrations/            # SQL numerado 001–019, idempotente
├── openapi/openapi-v1.yaml   # contrato API — mantener alineado con backend
├── docs/
│   ├── as-is.md              # estado real verificado
│   ├── contracts/            # error-contract.md
│   ├── domain/cortecero/     # dominio operativo
│   └── R8_BACKLOG.md         # backlog activo
├── scripts/                  # wrappers operativos de una orden
├── .claude/
│   ├── rules/                # reglas por contexto
│   └── commands/             # slash commands reutilizables
├── CLAUDE.md                 # este archivo
└── AGENTS.md                 # contrato operativo de agentes
```

---

## Modo de trabajo

### Principio central

Un bloque por vez. No mezcles tickets. No adelantes el siguiente sin instrucción explícita.

### Antes de escribir código

1. Lee `docs/as-is.md` para entender el estado real
2. Identifica el área: `backend` / `frontend` / `db` / `openapi` / `docs` / `routing` / `demo`
3. Carga la regla correspondiente de `.claude/rules/`
4. Verifica que el cambio no rompe invariantes de `AGENTS.md`

### Tipos de bloque

| Tipo | Cuándo | Cierre válido |
|------|--------|---------------|
| `IMPLEMENTATION` | Feature nueva o cambio de lógica | test green + CI verde |
| `HARDENING` | Seguridad, corrección, deuda técnica | test green + CI verde |
| `SPIKE` | Exploración técnica | respuesta clara a pregunta definida |
| `DEMO` | Preparar evidencia demostrable | evidence green (no solo test green) |
| `DOCS` | Documentación | contenido verificado, no aspiracional |

---

## Regla crítica: test green ≠ evidence green

`test green` = los tests del bloque pasan.
`evidence green` = existe salida real verificable del flujo objetivo.

**Nunca declares un bloque DEMO o SPIKE cerrado con solo test green.**

---

## Stack rápido

### Backend (comandos)

```bash
# Tests en Docker
docker compose run --rm backend pytest -q [archivo_o_carpeta]

# Levantar stack
docker compose up -d --build

# Solo backend
docker compose up -d postgres backend

# Migraciones + seed + servidor
docker compose up -d  # la imagen ya corre start.sh

# Script directo
./scripts/backend-check.sh
./scripts/test.sh
```

### Frontend (comandos)

```bash
cd frontend && npm test
cd frontend && npm run build
cd frontend && npm run dev   # localhost:3000

./scripts/frontend-check.sh
```

### Smoke Google

```bash
# Listar rutas disponibles
SMOKE_LIST_ROUTES=1 python3 backend/scripts/smoke_google_optimization.py

# Crear ruta y optimizar
SMOKE_CREATE_ROUTE=1 \
GOOGLE_APPLICATION_CREDENTIALS=~/.config/kelko/google/route-optimization-sa.json \
GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID=samurai-system \
python3 backend/scripts/smoke_google_optimization.py

# Optimizar ruta existente
CORTECERO_ROUTE_ID=<uuid> \
GOOGLE_APPLICATION_CREDENTIALS=~/.config/kelko/google/route-optimization-sa.json \
GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID=samurai-system \
python3 backend/scripts/smoke_google_optimization.py
```

---

## Reglas de alineación contractual

Cuando cambies un endpoint en `backend/app/routers/*.py`:
1. Actualiza `openapi/openapi-v1.yaml`
2. Actualiza `frontend/lib/api.ts` si el path o schema cambia
3. Actualiza `docs/as-is.md` si cambia el estado de madurez de esa capacidad
4. Verifica que los tres apunten al mismo path (lección de BUG-ROUTING-READY-DISPATCH-001)

---

## Reglas de nomenclatura

| Contexto | Nombre correcto |
|----------|----------------|
| Commits | CorteCero |
| Nombres de archivo | cortecero / kebab-case |
| Variables de entorno | CORTECERO_* |
| Conversación privada | Kelko (solo ahí) |

---

## Invariantes no negociables (resumen rápido)

Ver lista completa en `AGENTS.md`. Los más críticos:

- multi-tenant estricto en todas las queries
- `drivers.user_id` es la FK de vínculo conductor-usuario (migration 018)
- OpenAPI debe reflejar el runtime, no ser aspiracional
- eventos de auditoría son append-only
- no datos reales de cliente en repo
- no secrets en repo

---

## Riesgos a evitar

- Declarar "operativo e2e" sin evidencia de smoke ejecutado
- Afirmar "mapa operativo" cuando solo hay list-view
- Afirmar "seguimiento en tiempo real" cuando solo hay estado transaccional
- Llamar "integrado" a un agente IA que no existe en flujo real
- Usar "Kelko" en cualquier artefacto repo-safe

---

## Output contract esperado de Claude

Toda entrega debe incluir:

```
Bloque: <nombre>
Tipo: IMPLEMENTATION | HARDENING | SPIKE | DEMO | DOCS
Objetivo: <qué resuelve>
Commit: <sha o PENDIENTE>
Archivos tocados: <lista>
Validación ejecutada: <qué se corrió>
Resultado: <output real>
Huecos: <qué no se verificó>
Riesgos: <qué no conviene afirmar>
Estado final: CERRADO_LOCAL | CERRADO_CON_EVIDENCIA_LOCAL | PROMULGADO | BLOQUEADO | PARCIAL
```

---
## Imports automáticos

@AGENTS.md
@docs/as-is.md
@docs/platform-freeze-v3.md

---

## Fase activa actual — R8

Ver detalle completo en `docs/R8_BACKLOG.md`.

### Bloques completados (VERIFICADO LOCAL)
- Fase A completa: GPS-001, POD-001, MAP-001 backend + frontend
- B1: REALTIME-001 (SSE backend)
- B2: ETA-001 (recálculo haversine + delay_alerts)
- B3: CHAT-001 (chat dispatcher↔conductor)
- B4: LIVE-EDIT-001 (add/remove/move-stop en in_progress)
- C1: RETURN-001 (return-to-planning)
- E.2: DEMO-OPT-001 smoke 200 real con Google
- FLEET-VIEW-001: panel OpsMapDashboard
- F1–F6: time windows, capacidad, doble viaje, ADR, ZBE

### Pendiente activo (orden de prioridad)
1. **CI verde en `3e5980d`** — confirmar backend-tests #139
2. **R8-SMOKE** — Google smoke dataset geo-ready (reproducible)
3. **R8-SSE-FE** — SSE frontend, reemplazar polling 30s
4. **R8-POD-FOTO** — foto en proof of delivery (decisión storage pendiente)

### Huecos conocidos
- SSE backend usa asyncio.Queue in-process → no escala con gunicorn multi-worker (fix R9: Redis)
- MAP-001 frontend: evidence en browser local; sin CI automatizado con API key
- GPS-001 y POD-001 frontend: evidence en device real pendiente
- POD foto: schema preparado, UI no implementada, storage no decidido
- Notificaciones (D1): congeladas, pendiente proveedor email/SMS
- Asistente IA: no existe en ninguna capa