# AGENTS.md

## Propósito

Este archivo define el contrato operativo para cualquier agente que trabaje en este repositorio.

Su objetivo es evitar:

* cambios fuera de alcance
* cierres falsos
* sobreafirmaciones de madurez
* mezcla entre implementación, validación y demo

Este repositorio usa el nombre **CorteCero** como nombre seguro de repo y artefactos compartibles.
**Kelko** es solo contexto interno de cliente y no debe aparecer en commits, prompts reutilizables, documentación pública ni artefactos que puedan salir del entorno privado.

---

## Autoridad

Orden de autoridad dentro del trabajo del agente:

1. instrucciones directas del usuario
2. instrucciones del sistema / runtime
3. este `AGENTS.md`
4. convenciones implícitas del agente

El agente **no** define estrategia, fase ni prioridad por su cuenta.

* **El usuario dirige**
* **el agente ejecuta**
* **el revisor valida el resultado real**

---

## Unidad de trabajo

Regla general:

* **un bloque por vez**
* no mezclar tickets
* no adelantar el siguiente bloque sin instrucción explícita
* no abrir frentes laterales “de paso”

Cada bloque debe clasificarse explícitamente como uno de estos tipos:

* **IMPLEMENTATION**
* **SPIKE**
* **DEMO**
* **HARDENING**
* **DOCS**

Si el tipo no está indicado, el agente debe inferirlo de forma conservadora y declarar esa inferencia en su salida.

---

## Nomenclatura obligatoria

En todo output repo-safe:

* usar **CorteCero**
* no usar **Kelko** en:

  * commits
  * nombres de archivos
  * prompts reutilizables
  * documentación versionada
  * seeds o fixtures

`Kelko` solo puede aparecer en conversación privada o contexto verbal del usuario.

---

## Invariantes no negociables

El agente debe preservar siempre:

* multi-tenant estricto
* RBAC correcto
* contrato de errores estable (`detail.code`, `detail.message`)
* endpoints de lectura sin side effects
* eventos append-only donde aplique
* frontend representa; backend decide
* OpenAPI fiel al comportamiento real
* no secrets en repo
* no datos reales de cliente en repo
* no refactors laterales sin autorización

---

## Regla de mínima intervención

Todo cambio debe ser:

* mínimo
* reversible
* trazable
* suficiente para cerrar el bloque activo
* compatible con el baseline salvo que el bloque indique lo contrario

El agente no debe “aprovechar” para:

* limpiar otras cosas
* renombrar estructuras por gusto
* mover arquitectura
* reordenar backlog
* introducir deuda nueva por velocidad

---

## Reglas por capa

### DB

* migraciones explícitas
* nombres claros de índices, constraints y triggers
* no tocar datos previos salvo que el bloque lo exija
* no meter seeds funcionales fuera de alcance
* no introducir rigidez prematura si el bloque pide flexibilidad semántica

### Backend

* queries y mutaciones tenant-safe
* errores contractuales explícitos
* no lógica lateral fuera del scope
* tests del comportamiento pedido
* no vender “e2e” si no existe validación real

### Frontend

* representar fielmente lo decidido por backend
* no recalcular prioridad ni semántica
* no inventar fallbacks falsos
* mostrar límites reales del sistema con claridad
* tests focalizados del bloque

### Docs

* separar claramente:

  * implementado
  * verificado
  * no verificado
  * bloqueos
  * riesgos
* no convertir ausencia de evidencia en afirmación positiva

---

## Modos de cierre

Todo bloque debe declarar su tipo de cierre.

### 1. Test green

Significa:

* tests relevantes del bloque en verde
* build o validación técnica relevante en verde
* sin afirmar evidencia operativa real

### 2. Evidence green

Significa:

* existe salida real verificable del flujo objetivo
* hay evidencia operativa o demostrable
* no depende de suposiciones no resueltas

### Regla crítica

**Ningún bloque puede declararse cerrado como demo, spike validado o flujo e2e si solo está en `test green` y no en `evidence green`.**

---

## Regla de prerrequisitos para demo / smoke / evidencia

Si un bloque requiere:

* smoke real
* demo funcional
* evidencia e2e
* validación contra proveedor real
* validación con datos operativos mínimos

entonces la definición de done debe incluir también los **prerrequisitos mínimos necesarios** para producir esa evidencia.

Ejemplos de prerrequisitos válidos:

* dataset mínimo
* fixture sintético
* ruta demo geo-ready
* credencial privada ya disponible
* estado previo de entidades

### Regla obligatoria

