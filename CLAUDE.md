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

### Reglas de comportamiento con el usuario

1. **Nunca dar código para que el usuario lo ejecute.** Si hay algo que ejecutar (git, bash, npm), hacerlo directamente con las herramientas disponibles.
2. **Verificar estado antes de actuar.** Antes de hacer un commit o cualquier acción sobre el repo, leer el estado actual (`git status`, `git log`) — no asumir.
3. **No ejecutar sin confirmación previa cuando hay ambigüedad.** Si no está claro si el usuario ya hizo algo, preguntar primero.
4. **Análisis crítico, no complaciente.** Si algo está roto o incompleto, decirlo directamente. No suavizar ni dar por bueno lo que no lo es.
5. **No abrir el siguiente bloque sin instrucción explícita.** Bloque 1 en evidence green antes de mencionar Bloque 2.
6. **No repetir el resumen de lo que se acaba de hacer** a menos que el usuario lo pida. Acción → silencio → esperar feedback.

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

## Lecciones aprendidas — helpers de test (R8-POD-FOTO)

### 1. SIEMPRE leer models.py antes de escribir helpers que instancian modelos

No inferir nombres de enums ni campos. Cada error cuesta un rebuild completo (~10 min).

Errores cometidos en R8-POD-FOTO:

| Inferido (incorrecto) | Real en models.py |
|-----------------------|-------------------|
| `OrderStatus.in_route` | `OrderStatus.dispatched` |
| `OrderIntakeType.new` | `OrderIntakeType.new_order` |
| `SourceChannel.manual` | `SourceChannel.office` |
| `RouteStop(sequence=1)` | `RouteStop(sequence_number=1)` |
| `RouteStop(customer_id=...)` | campo no existe en RouteStop |
| `Order(reference=...)` | `Order(external_ref=...)` |

**Regla:** antes de instanciar cualquier modelo en un test helper, abrir `backend/app/models.py` y verificar (1) valores exactos de Enums, (2) campos NOT NULL sin default, (3) campos que NO existen.

### 2. Constraints de DB que el ORM no valida pero la DB sí

PostgreSQL CHECK constraints no se disparan en Python — explotan en `flush()`/`commit()`.
Leer las migraciones relevantes antes de crear fixtures con estados no triviales.

Ejemplo crítico: `ck_route_stops_arrived_consistency`
- `status='arrived'` → `arrived_at` NOT NULL obligatorio
- `status='completed'` → `arrived_at` Y `completed_at` NOT NULL obligatorios

Patrón correcto para helpers con stop_status variable:
```python
stop = RouteStop(
    ...
    status=stop_status,
    arrived_at=now if stop_status in (RouteStopStatus.arrived, RouteStopStatus.completed) else None,
    completed_at=now if stop_status == RouteStopStatus.completed else None,
)
```

### 3. Colisión de fechas entre seed y helpers de test

El seed crea Plans para `date.today()` (hoy) — zona_a (open) y zona_b (locked).
Helpers que usen `date.today()` y creen un Plan incondicionalmente para esa zona → UniqueViolation.

**Patrón correcto — check-first antes de insertar:**
```python
plan = db_session.scalar(
    select(Plan).where(
        Plan.tenant_id == tenant_id,
        Plan.service_date == svc_date,
        Plan.zone_id == zone.id,
    )
)
if plan is None:
    plan = Plan(id=uuid.uuid4(), ...)
    db_session.add(plan)
    db_session.flush()
```

**Alternativa** — para tests que no necesitan `today`: usar offset determinista lejos del hoy:
```python
svc_date = date.today() + timedelta(days=(uuid.uuid4().int % 300) + 1)
```
Con el seed en `today`, `+ 1` ya es seguro (antes el seed usaba `tomorrow = today+1` y se necesitaba `+ 2`).

### 4. El sandbox de shell no tiene Docker

`docker compose` debe correr en la terminal del usuario. El ciclo es:
1. Claude edita archivos en el repo
2. Usuario corre `docker compose build --no-cache backend` + `pytest`
3. Usuario pega el output completo
4. Claude analiza y aplica el siguiente fix

### 5. Cambios en seed.py que afectan service_date — protocolo obligatorio

**Contexto:** Cuando se cambia `service_date` en el seed (ej. de `tomorrow` a `today`), los helpers de test que crean `Plan(...)` para esa fecha en zonas del seed dejan de ser seguros.

