# Decisión de producto: ERP integration + Sales view
> Fecha: 2026-04-16
> Origen: gap-polpoo.md — gaps P1 confirmados como fuera de scope de R8
> Propósito: convertir la identificación del gap en una decisión explícita con opciones, implicaciones y recomendación

---

## Contexto

El análisis gap-polpoo.md identifica dos gaps que R8 no cierra y que son los más repetidos en los
testimonios reales de clientes de Polpoo:

1. **ERP integration**: sincronización bidireccional con sistemas internos del cliente (Telynet, SAP,
   Sage, Winfra, etc.). Tres de cuatro testimonios de Polpoo lo mencionan directamente.

2. **Sales view (actor comercial)**: el comercial responsable de una cuenta necesita ver el estado
   de sus pedidos en tiempo real, recibir alertas de incidencias, y confirmar entregas sin depender
   del equipo logístico.

Estas dos decisiones no son de implementación — son de estrategia de producto. No requieren que
se escriba código todavía. Requieren que exista una postura clara para que el equipo comercial
pueda responderlas cuando el cliente las pregunte.

---

## DECISIÓN 1 — ERP integration

### El problema concreto

Sin integración con ERP, el flujo de un cliente con Telynet (caso Heyp) es:
1. Pedido entra al ERP del cliente
2. Alguien lo copia manualmente a CorteCero
3. CorteCero optimiza y ejecuta
4. Alguien copia el resultado de vuelta al ERP

Ese paso 2 y 4 son doble entrada. Polpoo lo elimina. Si CorteCero no tiene respuesta, pierde ante
Polpoo en cualquier cuenta que ya tenga ERP.

### Opciones

**Opción A — Integración nativa por ERP (conector dedicado)**
Construir un conector por ERP específico: primero Telynet (más común en distribución Mallorca),
luego Sage/SAP según demanda.
- Esfuerzo: alto. Cada ERP tiene su API o protocolo. Requiere acceso a sandbox del ERP.
- Riesgo: los ERPs cambian versiones y rompen integraciones. Coste de mantenimiento indefinido.
- Ventaja: diferenciador real, argumento de venta directo, cierra el gap de Polpoo.
- Prerequisito: cliente piloto con ERP dispuesto a dar acceso sandbox + tiempo de integración.

**Opción B — Import/export bridge (CSV o Excel estructurado)**
CorteCero define un formato de importación estándar (CSV con columnas fijas). El cliente exporta
pedidos de su ERP al CSV y lo sube a CorteCero (manual o vía SFTP). Al cerrar ruta, CorteCero
exporta resultado en el mismo formato para reimportar al ERP.
- Esfuerzo: bajo. Import/export de CSV ya es una capacidad plausible con datos actuales.
- Riesgo: sigue siendo doble entrada, pero semi-automática. No elimina el problema, lo reduce.
- Ventaja: entregable rápido, no depende de acuerdos con fabricantes de ERP.
- Desventaja: el cliente lo percibe como "solución de transición", no como integración real.

**Opción C — API-first + partner de integración**
CorteCero expone una API robusta y documentada (ya existe el contrato OpenAPI). El cliente o un
partner de integración conecta su ERP a la API de CorteCero usando herramientas estándar
(Zapier, Make, middleware propio).
- Esfuerzo: bajo en CorteCero (la API ya existe). El esfuerzo es del partner o del cliente IT.
- Riesgo: el cliente necesita tener capacidad técnica propia o pagar a un integrador.
- Ventaja: escalable, no hay que mantener conectores propietarios. Polpoo probablemente hace esto
  también para ERPs menos comunes.
- Recomendación: definir y publicar la API de ingestión de pedidos como contrato estable.
  Ofrecer esta opción activamente a clientes con ERP.

**Opción D — No hacer nada explícito (postura de espera)**
No afirmar integración con ERP. Esperar a que un cliente piloto lo pida con fuerza para decidir
qué conector construir primero.
- Riesgo: perder la oportunidad de venta ante Polpoo mientras se espera.
- Ventaja: no se gasta esfuerzo en integraciones que nadie ha pedido todavía.

### Recomendación

**Opción B + C en paralelo, Opción A solo cuando haya cliente piloto comprometido.**

Razón: la Opción B (CSV bridge) es un entregable rápido que elimina la doble entrada manual y
permite ganar credibilidad con el cliente mientras se construye algo más robusto. La Opción C
(API-first) es el camino correcto a largo plazo y ya tiene la base técnica hecha. La Opción A
(conector nativo por ERP) solo tiene sentido cuando hay un cliente real que lo pide con nombre
de ERP concreto y acceso sandbox garantizado — construir conectores a ciegas es deuda sin retorno.

### Postura comercial resultante

> "CorteCero tiene una API abierta y documentada. Si tienes ERP con API propia, podemos conectarlo.
> Si necesitas algo más sencillo, tenemos importación/exportación estructurada que reduce la fricción.
> Un conector nativo lo construimos con el primer cliente piloto que lo necesite."