Si la evidencia depende de un prerrequisito no resuelto, el agente debe hacer una de estas dos cosas:

1. **incluir ese prerrequisito dentro del alcance del bloque**, o
2. **marcar el bloque como bloqueado / no cerrado**

Lo que **no** puede hacer es declarar el bloque cerrado con:

* tests verdes
* fix técnico parcial
* evidencia aún imposible

---

## Regla específica para bloques DEMO

En bloques tipo **DEMO**, el agente debe entregar siempre:

* qué parte ya era real antes del bloque
* qué impedía la demo
* qué cambió exactamente
* qué comando o flujo produce la evidencia
* qué sigue siendo manual
* qué sigue siendo local
* qué no debe sobreafirmarse ante dirección

### Lenguaje prohibido en DEMO

No usar estas afirmaciones sin evidencia real:

* “operativo e2e”
* “listo para dirección”
* “demo-ready”
* “reproducible”
* “pilot-ready”
* “tráfico en tiempo real resuelto”
* “IA integrada”

---

## Regla específica para SPike

Un bloque tipo **SPIKE** no se cierra por volumen de exploración sino por respuesta clara a una pregunta técnica.

Debe terminar diciendo:

* hipótesis evaluada
* resultado
* evidencia
* huecos
* decisión recomendada

---

## Validación obligatoria

Si el bloque toca código, contrato o comportamiento, el agente debe ejecutar todas las validaciones razonables y relevantes del bloque.

Como mínimo, debe intentar:

* tests del área tocada
* build relevante
* smoke relevante si el bloque lo exige
* validación manual mínima si no hay test automatizable

Si una validación no puede ejecutarse, debe decir:

* cuál
* por qué no
* qué impacto tiene sobre el nivel de cierre

---

## Git y estado del árbol

Cuando el bloque implique cambios de archivos:

* no dejar trabajo ambiguo sin declarar
* no mezclar cambios ajenos dentro del mismo cierre
* no reescribir commits existentes
* no declarar cierre si el estado del árbol impide saber qué pertenece al bloque
* distinguir entre:

  * **cerrado local**
  * **promulgado en repo**
  * **pendiente de checks remotos**

---

## Salida obligatoria del agente

Toda entrega debe salir con este formato:

* **Bloque**
* **Tipo**
* **Objetivo**
* **Commit**
* **Alcance implementado**
* **Archivos tocados**
* **Validación ejecutada**
* **Resultado**
* **Huecos**
* **Riesgos**
* **Estado final**

### Estados permitidos

* `CERRADO_LOCAL`
* `CERRADO_CON_EVIDENCIA_LOCAL`
* `PROMULGADO`
* `BLOQUEADO`
* `PARCIAL`

No usar “done”, “ready” o “closed” sin uno de esos estados.

---

## Criterio de honestidad

El agente debe separar siempre:

### Implementado

Lo que cambió de verdad.

### Verificado

Lo que fue comprobado con tests, build, smoke o evidencia real.

### No verificado

Lo que parece correcto pero no se probó.

### Bloqueos

Lo que impide cierre real.

### Riesgos

Lo que no bloquea, pero limita la afirmación que puede hacerse.

---

## Prohibiciones explícitas

El agente no puede:

* inventar estado de CI no ejecutado
* inferir evidencia operativa a partir de tests unitarios
* vender como reproducible algo que depende de SQL manual o intervención local no versionada
* llamar “integrado” a un agente IA que no existe en flujo real
* convertir una ausencia de dataset en problema “menor” si bloquea la demo
* ocultar prerequisitos críticos dentro de supuestos implícitos

---

## Regla para IA / Agent features

Ninguna funcionalidad de IA se considera existente solo por:

* intención del negocio
* mención en email
* idea arquitectónica
* placeholder UI
* comentarios de código

Solo puede declararse como existente si hay al menos uno de estos elementos reales:

* endpoint funcional
* flujo UI funcional
* integración ejecutable
* evidencia verificable de uso

---

## Plantilla operativa breve para cada bloque

### Entrada esperada

* Proyecto: CorteCero
* Bloque:
* Tipo:
* Objetivo:
* Invariantes:
* Definition of done:

### Salida esperada

* Commit:
* Validación:
* Evidence green: sí/no
* Riesgos:
* Estado final:

---

## Cierre

La regla central de este repositorio es:

**no confundir cambio técnico con cierre real.**

Un bloque solo queda verdaderamente cerrado cuando su nivel de validación corresponde con el tipo de afirmación que se quiere hacer sobre él.
