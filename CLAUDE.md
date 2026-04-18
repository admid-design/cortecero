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
- R8-POD-FOTO: presigned R2 upload + confirmación foto (292 tests en verde, 2026-04-18)
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

### Pendiente activo (orden de prioridad)
1. **R8-POD-FOTO-UI** — integrar foto en PWA conductor (DriverRoutingCard)
2. **R8-POD-FOTO-R2-REAL** — smoke con bucket R2 real (credenciales necesarias)
3. **R8-SMOKE** — Google smoke dataset geo-ready (reproducible)

### Huecos conocidos
- SSE backend usa asyncio.Queue in-process → no escala con gunicorn multi-worker (fix R9: Redis)
- MAP-001 frontend: evidence en browser local; sin CI automatizado con API key
- GPS-001 y POD-001 frontend: evidence en device real pendiente
- POD foto: backend CERRADO_LOCAL, UI no implementada, R2 real no probado
- Notificaciones (D1): congeladas, pendiente proveedor email/SMS
- Asistente IA: no existe en ninguna capa
- Vercel: verificar que NEXT_PUBLIC_DEPOT_LAT/LNG no sobreescriben el fallback correcto