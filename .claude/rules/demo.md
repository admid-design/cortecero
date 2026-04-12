# Reglas — Bloques DEMO

Aplica cuando el bloque es de tipo DEMO o cuando preparas evidencia para mostrar a dirección.

## Principio central

Un bloque DEMO no cierra por test green. Cierra por evidence green.

Evidence green = existe salida real verificable del flujo objetivo que puedes reproducir con un comando.

## Qué debes entregar en un bloque DEMO

- Qué parte del flujo ya era real antes del bloque
- Qué impedía la demo antes del bloque
- Qué cambió exactamente
- Qué comando o flujo exacto produce la evidencia
- Qué sigue siendo manual (no automatizable aún)
- Qué sigue siendo local (no en producción)
- Qué NO debe sobreafirmarse ante dirección

## Lenguaje prohibido sin evidencia real

No uses ninguna de estas afirmaciones sin poder respaldarla con output real:

- "operativo e2e"
- "listo para dirección"
- "demo-ready"
- "reproducible"
- "pilot-ready"
- "tráfico en tiempo real"
- "seguimiento en tiempo real"
- "IA integrada"
- "mapa operativo"
- "fleet view"
- "proof of delivery"

## Prerrequisitos de demo

Si la demo requiere:
- dataset específico → créalo o documenta cómo crearlo
- credenciales privadas → indica cuáles y dónde
- estado previo de entidades → indica cómo llegar a ese estado
- backend corriendo → indica el comando exacto

No declares la demo lista si alguno de estos prerrequisitos no está resuelto.

## Gap actual CorteCero vs objetivo Routific-like

Ver `docs/as-is.md` para el estado verificado completo.

Capacidades NO demostrables hoy:
- Mapa operativo — no hay SDK de mapas
- Seguimiento GPS en tiempo real — no existe
- ETA dinámico — solo ETA estático post-optimize
- Proof of delivery — no existe
- Fleet view — no existe
- Asistente IA — no existe en ninguna capa

Capacidades demostrables hoy:
- Flujo dispatcher completo (plan → dispatch → optimize → paradas)
- PWA conductor (arrive/complete/fail/skip/incidencias)
- Gestión de excepciones
- Panel operativo

## Preparación de dataset para smoke

```bash
# Preparar órdenes geo-ready en tenant demo
python3 backend/scripts/prepare_google_smoke_dataset.py

# Verificar que hay rutas disponibles
SMOKE_LIST_ROUTES=1 python3 backend/scripts/smoke_google_optimization.py
```