Esa respuesta es honesta, cubre los tres perfiles de cliente, y no promete nada que no existe.

### Decisión pendiente de responder

- ¿Se publica la API de ingestión de pedidos como contrato estable en esta fase?
- ¿Se añade import/export de pedidos en CSV al scope de R8 o va a R9?
- ¿Hay algún cliente potencial con ERP específico que justifique Opción A ya?

---

## DECISIÓN 2 — Sales view (actor comercial)

### El problema concreto

En el flujo actual, el comercial de una empresa de distribución:
1. Vende pedidos a sus clientes
2. Los entrega (o manda a logística) sin más información
3. Se entera de incidencias cuando el cliente se queja
4. No sabe si la entrega del día fue bien hasta el día siguiente

Polpoo le da visibilidad en tiempo real sobre sus cuentas. CorteCero no tiene respuesta para ese
actor. Si el interlocutor en el proceso de venta es el responsable comercial (no el de logística),
CorteCero no puede mostrarle nada útil.

### Opciones

**Opción A — Rol `comercial` en la app existente con vista filtrada**
Añadir un nuevo rol RBAC `comercial` que accede al panel existente pero con datos filtrados
a los clientes de su cartera. No hay UI nueva — es la misma app con permisos distintos.
- Esfuerzo: bajo-medio. Backend: filtro por `comercial_id` en queries de pedidos y rutas.
  Frontend: restringir qué cards ve el rol `comercial` en el dashboard.
- Ventaja: no hay que construir una app nueva. Reutiliza toda la infraestructura existente.
- Desventaja: la UI del dispatcher no está diseñada para el comercial. Puede sentirse rara.

**Opción B — Módulo "vista comercial" con UX específica**
Nueva sección del frontend dedicada al actor comercial: listado de sus clientes, estado de pedidos
del día, alertas activas, historial de entregas. UX limpia, sin el ruido operacional del dispatcher.
- Esfuerzo: medio. Requiere nuevos componentes frontend y endpoints específicos.
- Ventaja: experiencia correcta para el actor. Se puede vender como feature diferenciada.
- Desventaja: más tiempo. No entra en R8 sin decidirlo explícitamente.

**Opción C — Notificaciones push/email al comercial (sin app)**
El sistema notifica al comercial por email/Slack/WhatsApp cuando ocurre algo en sus cuentas:
pedido entregado, incidencia reportada, retraso detectado. No necesita entrar a la app.
- Esfuerzo: bajo. Se apoya en la infraestructura de notificaciones de D1/D2 (que ya están en R8).
  Solo hay que añadir lógica de "a quién notificar" por cuenta.
- Ventaja: entregable rápido, valor inmediato sin construir UI nueva.
- Desventaja: no da la visibilidad activa (el comercial tiene que esperar a recibir la notificación).

### Recomendación

**Opción C primero (se construye con D1/D2), Opción A después (bajo esfuerzo, alto impacto),
Opción B solo si hay tracción real de comerciales usando la herramienta.**

Razón: la Opción C se puede entregar como parte de D1/D2 sin añadir scope. La Opción A requiere
definir un nuevo rol y filtros, pero reutiliza todo lo existente — es trabajo de una semana, no
de un mes. La Opción B solo tiene sentido cuando hay comerciales reales usando el sistema y
quejándose de la UX del dispatcher — construirla antes sería especular sobre una necesidad que
no se ha validado.

### Decisión pendiente de responder

- ¿Se añade el rol `comercial` al RBAC en R8 Fase B (cuando se implementen notificaciones)?
- ¿La primera entrega es notificaciones push (Opción C) o vista filtrada (Opción A)?
- ¿Hay algún cliente piloto con equipo comercial activo que pueda dar feedback temprano?

---

## Resumen de decisiones pendientes

| Decisión | Opciones sobre la mesa | Prerequisito para decidir |
|---|---|---|
| ERP strategy | B+C ahora, A con piloto | ¿Hay cliente con ERP concreto? |
| ERP scope en R8 vs R9 | CSV import en R8 / API-first ya disponible | Decisión de roadmap |
| Sales view: primera entrega | Notificaciones (C) vs filtro RBAC (A) | Depende de si hay comerciales en cliente piloto |
| Sales view: profundidad | Opción A (filtro) vs Opción B (módulo) | Tracción real de uso |

---

## Lo que este documento no decide

- Si ERP integration entra en R8 o R9. Eso es decisión del usuario, no de este documento.
- Qué ERP específico construir primero. Depende del cliente piloto, no de preferencia técnica.
- Si el actor comercial necesita app nativa. La PWA del conductor ya es la apuesta web-first.

---

## Próximo paso

Responder las cuatro preguntas del cuadro de arriba. Con esas respuestas, este documento
se convierte en una decisión de roadmap concreta que puede trasladarse directamente a bloques
de R8/R9 con alcance y tipo definido.