**Protocolo — ejecutar ANTES de hacer push:**
```bash
# 1. Encontrar todos los helpers que crean Plan directamente
grep -rn "= Plan(" backend/tests/ --include="*.py"

# 2. Para cada resultado, verificar contexto (-B10):
#    ¿Hay "if plan is None" en las 10 líneas anteriores? → seguro
#    ¿Usa tenant_id/zone_id de una entidad fresca (no del seed)? → seguro
#    ¿Usa while-loop que busca fecha libre? → seguro
#    Cualquier otro caso → aplicar check-first

# 3. Aplicar check-first a todos los inseguros en UN SOLO COMMIT
```

**Archivos corregidos en R8 (2026-04-18) por cambio today→tomorrow:**
- `test_routing_proof_a2.py` — `_build_route_with_stop()`
- `test_routing_gps_a3.py` — `_build_route()`
- `test_routing_proof_foto_r8.py` — helper principal
- `test_routing_bloque_e.py` — `_build_route_for_optimize()` + `test_optimize_422_missing_geo()`

**Lección operativa:** Los fallos en CI aparecen en cascada — el primer commit muestra N fallos, el fix muestra M fallos nuevos, etc. Esto no es que el fix empeoró las cosas; es que el CI corta en el primer fallo de cada archivo. **Siempre barrer todos los archivos de golpe, no uno a uno.**

### 6. grep sobre patrones de código devuelve falsos positivos

`grep "plan = Plan("` detecta también líneas **dentro** de bloques `if plan is None:`.
El resultado parece un problema cuando no lo es.

Usar siempre contexto amplio (`-B10`) o un script que evalúe el contexto antes de reportar un conflicto.

### 7. Vercel puede rechazar un deploy silenciosamente por config inválida en `vercel.json`

**Contexto:** `backend/vercel.json` tenía `"functions"` y `"builds"` simultáneamente. Vercel rechazó todos los deploys de `cortecero-api` sin crear ningún deployment record, sin log visible, sin error en GitHub Actions. CI verde, cero deploys reales.

**Fix:** eliminar `"functions"` — commit `7a5e159`. Ver detalle completo en `docs/deploy-notes.md` (DEPLOY-001).

**Señales de alerta:**
- Push exitoso en GitHub pero sin deployment record reciente en Vercel.
- `list_deployments` devuelve el último deployment como anterior al commit más reciente.
- No hay build logs porque Vercel no llegó a iniciar ningún build.

**Primer paso de diagnóstico:** revisar `vercel.json` en busca de claves incompatibles antes de buscar el bug en el código.

**Aprendizaje:** CI verde no implica deployment exitoso. El canal de verificación correcto es `list_deployments` o el dashboard de Vercel — no el status del push en GitHub.

### 8. Cambio de nullability en un campo = impacto 4-vías, no 3

**Contexto (ROUTE-FROM-TEMPLATE-001, 2026-04-21):** `RoutingRoute.plan_id` y `RoutingRouteStop.order_id` pasaron de `string` a `string | null` en `api.ts`. El build de TypeScript falló en CI porque los componentes que consumían esos campos hacían `.slice()` directo sin null-check.

**La regla de tres-vías no es suficiente.** Cuando cambia la nullability de un campo:

```
routers/*.py  ↔  openapi-v1.yaml  ↔  api.ts  ↔  componentes que usan el tipo
```

**Protocolo obligatorio antes de push:**

```bash
# 1. Encontrar todos los usos del campo en frontend
rg -n "\bplan_id\b" frontend/components frontend/app frontend/tests frontend/lib/api.ts
rg -n "\border_id\b" frontend/components frontend/app frontend/tests frontend/lib/api.ts

# 2. Para cada uso: ¿hay null-check? Si no → añadir en el mismo commit
#    Patrón correcto:
#      route.plan_id ? route.plan_id.slice(0, 8) : "—"
#      stop.order_id ? stop.order_id.slice(0, 8) + "…" : "—"
#      route.plan_id ?? ""   (cuando se necesita string no-null para una función)

# 3. Verificar build ANTES de push
cd frontend && npm run build
```

**Regla operativa:** `npm run build` es gate de pre-push para cualquier bloque que toque `api.ts` o schemas. No push sin build limpio local. CI valida, no descubre errores de tipado obvios.

### 9. `git status --short` y `git diff --name-only --cached` antes de cada push

**Contexto (ROUTE-FROM-TEMPLATE-001, 2026-04-21):** Los null-guards de frontend estaban en working tree modificado pero nunca entraron en ningún commit. `dba1cc8` (fix de test) era de alcance mínimo correcto, pero los archivos frontend pendientes quedaron fuera.

