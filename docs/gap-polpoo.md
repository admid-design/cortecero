# Gap Analysis: CorteCero vs Polpoo 2.0
> Última actualización: 2026-04-16
> Fuente: Presentación Polpoo 2.0 (29 páginas) + docs/as-is.md verificado + R8_PLAN_DESARROLLO.md
> Propósito: entender qué cubre R8, qué no cubre, y qué tiene Polpoo que no está en ningún plan.

---

## Corrección crítica de lectura

**R8 no cubre ~75-80% de Polpoo en estado actual del repo.**
**R8 cubre ~75-80% de Polpoo como plan maestro de producto.**

Esa distinción importa. Como blueprint, R8 contempla mapas, optimize, GPS, POD, realtime, ETA,
devoluciones, cobro, notificaciones, tracking portal, métricas, costes, IA, scheduler y constraints
avanzados. Como producto implementado hoy, una parte importante sigue en roadmap, verificada solo
localmente, o pendiente de ejecutar.

---

## Lo que Polpoo vende realmente

Polpoo no vende un "algoritmo de rutas". Vende esto:

> **visibilidad + operación + sincronización + datos + comunicación**

Lo que diferencia a Polpoo de un simple optimizador de rutas es que convierte la distribución en
una operación visible, conectada y trazable para tres actores simultáneamente: el distribuidor,
el comercial y el cliente final. Eso está en páginas 2-6 como propuesta general, en páginas 23-27
como contraste actual-vs-con-Polpoo por actor, y en páginas 11-18 como módulo de costes, IA e
integración.

---

## El modelo de tres actores de Polpoo

**Distribuidor / Encargado (dispatcher)**
Problema actual: pedidos manuales, rutas sin centralizar, papel, sin datos.
Con Polpoo: pedidos centralizados, planificación visible, reportes al instante, sincronización ERP.

**Comercial (sales rep)**
Problema actual: pierde visibilidad cuando el camión sale, se entera de incidencias al día siguiente,
conflicto permanente con logística.
Con Polpoo: estado de sus pedidos en tiempo real, alertas de incidencias en sus cuentas, puede
enfocarse en vender.
Estado en CorteCero: este actor no existe en ningún plano de R8. El rol `office` existe en RBAC
pero no hay UI ni flujo diseñado para el comercial con vista propia.

**Cliente final**
Problema actual: no sabe cuándo llega, no recibe comunicación proactiva.
Con Polpoo: previsión exacta de hora de llegada, notificado en tiempo real de retrasos,
digitalización y envío automático de albarán, portal con estado de pedidos.
Estado en CorteCero: cubierto en R8 Fases D (email / WhatsApp / portal tracking) como plan,
no implementado aún.

---

## Qué puede decirse hoy con seguridad

CorteCero ya tiene una base mucho más cercana a un producto operativo de distribución que a
un simple optimizador técnico:

- Dispatcher completo: plan → dispatch → optimize con Google → seguimiento de paradas
- SSE streaming de eventos de ruta en tiempo real (PROMULGADO — commit 906fd8e)
- GPS del conductor con posición en mapa, polling 30 s (VERIFICADO LOCAL)
- Firma digital del cliente en PWA del conductor (VERIFICADO LOCAL)
- Gestión de excepciones e incidencias
- Multi-tenant SaaS con RBAC completo
- Base de colas, planes y ejecución operativa verificada en CI

Eso ya separa a CorteCero de una demo técnica tipo "route optimizer".

Lo que no puede decirse hoy: "sincronizamos con tu ERP", "tus comerciales tienen visibilidad en
tiempo real", "IA operativa", "control de costes por ruta". Nada de eso existe ni está implementado.

---

## Cobertura de R8 — distinguiendo roadmap de estado implementado

### A. R8 como blueprint (~75-80% de Polpoo)

> Nota: el ~75-80% es una aproximación estratégica, no un scoring técnico exacto. Sirve para
> orientar decisiones de priorización y comunicación, no para comparación feature-by-feature.

R8 ya contempla en su plan los bloques equivalentes a cada módulo de Polpoo:

