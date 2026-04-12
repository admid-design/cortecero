# /review-block

Revisa el bloque activo antes de declararlo cerrado.

## Instrucciones

El usuario te dará un bloque (nombre, tipo, alcance) o lo inferirás del contexto reciente.

Ejecuta este checklist completo y devuelve el resultado:

### 1. Verificación de cambios

- Lista todos los archivos modificados en el bloque
- Verifica que no hay cambios fuera del alcance declarado
- Verifica que no hay TODOs o código comentado pendiente de resolver

### 2. Verificación contractual

- Si se tocaron endpoints: ¿está `openapi/openapi-v1.yaml` alineado?
- Si cambió algún path: ¿está `frontend/lib/api.ts` alineado?
- Si hubo cambio de schema: ¿están los tipos frontend actualizados?

### 3. Verificación de tests

- ¿Cuáles tests del área relevante están en verde?
- ¿Hay tests fallando? Si sí, ¿son esperados (e.g., test_routing_bloque_e.py sin Google) o no?
- ¿El CI remoto está en verde sobre `main`?

### 4. Verificación de evidencia (solo para DEMO/SPIKE)

- ¿Hay salida real verificable del flujo objetivo?
- ¿Existe un comando reproducible que produce esa evidencia?
- ¿Qué prerequisitos necesita ese comando?

### 5. Honestidad

- ¿Hay algo que parece funcionar pero no se verificó?
- ¿Hay afirmaciones en el output del bloque que no tienen respaldo?

## Output esperado

```
Bloque: <nombre>
Tipo: <tipo>
Alcance declarado: <qué debía hacer>
Cambios reales: <qué se tocó realmente>
Contractual: OK / PROBLEMA — <detalle>
Tests: OK / FALLANDO — <detalle>
Evidencia: EXISTE / FALTA — <detalle>
Afirmaciones sin respaldo: <lista o "ninguna">
Veredicto: CERRADO / PARCIAL / BLOQUEADO
Estado sugerido: <CERRADO_LOCAL | PROMULGADO | BLOQUEADO | PARCIAL>
```