**Protocolo de cierre de commit:**

```bash
# Antes de hacer git add:
git status --short          # qué archivos hay modificados (¿pertenecen al bloque?)

# Después de git add, antes de git commit:
git diff --name-only --cached   # qué entra realmente al commit

# Regla: si git status muestra modificados que pertenecen al bloque activo → van en el commit
# No dejar deuda de working tree al cerrar un bloque
```

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

### Bloques completados (continuación)
- R8-POD-FOTO: presigned R2 upload + confirmación foto + `ProofModal` UI en `DriverRoutingCard` (292 tests en verde, commit `c095510`, 2026-04-18)
- DEMO-SEED-001: seed demo realista para lunes (2026-04-18)
  - service_date = today (cola visible inmediatamente)
  - Depósito: 39.65779, 2.79008 (Poligon Industrial Son Llaut, Santa Maria del Camí)
  - 12 vehículos con capacidades reales (7580..290 kg), VH-010/011/012 reserva
  - 8 conductores con carnet/ADR en nombre (4×C·ADR, 3×B·ADR, 1×B)
  - 15 clientes con coordenadas reales por toda Mallorca
  - 30 pedidos/día, catálogo 25 SKUs en 6 categorías
  - Reset queue: pedidos planned sin RouteStop → ready_for_planning al reiniciar
- DEMO-SEED-001-TESTS: fix colisión Plans en 5 archivos de test (2026-04-18)
  - check-first en proof_a2, gps_a3, foto_r8, bloque_e (×2)
- HARDENING-SEC-001: eliminado `/debug/db`; JWT guard en lifespan; credenciales frontend limpiadas (2026-04-18)
- HARDENING-DB-001: FK constraints stop_proofs + route_messages, índices rendimiento, migration 027, `StopProof` models.py alineado (commit `094a702`, 2026-04-18) — Neon pendiente manual
- DEMO-DB-RESEED-001: `seed()` en lifespan FastAPI → cold start Vercel siembra Neon (commit `e6cbd34`, 2026-04-18) — verificado: 30 pedidos + 9 vehículos activos
- UX-GESTION-001: Gestión form como 4 pasos numerados; Plan dropdown real; selector conductores sidebar; chips con × por pedido; botón deshabilitado hasta plan+vehículo+≥1 pedido (commit `d11defe`, 2026-04-19)
- MONITOR-MODE-001: Monitor mode en OpsMapDashboard — mapa full-width, chips flotantes por ruta activa, drawer slide-in con stops/stats/acciones (commit `c5980aa`, 2026-04-19) — tsc clean, PROMULGADO

### Bloques R9 completados
- R9-HARDENING-001: envs auditados (STARTUP_SEED_RESET, ENVIRONMENT), api.ts timeout+204+205, CI npm test glob fix, startup_seed_reset wired — PROMULGADO (commits 099ec24+ed6cfbe+a5c3f27)
- R9-PERF-001: _serialize_routes_batch (2 queries planas para list_routes), dispatch batch IN query, optimize 3× batch pre-loop (orders+customers+profiles) — PROMULGADO
- FIX-DEPLOY-001: eliminado bloque `"functions"` de `backend/vercel.json` que conflictuaba con `"builds"` — causa raíz de todos los fallos silenciosos de `cortecero-api` en Vercel (commit `7a5e159`, 2026-04-20) — PROMULGADO
- DRIVER-MOBILE-001: smoke en device real — login conductor, GPS, parada Pendiente→Llegó, truck marker en posición real, trayectoria vial real — CERRADO_CON_EVIDENCIA_REAL (2026-04-20)
- VISUAL-POLISH-001: token set `:root` expandido (17→45 vars), semánticos superficie/estado completos, 50+ inline styles reemplazados por vars CSS en 19 componentes, deploy frontend READY (commit `09b3f03`, 2026-04-20) — PROMULGADO

### R9 — CERRADO (2026-04-20)
**R9-REALTIME-001** — CONGELADO por decisión de arquitectura. Redis resuelve fanout entre procesos pero no la naturaleza efímera de Vercel Functions. Solo se activa cuando se decida arquitectura realtime definitiva (servicio persistente vs. serverless).

**MONITOR-MODE-002** — PARCIAL. Lado dispatcher (web): operativo — `ChatFloating` en `OpsMapDashboard`, polling 10s, tabs por ruta activa. Lado conductor (móvil): pendiente — `DriverRoutingCard` sin UI de chat. No presentar como "chat bidireccional completo".

