# Reglas — Review y cierre de bloques

Aplica cuando vas a cerrar o revisar un bloque.

## Criterios de cierre por tipo

### IMPLEMENTATION / HARDENING

- [ ] Cambio mínimo suficiente para el objetivo del bloque
- [ ] No hay cambios laterales no declarados
- [ ] Tests del área tocada en verde
- [ ] CI en verde (`backend-tests`, `frontend-smoke`, `openapi-check`)
- [ ] `openapi/openapi-v1.yaml` alineado si tocaste endpoints
- [ ] `frontend/lib/api.ts` alineado si cambió algún path
- [ ] Commit descriptivo con tipo convencional (`feat`, `fix`, `docs`, `refactor`, `test`)

### SPIKE

- [ ] Pregunta técnica definida al inicio
- [ ] Respuesta clara y verificable
- [ ] Evidencia real (no narrativa)
- [ ] Huecos declarados
- [ ] Decisión recomendada explícita

### DEMO

- [ ] Test green sobre el bloque
- [ ] Evidence green: existe salida real del flujo objetivo
- [ ] Comando reproducible para producir la evidencia
- [ ] No se sobreafirma ninguna capacidad no verificada
- [ ] Qué sigue siendo manual o local declarado explícitamente

### DOCS

- [ ] Solo documenta lo que es real y verificado
- [ ] Distingue implementado / verificado / no verificado / bloqueos
- [ ] No hay afirmaciones aspiracionales sin nota explícita

## Checklist de honestidad antes de cerrar

Antes de declarar cualquier bloque cerrado, responde:

1. ¿Ejecuté los tests relevantes y los vi pasar?
2. ¿Hay algún lado effect en archivos que no debería haber tocado?
3. ¿El contrato OpenAPI sigue alineado con el runtime?
4. ¿Hay algún prerrequisito no resuelto que haga la evidencia imposible?
5. ¿Estoy afirmando algo que no puedo demostrar hoy?

Si la respuesta a 4 o 5 es sí → el bloque es BLOQUEADO o PARCIAL, no cerrado.

## Estados válidos de cierre

| Estado | Significa |
|--------|-----------|
| `CERRADO_LOCAL` | Test green local, sin CI remoto aún |
| `CERRADO_CON_EVIDENCIA_LOCAL` | Evidence green local, sin CI remoto aún |
| `PROMULGADO` | CI remoto en verde, commit en main |
| `BLOQUEADO` | Hay prerrequisito no resuelto que impide cerrar |
| `PARCIAL` | Parte del alcance cerrado, parte pendiente |

No uses "done", "ready", "closed" sin uno de estos estados.

## Formato de salida obligatorio

```
Bloque: <nombre>
Tipo: <tipo>
Objetivo: <qué resuelve>
Commit: <sha>
Archivos tocados: <lista>
Validación ejecutada: <qué se corrió y resultado>
Resultado: <output real>
Huecos: <qué no se verificó>
Riesgos: <qué no conviene afirmar>
Estado final: <estado>
```
