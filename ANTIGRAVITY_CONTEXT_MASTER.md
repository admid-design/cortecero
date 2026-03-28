# Contexto maestro para Antigravity — CorteCero

## 1) Qué es CorteCero

**CorteCero** es un SaaS B2B para distribuidores con flota propia que necesitan **proteger la planificación diaria** frente a pedidos tardíos y excepciones operativas.

No es un optimizador de rutas avanzado ni un WMS completo en esta fase.

El problema núcleo que resuelve el MVP es este:

> Una vez que logística cierra la planificación del día siguiente, los pedidos nuevos o tardíos no deben entrar sin control y romper el trabajo ya hecho.

## 2) Problema real que estamos resolviendo

La operación actual funciona por:

- experiencia del encargado
- memoria del chófer
- trabajo manual
- llamadas de última hora
- pedidos que entran tarde desde comerciales, oficina o clientes

Eso provoca:

- rutas rehechas a última hora
- pérdida de tiempo
- conflicto entre logística y comercial
- falta de trazabilidad
- imposibilidad de saber quién rompió la planificación
- sensación de caos operativo

El MVP entra exactamente ahí:

- **cut-off**
- **planes diarios por zona**
- **lock**
- **pedidos tardíos**
- **workflow de excepción**
- **auditoría**

## 3) Cliente ideal del MVP

Distribuidores B2B con:

- 5 a 50 vehículos
- reparto por zonas/días
- pedidos que llegan por varios canales
- fuerte dependencia de personas clave
- planificación hecha en Excel, ERP rígido o papel

Sectores ideales:

- hostelería
- higiene profesional
- limpieza
- suministros a hoteles/restaurantes
- mayoristas locales con reparto propio

## 4) Qué NO es el MVP

Fuera de alcance del MVP:

- optimización automática avanzada de rutas
- navegación GPS
- tracking en tiempo real
- WMS completo
- CRM comercial
- facturación
- mantenimiento de flota
- distinción formal de “añadido al mismo cliente” como clase separada
- motor complejo de replanificación post-lock

## 5) Objetivo del MVP (6 semanas)

Construir un producto funcional que permita:

1. Definir un **cut-off** por zona/cliente/default
2. Calcular automáticamente si un pedido es **tardío**
3. Crear **planes** por `service_date + zone`
4. **Bloquear** un plan
5. Impedir inclusión normal en planes bloqueados
6. Gestionar pedidos no elegibles mediante **excepciones**
7. Mantener **auditoría inmutable**
8. Mostrar un panel operativo simple para el día

## 6) Semántica funcional cerrada

### 6.1 `service_date`

Fecha operativa en la que el pedido debe quedar incluido en planificación o salir en reparto.

### 6.2 `created_at`

Timestamp de entrada inicial del pedido en CorteCero. No cambia.

### 6.3 `effective_cutoff_at`

Timestamp exacto de corte aplicable al pedido.

Se resuelve con esta prioridad:

1. override de cliente
2. cutoff de zona
3. cutoff por defecto del tenant

Para el MVP:

- el cut-off de un `service_date` se evalúa el **día anterior**
- a la hora definida por la regla aplicable
- con timezone de la zona o del tenant

### 6.4 Regla oficial de tardío

Un pedido es tardío si:

`created_at > effective_cutoff_at`

### 6.5 Estados del plan

- `open`
- `locked`
- `dispatched`

### 6.6 Regla de lock

Un plan `locked`:

- no admite inclusión normal
- solo admite pedidos con excepción aprobada

### 6.7 Tipo de excepción MVP

Solo existe:

- `late_order`

### 6.8 Estados de excepción

- `pending`
- `approved`
- `rejected`

### 6.9 Estados del pedido

Estados mínimos:

- `ingested`
- `late_pending_exception`
- `ready_for_planning`
- `planned`
- `exception_rejected`

### 6.10 Transiciones válidas

Flujo normal:

- `ingested -> ready_for_planning -> planned`

Flujo tardío:

- `ingested -> late_pending_exception -> planned` si excepción aprobada

Flujo tardío rechazado:

- `ingested -> late_pending_exception -> exception_rejected`

### 6.11 Inclusión en plan

Caso A: inclusión normal

- plan `open`
- pedido elegible
- pedido no incluido aún

Caso B: inclusión por excepción

- plan `open` o `locked`
- excepción `approved`
- pedido no incluido aún

No puede incluirse si:

- plan `locked` sin excepción aprobada
- plan `dispatched`
- pedido ya incluido
- pedido rechazado para ese `service_date`

## 7) Modelo de dominio

### Entidades core

#### `tenants`

Representa la empresa cliente del SaaS.

Campos clave:

- id
- name
- slug
- default_cutoff_time
- default_timezone
- auto_lock_enabled

#### `users`

Usuarios del tenant.

Campos clave:

- id
- tenant_id
- email
- full_name
- password_hash
- role
- is_active

Roles MVP:

- `office`
- `logistics`
- `admin`

#### `zones`

Zonas operativas.

Campos clave:

- id
- tenant_id
- name
- default_cutoff_time
- timezone
- active

#### `customers`

Clientes.

