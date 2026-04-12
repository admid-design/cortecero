# /demo-check

Evalúa qué es demostrable hoy en CorteCero y qué no.

## Instrucciones

Genera una evaluación honesta del estado actual demostrable.
No asumas capacidades que no están en `docs/as-is.md` o que no puedas verificar en el código.

### 1. Verificar backend running

```bash
curl -s http://localhost:8000/health
```

### 2. Verificar flujo dispatcher

- ¿Existen rutas en estado draft/planned? (`GET /routes`)
- ¿El panel dispatcher es funcional? (`DispatcherRoutingCard`)

### 3. Verificar flujo conductor

- ¿La PWA carga? (`DriverRoutingCard`)
- ¿Los endpoints arrive/complete/fail/skip responden?

### 4. Verificar optimize

- ¿Hay ruta con paradas geo-ready?
- ¿`POST /routes/{id}/optimize` devuelve 200?
- ¿Con mock provider o Google real?

### 5. Evaluar gaps vs objetivo Routific-like

Contrasta contra la matriz de `docs/as-is.md`.

## Output esperado

```
Estado del backend: UP / DOWN
Flujo dispatcher: DEMOSTRABLE / NO DEMOSTRABLE — <razón>
PWA conductor: DEMOSTRABLE / NO DEMOSTRABLE — <razón>
Optimize mock: DEMOSTRABLE / NO DEMOSTRABLE
Optimize Google: DEMOSTRABLE / NO DEMOSTRABLE — <razón si no>

Qué puedes enseñar hoy:
  - <capacidad 1>
  - <capacidad 2>

Qué NO debes afirmar hoy:
  - <afirmación peligrosa 1>
  - <afirmación peligrosa 2>

Siguiente acción para acercar a demo Routific-like:
  <bloque mínimo concreto>
```