| Módulo Polpoo | Bloques R8 equivalentes |
|---|---|
| Mapa + seguimiento tiempo real | A1 (MAP-001) + B1 (REALTIME-001) |
| GPS conductor | A3 (GPS-001) + B1 |
| Firma digital / albarán | A2 (POD-001) |
| ETA dinámica + alertas de retraso | B2 (ETA-001) |
| Chat interno | B3 (CHAT-001) |
| Modificar ruta en vivo | B4 (LIVE-EDIT-001) |
| Devoluciones estructuradas | C1 (RETURNS-001) |
| Control de cobro | C2 (PAYMENT-001) |
| Actualización datos cliente | C3 (CLIENT-UPDATE-001) |
| Email ETA + confirmación entrega | D1 (NOTIFY-EMAIL-001) |
| WhatsApp | D2 (NOTIFY-WA-001) |
| Portal tracking cliente final | D3 (TRACKING-001) |
| Métricas por cliente / conductor | E1 (METRICS-001) |
| Informe PDF de ruta | E2 (REPORTS-001) |
| Control de costes por ruta | E3 (COSTS-001) |
| Análisis IA anomalías | E4 (AI-001) |
| Time windows en optimizer | F1 (TW-001) |
| Capacidad vehículo en optimizer | F2 (CAPACITY-001) |
| Fleet view multivehículo | F3 (MULTIVEHICLE-001) |
| Doble viaje por jornada | F4 (DOUBLE-TRIP-001) |
| Scheduler automático (9am) | G1 (SCHEDULER-001) |
| ADR (restricciones peligrosos) | F5 (ADR-001) — diferenciador CorteCero |
| ZBE Palma | F6 (ZBE-001) — diferenciador CorteCero |

### B. R8 como estado implementado actual

Leyenda de evidencias (orden descendente de certeza):

- `PROMULGADO` — CI remoto verde, commit en main, verificable por cualquiera
- `VERIFICADO LOCAL` — tests en verde localmente, smoke ejecutado; CI remoto aún no confirmado para este bloque
- `CERRADO_CON_EVIDENCIA_LOCAL` — evidencia real del flujo (output JSON, browser render); no depende solo de tests
- `NO IMPLEMENTADO` — no existe código productivo del bloque; puede existir schema o plan

| Capacidad | Estado real |
|---|---|
| Dispatcher completo (plan→dispatch→optimize→paradas) | PROMULGADO |
| Optimize con Google Route Optimization | CERRADO_CON_EVIDENCIA_LOCAL |
| SSE streaming tiempo real (REALTIME-001) | PROMULGADO |
| Mapa dispatcher con marcadores | VERIFICADO LOCAL |
| GPS conductor + marcador en mapa (polling) | VERIFICADO LOCAL |
| Firma digital conductor (POD) | VERIFICADO LOCAL |
| ETA dinámica | NO IMPLEMENTADO |
| Chat interno | NO IMPLEMENTADO |
| Devoluciones / cobros / actualización cliente | NO IMPLEMENTADO |
| Notificaciones email / WhatsApp / portal | NO IMPLEMENTADO |
| Métricas / informes / costes | NO IMPLEMENTADO |
| IA | NO IMPLEMENTADO (requiere datos acumulados) |
| Constraints avanzados (time windows, capacidad, ADR, ZBE) | NO IMPLEMENTADO |
| Fleet view / scheduler | NO IMPLEMENTADO |

---

## Gaps por prioridad comercial

### P1 — Gaps que bloquean el pitch ante clientes reales

**ERP integration**
Excluido explícitamente de R8. Polpoo lo repite como pilar central y los testimonios lo confirman:
3 de 4 clientes reales mencionan sincronización con sistemas internos. Sin esto, ante un cliente que
ya tiene Telynet, Sage o SAP, CorteCero obliga a doble entrada de datos. Es el argumento de venta
más fuerte de Polpoo y el hueco más visible del plan.

Acción: no entra en R8, pero necesita una postura clara. ¿R9 lo aborda? ¿O es "integración vía
export/import" como solución bridge? Sin postura, el comercial no puede responder.