---

## Fase activa actual — R10

> Última actualización: 2026-04-20
> Ver detalle completo en `docs/R10_BACKLOG.md` y `TASKS.md`.

### Bloques R10 completados (PROMULGADO)
- ROUTE-PLANNER-TW-001: `PATCH /stops/{stop_id}/scheduled-arrival` + schema + OpenAPI + api.ts — commit `7cf26e3`
- ROUTE-PLANNER-CAL-001 v2: `RoutePlannerCalendar` — KPI strip, toggle semana/día, gantt, drawer ETA inline — commit `6d505ac`
- TW-001-UI: input inline `type="time"` en drawer del planificador — incluido en CAL-001 v2
- R9-MONITOR-UX-001: chip delay badge persiste tras cerrar drawer — commit `b9e9374`
- PLANNER-AS-HOME-001: Planificador como pantalla inicial — commit `1516307`
- UX-SHELL-002: Gestión Operativa sin mapa por defecto; search; DataTable clickable — commit `815ba0a`
- UX-CLEANUP-001: nav "Rutas" interno + pills azules eliminados — commit `442be46`
- FIX-DEPLOY-001: eliminado `"functions"` de `backend/vercel.json` (causa raíz de silent failures Vercel) — commit `7a5e159`
- VISUAL-POLISH-001: token set `:root` expandido (17→45 vars), 50+ inline styles → CSS vars en 19 componentes — commit `09b3f03`
- ROUTIFIC-ANALYSIS-001: análisis Routific Beta + comparativa + diseño XLSX import — `docs/routific-analysis-and-xlsx-import.md`

### Bloque en CI (commit lanzado, esperando verde)
- **UX-FIXES-001** (2026-04-20): `hideSidebar` en OpsMapDashboard (elimina sidebar doble), `<select>` inline vehículo/conductor en Gestión form pasos 3+4, `DetailPanel` en Pedidos/Clientes/Conductores, `useToast` hook, Insights 6 KPIs (rutas + paradas + tasa), "+ Nueva ruta" en Planificador → navega a Gestión. Archivos: `OpsMapDashboard.tsx`, `RoutePlannerCalendar.tsx`, `page.tsx`, `GlobalShell.tsx`.

### Siguiente bloque — EJECUTAR cuando UX-FIXES-001 esté en verde
**XLSX-PARSE-001** — commit solo, sin mezclar con migraciones:
- `backend/app/utils/xlsx_parser.py`: `parse_xlsx()`, `normalize_header()`, `auto_map_columns()`, soporte `.xlsx`+`.csv`
- `backend/tests/test_xlsx_parser.py`: tests unitarios (happy path, columnas faltantes, CSV, headers con tildes)
- Sin tocar DB, sin migración, sin modelos

### Pipeline XLSX — orden de producto corregido (2026-04-20)
> Prioridad: cerrar primero el gap visible frente a Routific (pedidos → ruta).
> Plantillas estacionales son diferencial pero segundo paso.

```
XLSX-PARSE-001
    ↓
XLSX-ORDERS-001 + DATE-FORMAT-CONFIG-001
    ↓
XLSX-UI-ORDERS-001
    ↓
ROUTE-TEMPLATE-MODEL-001
    ↓
XLSX-TEMPLATES-001 + ROUTE-FROM-TEMPLATE-001
    ↓
XLSX-UI-TEMPLATES-001
```

### Pendiente — otros (independientes, menor prioridad)
- R9-CONTRACT-001 — Auditoría OpenAPI ↔ runtime completa + catálogo errores 4xx
- MONITOR-MODE-002-CONDUCTOR — Chat en `DriverRoutingCard` móvil (lado dispatcher ya operativo)
- HARDENING-DB-001-NEON — Aplicar migration 027 en Neon (manual, solo SQL)

### Huecos conocidos (no en backlog activo)
- SSE backend usa asyncio.Queue in-process → no escala multi-worker (fix: Redis + decisión arquitectura realtime)
- POD foto: UI + backend listos; R2 bucket real no probado (pospuesto hasta decidir storage)
- Migration 027: en repo, pendiente aplicar en Neon manualmente
- Notificaciones (D1): congeladas, pendiente proveedor email/SMS
- GPS conductor: polling 30s — tiempo real requiere arquitectura persistente
- Asistente IA: no existe en ninguna capa