Campos clave:

- id
- tenant_id
- zone_id
- name
- priority
- cutoff_override_time
- active

#### `orders`

Pedido lógico.

Campos clave:

- id
- tenant_id
- customer_id
- zone_id
- external_ref
- requested_date
- service_date
- created_at
- status
- is_late
- lateness_reason
- effective_cutoff_at
- source_channel
- ingested_at
- updated_at

Idempotencia funcional:

- `tenant_id + external_ref + service_date` = mismo pedido lógico

#### `order_lines`

Líneas del pedido.

Campos clave:

- id
- tenant_id
- order_id
- sku
- qty
- weight_kg
- volume_m3

#### `plans`

Plan operativo diario por fecha y zona.

Campos clave:

- id
- tenant_id
- service_date
- zone_id
- status
- version
- locked_at
- locked_by

Restricción:

- único por `tenant_id + service_date + zone_id`

#### `plan_orders`

Inclusión de pedidos dentro del plan.

Campos clave:

- id
- tenant_id
- plan_id
- order_id
- inclusion_type (`normal` | `exception`)
- added_at
- added_by

#### `exceptions`

Excepciones sobre pedidos.

Campos clave:

- id
- tenant_id
- order_id
- type (`late_order`)
- status (`pending`, `approved`, `rejected`)
- requested_by
- resolved_by
- resolved_at
- note
- created_at

Regla:

- solo una excepción pendiente por pedido

#### `audit_logs`

Auditoría append-only.

Campos clave:

- id
- tenant_id
- entity_type
- entity_id
- action
- actor_id
- ts
- request_id
- metadata_json

## 8) Stack técnico recomendado

### Backend

- Python
- FastAPI
- SQLAlchemy 2.x
- Pydantic
- Alembic

### DB

- PostgreSQL

### Frontend

- Next.js
- React
- TypeScript
- UI simple orientada a operación

### Auth

- JWT
- RBAC

### Jobs

Para MVP:

- empezar sin complejidad innecesaria
- si hace falta background, usar Redis + Celery más adelante
- no sobrecomplicar semana 1

### Infra

- Docker Compose para piloto
- despliegue sencillo posterior en Render / Fly / ECS

## 9) API MVP

### Auth

- `POST /auth/login`

### Ingesta

- `POST /ingestion/orders`

### Orders

- `GET /orders`
- `GET /orders/{order_id}`

### Plans

- `GET /plans`
- `POST /plans`
- `GET /plans/{plan_id}`
- `POST /plans/{plan_id}/lock`
- `POST /plans/{plan_id}/orders`

### Exceptions

- `POST /exceptions`
- `GET /exceptions`
- `POST /exceptions/{id}/approve`
- `POST /exceptions/{id}/reject`

### Dashboard

- `GET /dashboard/daily-summary`

### Audit

- `GET /audit?entity_type=&entity_id=`

## 10) Reglas de autorización (RBAC)

### `office`

Puede:

- ingestar pedidos
- ver pedidos
- ver planes
- solicitar excepciones

No puede:

- bloquear planes
- aprobar excepciones
- cambiar configuración

### `logistics`

Puede:

- ver pedidos del día
- crear planes
- bloquear planes
- incluir pedidos en planes
- aprobar/rechazar excepciones
- ver auditoría

### `admin`

Puede:

- todo lo anterior
- gestionar zonas
- gestionar clientes
- gestionar usuarios
- configurar cut-offs del tenant

## 11) Reglas de negocio obligatorias

1. El cálculo de tardío usa `created_at`, no `updated_at`
2. El plan se define por `service_date + zone`
3. Un plan `locked` no acepta pedidos normales
4. Un pedido tardío requiere excepción para ir en ese `service_date`
5. Un pedido no puede añadirse dos veces al mismo plan
6. La auditoría es append-only
7. Toda acción crítica genera `audit_log`
8. Toda excepción requiere nota
9. La aprobación/rechazo registra actor y timestamp
10. Un pedido rechazado no se borra, queda rechazado para ese `service_date`

## 12) Casos de verdad del producto

### Caso 1

Pedido entra antes del cut-off, plan abierto.
Resultado: `ready_for_planning`.

### Caso 2

Pedido entra después del cut-off, plan abierto.
Resultado: `late_pending_exception`.

### Caso 3

Pedido entra antes del cut-off, pero el plan ya está `locked`.
Resultado: necesita excepción.

### Caso 4

Pedido tardío, excepción aprobada, plan locked.
Resultado: entra con `inclusion_type = exception`.

### Caso 5

Pedido tardío, excepción rechazada.
Resultado: `exception_rejected`.

## 13) UX MVP

### Pantallas mínimas

#### A. Login

- email
- password

#### B. Pedidos del día

Tabla con:

- external_ref
- customer
- zone
- service_date
- status
- is_late
- effective_cutoff_at
- semáforo visual: on time / late / exception

#### C. Planes

Listado por:

- fecha
- zona
- estado
- número de pedidos
- lock status

#### D. Detalle de plan

- pedidos incluidos
- tipo de inclusión
- acción de lock
- acción de agregar pedido

#### E. Cola de excepciones