**Actor comercial (sales rep view)**
R8 no tiene ningún bloque para este actor. No requiere infraestructura nueva — es una vista
filtrada por `comercial_id` sobre datos ya existentes — pero no está planificado. Polpoo dedica
páginas 25-27 a este actor como pilar diferenciador. Si el cliente tiene un equipo comercial activo,
CorteCero no tiene respuesta.

Acción: considerar para R9. Impacto alto, esfuerzo bajo comparado con ERP.

### P2 — Gaps que limitan la propuesta de valor completa

- **Capa cliente final consolidada**: email / WhatsApp / portal tracking están en R8 (D1-D3) pero
  no implementados. Hasta que existan, no puede afirmarse visibilidad al cliente final.
- **Costes y rentabilidad explotables como argumento**: E3 está en R8 pero no implementado. Sin datos
  reales de coste, el pitch de "controla cuánto te cuesta cada ruta" es solo promesa.
- **Fleet view madura**: F3 está en R8 pero no implementado. El dispatcher todavía no ve todas sus
  rutas activas en un mapa simultáneo.

### P3 — Gaps reales pero de menor peso comercial

- Mapa en app del conductor (R8 solo planifica mapa en dispatcher)
- Gestión de envases (no está en R8)
- Foto de albarán (schema existe en R8, UI no planificada)
- Registro de repostaje / mantenimiento de vehículo desde conductor
- Tracking post-ruta (recorrido real del vehículo)
- Rutas retén / ayudantes de reparto

---

## Lo que R8 añade que Polpoo no menciona

- **ADR (F5)**: restricciones de materiales peligrosos con validación de certificación del vehículo.
  Diferenciador para clientes con carga regulada.
- **ZBE — Zona de Bajas Emisiones Palma (F6)**: restricción por etiqueta ambiental DGT. Específico
  del mercado Mallorca/España.
- **Multi-tenant SaaS estricto**: habilita modelo de reseller o agencia. Polpoo parece single-tenant
  por cliente.
- **Auditoría append-only**: relevante para certificaciones y disputas.

---

## Testimonios Polpoo: qué valoran los clientes reales

1. **Cefrusa** (4 años): "control durante las rutas y comunicación con los choferes y clientes."
   → Visibilidad + comunicación son lo más valorado.

2. **Heyp**: "Los pedidos se sincronizan y se planifican rutas optimizadas."
   → El valor central expresado es la sincronización con ERP. Sin ERP sync, el pitch para este
   perfil de cliente es débil.

3. **Pescados Oliver**: "El sistema aprendió rápido, la secuencia de entregas queda clara, menos
   tiempo en oficina."
   → Valoran onboarding rápido y planificación automática de calidad. El scheduler G1 ataca esto.

4. **Proquibsa**: "Gestión de conformes de entrega e integración con nuestros sistemas internos."
   → POD + integración interna. Sin ERP sync, este cliente tampoco encaja.

Conclusión: 3 de 4 testimonios mencionan sincronización o integración con sistemas internos.
Es la señal más clara del gap estratégico real de R8.

---

## Resumen final

| Dimensión | Como plan R8 | Como estado actual |
|---|---|---|
| Planificador de rutas | ~80% | ~60% (optimize sin constraints avanzados) |
| Seguimiento tiempo real | ~85% | ~50% (SSE OK, ETA/chat/live-edit pendientes) |
| App conductor | ~65% | ~40% (POD+GPS local, sin devoluciones/cobros) |
| Métricas e informes | ~90% | ~5% (dashboard básico existe, el resto no) |
| Notificaciones cliente final | ~90% | ~0% (nada implementado) |
| ERP integrations | 0% | 0% — excluido del plan |
| Actor comercial (sales view) | 0% | 0% — no planificado |
| Hardware | 0% | 0% — fuera de scope |

**Postura honesta para vender o priorizar:**
CorteCero es un producto operativo con base técnica sólida y hoja de ruta correcta para llegar
a Polpoo-completo. No es Polpoo hoy. La ejecución de R8 cierra la mayoría de las brechas
funcionales. Los dos gaps que R8 no cierra — ERP integration y visibilidad del comercial —
son los que más aparecen en los testimonios reales de clientes de Polpoo y requieren una decisión
estratégica antes de R9.
