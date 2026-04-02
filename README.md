# CorteCero

CorteCero es un sistema operativo para gestión de pedidos, planificación, excepciones y control operativo, con arquitectura **backend + frontend + base de datos + OpenAPI + gobernanza documental**.

El objetivo del repo no es solo implementar funcionalidades, sino hacerlo con **trazabilidad**, **contratos explícitos** y una forma de trabajo pensada para reducir improvisación y aumentar consistencia.

---

## Estado actual del repositorio

**Estado de fases**

* R1–R6: cerradas
* R7: abierta, con implementación congelada mientras se consolida la capa documental y contractual

**Capa documental ya instalada**

* Gobernanza de agente: `CLAUDE.md` y `.claude/`
* Baseline factual del sistema: `docs/as-is.md`
* Dominio documentado: `docs/domain/`
* Contratos y reglas: `docs/contracts/`

**Importante**
Este repositorio ya no debe leerse como un MVP genérico, sino como un sistema con:

* modelo de trabajo explícito
* gates y criterios de cierre
* dominio documentado
* reglas de revisión
* separación entre contrato vigente, huecos pendientes y decisiones no promulgadas

---

## Arquitectura resumida

### Backend

* FastAPI
* SQLAlchemy
* Pydantic
* JWT auth
* routers por dominio operativo y admin

### Base de datos

* PostgreSQL
* migraciones versionadas en `db/migrations/`
* vocabularios cerrados y constraints explícitos donde aplica

### Frontend

* Next.js
* cliente tipado contra backend
* componentes operativos y administrativos

### Contrato API

* OpenAPI versionado en `openapi/openapi-v1.yaml`

### CI/CD

* pytest backend
* build smoke frontend
* validación OpenAPI

---

## Fuentes de verdad del proyecto

### 1. Baseline factual del repo

* [`docs/as-is.md`](docs/as-is.md)

Documento principal para entender **qué existe realmente hoy** en:

* DB
* modelos
* schemas
* endpoints
* frontend
* tests
* CI/CD
* backlog y gates
* huecos y contradicciones observadas

### 2. Contratos del sistema

* [`docs/contracts/invariants.md`](docs/contracts/invariants.md)
* [`docs/contracts/acceptance-gates.md`](docs/contracts/acceptance-gates.md)
* [`docs/contracts/output-templates.md`](docs/contracts/output-templates.md)
* [`docs/contracts/fail-closed.md`](docs/contracts/fail-closed.md)
* [`docs/contracts/vocabularies.md`](docs/contracts/vocabularies.md)
* [`docs/contracts/decision-matrix.md`](docs/contracts/decision-matrix.md)

### 3. Dominio

* [`docs/domain/cortecero/`](docs/domain/cortecero)
* [`docs/domain/kelko/`](docs/domain/kelko)

### 4. Gobernanza del agente

* [`CLAUDE.md`](CLAUDE.md)
* `.claude/rules/`
* `.claude/commands/`

---

## Cómo se trabaja en este repo

Este repo se trabaja con un método explícito.

### Reglas base

* El usuario dirige fase, ticket y prioridad
* Un bloque por vez
* Cambio mínimo suficiente
* No mezclar tickets
* No abrir fases nuevas por iniciativa propia
* No declarar cierre de fase por cuenta propia
* Verificar gate antes de ejecutar
* Ante ambigüedad: **fail closed**

### Regla de evidencia

Ningún bloque se considera cerrado sin:

* commit o diff real
* alcance explícito
* archivos tocados
* tests/checks relevantes
* riesgos declarados
* estado final

### Revisión

La revisión se hace con doble lente:

* **valor operativo**
* **preparación para IA**

---

## Estructura principal del repositorio

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
└── CLAUDE.md
```

---

## Estado funcional actual

A nivel de sistema, el repo cubre actualmente estas áreas:

* autenticación
* ingestión de pedidos
* colas operativas
* colas de resolución
* snapshots operativos
* planificación
* excepciones
* dashboard
* export operativo
* auditoría
* administración de zonas
* administración de clientes
* administración de usuarios
* administración de tenant settings
* administración de productos

Además, ya existe soporte documental para inventario y almacenes, aunque no toda esa superficie está cerrada en todas las capas.

Para el detalle factual exacto, consultar:

* [`docs/as-is.md`](docs/as-is.md)

---

## Lo que este README sí cubre

* propósito del repo
* arquitectura general
* estado actual
* fuentes de verdad
* método de trabajo
* puntos de entrada para contributors y agentes

## Lo que este README no cubre

* backlog completo por fase
* detalle exhaustivo de todos los endpoints
* matrices completas de decisión
* diseño TO-BE no promulgado
* work-in-progress no consolidado

Para eso, usar `docs/`.

---

## Punto de entrada recomendado

Si vas a trabajar en este repo, empieza en este orden:

1. [`README.md`](README.md)
2. [`docs/as-is.md`](docs/as-is.md)
3. [`docs/contracts/`](docs/contracts)
4. [`docs/domain/cortecero/`](docs/domain/cortecero)
5. [`CLAUDE.md`](CLAUDE.md)

---

## Estado documental

Bloques documentales cerrados hasta ahora:

* `DOC-CLAUDE-001`
* `DOC-REPO-001`
* `DOC-DOMAIN-001`
* `DOC-CONTRACTS-001`
* `DOC-TEMPLATES-001`

Esto significa que la capa de gobernanza ya no es implícita: está versionada y debe tratarse como parte del sistema.

---

## Nota final

CorteCero no debe evolucionar por acumulación de parches.
Cuando falte diseño, contrato o gate, la acción correcta no es improvisar: es **bloquear, documentar y decidir explícitamente**.
