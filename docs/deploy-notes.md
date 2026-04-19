# Deploy Notes — CorteCero

Notas operativas sobre deploys, configuración de Vercel y fallos conocidos.
No son incidentes formales — son lecciones que costaron tiempo real y son fáciles de repetir.

---

## DEPLOY-001 — Vercel no crea deployment por config inválida en `backend/vercel.json`

**Fecha detectado:** 2026-04-20  
**Fix:** commit `7a5e159`  
**Afecta:** `cortecero-api` (backend FastAPI en Vercel)

### Síntoma

Commits al backend llegan a GitHub y el push tiene éxito, pero no aparece ningún deployment record en Vercel. La UI de Vercel no muestra error. El proyecto `cortecero-api` simplemente no actualiza. Da la impresión de que el deploy está en cola o perdido.

### Causa raíz

`backend/vercel.json` tenía simultáneamente las claves `"functions"` y `"builds"`:

```json
{
  "functions": {
    "api/index.py": { "maxDuration": 60 }
  },
  "builds": [
    { "src": "api/index.py", "use": "@vercel/python", "config": { "maxLambdaSize": "50mb" } }
  ],
  "routes": [{ "src": "/(.*)", "dest": "api/index.py" }]
}
```

En este proyecto y configuración, la combinación `"functions"` + `"builds"` en `backend/vercel.json` rompió el deploy silenciosamente. Vercel rechaza la configuración antes de crear ningún deployment record — sin log visible, sin error en GitHub Actions.

### Fix

Eliminar el bloque `"functions"` completo. La configuración correcta:

```json
{
  "version": 2,
  "builds": [
    { "src": "api/index.py", "use": "@vercel/python", "config": { "maxLambdaSize": "50mb" } }
  ],
  "routes": [{ "src": "/(.*)", "dest": "api/index.py" }]
}
```

**Nota:** `maxDuration` quedó sin configurar. Si se necesita timeout extendido en Vercel Pro, usar la clave `"functions"` sola, sin `"builds"`.

### Impacto que desbloqueó

Todos los commits desde `dc65fd9` hasta `7a5e159` no habían creado deployment en Vercel. Al resolverlo, el fix de seed `f4cdd8f` (User sin campo `updated_at`) llegó por fin a Neon, habilitando cold start correcto → cuentas de conductores demo activas → driver login operativo en dispositivo real.

### Cómo diagnosticar si vuelve a pasar

1. Push exitoso en GitHub pero sin deployment record en Vercel.
2. `list_deployments` vía MCP devuelve el último deployment como anterior al commit más reciente.
3. No hay build logs — porque Vercel no llegó a iniciar ningún build.

**Primer paso de diagnóstico:** revisar `backend/vercel.json` en busca de claves incompatibles o configuración malformada.

### Aprendizaje operativo

- CI verde (GitHub Actions) no implica deployment exitoso en Vercel.
- Vercel puede rechazar una configuración sin crear ningún registro — el fallo no deja rastro visible.
- El canal de verificación correcto es `list_deployments` o el dashboard de Vercel, no solo el status del push en GitHub.
- Ante "no veo mis cambios en producción tras varios commits": primero verificar que exista un deployment record reciente antes de buscar el bug en el código.