- pedido
- motivo
- solicitante
- estado
- aprobar / rechazar

#### F. Auditoría

- timeline por entidad
- actor
- acción
- fecha/hora

### Criterio UX

- primar tabla y claridad
- cero fantasía
- panel operativo, no dashboard de marketing

## 14) Roadmap de releases

### R1 — Control operativo

- tenants, users, roles
- zones, customers
- ingesta de pedidos
- cálculo de tardío
- planes
- lock
- excepciones
- auditoría
- dashboard diario simple

### R2 — Planificación asistida

- mejor filtrado
- mayor claridad por zonas
- automatismos de creación de planes
- mejores validaciones de inclusión

### R3 — Extensión futura

- añadidos vs pedido nuevo
- mejor maestro operativo
- integración con almacén
- carga/peso
- asignación de vehículo

## 15) Plan de ejecución sugerido

### Semana 1

- repo base
- Docker Compose
- PostgreSQL
- Alembic
- auth básica
- tenants/users/roles
- zonas/clientes

### Semana 2

- orders + order_lines
- endpoint de ingesta
- cálculo de `effective_cutoff_at`
- cálculo de `is_late`
- transición inicial de estado

### Semana 3

- plans + plan_orders
- endpoints de creación/listado/detalle
- lock
- reglas de inclusión

### Semana 4

- exceptions
- approve/reject
- reglas sobre plan `locked`
- auditoría base

### Semana 5

- UI operativa
- tablas de pedidos
- planes
- cola de excepciones
- detalle básico

### Semana 6

- hardening
- validaciones
- seed piloto
- métricas simples
- smoke testing end-to-end

## 16) Seed mínimo para piloto

Crear:

- 1 tenant
- 3 usuarios (`office`, `logistics`, `admin`)
- 2 zonas
- 10 clientes
- 20 pedidos de ejemplo
- 1 plan abierto
- 1 plan bloqueado
- 3 excepciones: una pending, una approved, una rejected

## 17) Definition of Done del MVP

El MVP está listo cuando se pueda demostrar que:

1. entra un pedido
2. el sistema calcula correctamente si es tardío
3. existe un plan por fecha y zona
4. el plan se puede bloquear
5. un pedido tardío no entra solo
6. una excepción aprobada sí permite inclusión
7. todo eso queda auditado
8. un usuario operativo puede verlo desde la UI sin depender de base de datos

## 18) Riesgos que Antigravity no debe ignorar

1. **Ambigüedad funcional**
   No reinterpretar `late`, `lock` o `exception`.

2. **Sobreingeniería**
   No meter colas, eventos o microservicios si no hacen falta en MVP.

3. **Falta de multi-tenant**
   Todo debe nacer tenant-aware.

4. **Falta de idempotencia**
   La ingesta no puede duplicar pedidos.

5. **UI ornamental**
   Tiene que servir a operación, no a demo.

6. **RBAC superficial**
   El rol importa de verdad en approve/lock/config.

## 19) Estilo de implementación esperado

- código claro y pequeño
- arquitectura simple
- tests en reglas críticas
- validaciones explícitas
- errores HTTP consistentes
- naming sobrio
- cero magia innecesaria

## 20) Qué espero de Antigravity en cada entrega

Cada entrega debe incluir:

1. qué implementó
2. qué decidió
3. qué dejó fuera
4. riesgos conocidos
5. evidencia de funcionamiento
6. archivos tocados
7. cómo probarlo

## 21) Primera misión para Antigravity

Construir el **skeleton funcional de R1**:

- monorepo o estructura clara backend/frontend
- auth mínima
- PostgreSQL + migraciones
- modelos base
- seed de demo
- ingesta de pedidos
- cálculo de tardío
- CRUD/listado de planes
- lock de planes
- flujo de excepciones
- auditoría base
- UI mínima operativa

No construir todavía:

- motor de rutas
- carga/peso
- optimización
- maestro de almacén

## 22) Criterio de éxito de negocio del piloto

Medir:

- % pedidos tardíos
- % tardíos aprobados
- nº de cambios después del lock
- tiempo medio de resolución de excepción
- visibilidad de quién cambió qué

El piloto sirve si demuestra:

> “ahora sí sabemos qué entró tarde, quién lo aprobó y cuándo se rompió el plan”.

Así voy a trabajar contigo a partir de aquí:

**Yo** hago de arquitecto/revisor y califico cada entrega de Antigravity.
**Antigravity** desarrolla.

### Mi rúbrica de calificación

- **9–10**: alineado con el contrato, simple, sólido, listo para seguir
- **7–8**: válido, pero con deuda o decisiones flojas a corregir
- **5–6**: funciona parcial, pero hay desalineación importante
- **<5**: rehacer; rompió semántica, scope o arquitectura

### Lo que te voy a revisar siempre

- coherencia con `late / lock / exception`
- simplicidad real del MVP
- calidad del modelo de datos
- multi-tenant correcto
- RBAC correcto
- idempotencia de ingesta
- trazabilidad
- si Antigravity está metiendo scope no pedido

Pásame la **primera entrega de Antigravity** y te la califico de forma quirúrgica.
