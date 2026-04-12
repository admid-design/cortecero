# /smoke-google

Ejecuta el smoke test de Google Route Optimization y captura evidencia.

## Instrucciones

### Prerrequisitos (verificar antes de ejecutar)

1. Backend corriendo: `docker compose up -d postgres backend`
2. Google credentials disponibles: `~/.config/kelko/google/route-optimization-sa.json`
3. `GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID=samurai-system` configurado
4. Dataset geo-ready disponible (verificar con modo LIST)

### Paso 1 — Verificar estado del backend

```bash
curl -s http://localhost:8000/health
```

Esperado: `{"status": "ok"}`

### Paso 2 — Listar rutas disponibles

```bash
SMOKE_LIST_ROUTES=1 python3 backend/scripts/smoke_google_optimization.py
```

Si no hay rutas draft, continuar con Paso 3.

### Paso 3 — Crear ruta y optimizar (si no hay ruta existente)

```bash
SMOKE_CREATE_ROUTE=1 \
GOOGLE_APPLICATION_CREDENTIALS=~/.config/kelko/google/route-optimization-sa.json \
GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID=samurai-system \
python3 backend/scripts/smoke_google_optimization.py
```

Si falla con `MISSING_GEO` o `no hay plan locked`:

```bash
# Preparar dataset geo-ready
python3 backend/scripts/prepare_google_smoke_dataset.py
# Luego reintentar SMOKE_CREATE_ROUTE
```

### Paso 4 — Optimizar ruta existente (modo directo)

```bash
CORTECERO_ROUTE_ID=<uuid-de-ruta-draft> \
GOOGLE_APPLICATION_CREDENTIALS=~/.config/kelko/google/route-optimization-sa.json \
GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID=samurai-system \
python3 backend/scripts/smoke_google_optimization.py
```

### Criterios de GO

- HTTP 200 en `POST /routes/{id}/optimize`
- `status == "planned"` en la ruta
- `optimization_request_id` no vacío
- `provider == "google"` en el response
- `estimated_arrival_at` en todas las paradas
- Secuencia reordenada respecto al draft

## Output esperado de este comando

Devuelve:

```
Smoke ejecutado: sí/no
Modo: LIST | CREATE | ROUTE_ID
Resultado HTTP: <status code>
Criterios GO:
  - HTTP 200: GO/NO-GO
  - status=planned: GO/NO-GO
  - request_id poblado: GO/NO-GO
  - provider=google: GO/NO-GO
  - ETAs en paradas: GO/NO-GO
  - secuencia reordenada: GO/NO-GO
Veredicto: GO / NO-GO
Bloqueador (si NO-GO): <descripción exacta>
```
