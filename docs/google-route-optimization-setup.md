# Google Route Optimization API — Checklist de configuración para piloto

**PILOT-HARDEN-001** · Solo para configuración. No implementa features nuevas.

---

## Requisitos previos (a realizar fuera del repo)

### 1. Proyecto GCP

- [ ] Proyecto GCP creado o seleccionado
- [ ] API habilitada: `Cloud Route Optimization API`
  ```
  gcloud services enable routeoptimization.googleapis.com --project=TU_PROJECT_ID
  ```
- [ ] Proyecto en estado de facturación activa (la API es de pago por solicitud)

### 2. Service Account

- [ ] Service account creada con el rol mínimo necesario:
  ```
  gcloud iam service-accounts create cortecero-route-opt \
    --display-name="CorteCero Route Optimization" \
    --project=TU_PROJECT_ID

  gcloud projects add-iam-policy-binding TU_PROJECT_ID \
    --member="serviceAccount:cortecero-route-opt@TU_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/routeoptimization.viewer"
  ```
- [ ] JSON de credenciales descargado y guardado FUERA del repositorio:
  ```
  gcloud iam service-accounts keys create ~/cortecero-sa.json \
    --iam-account=cortecero-route-opt@TU_PROJECT_ID.iam.gserviceaccount.com
  ```
- [ ] Archivo JSON **NO está en el repositorio** (verificar `.gitignore`)

### 3. Cuotas y límites a verificar

| Parámetro | Valor por defecto | Impacto |
|-----------|-------------------|---------|
| Solicitudes por minuto | 60 | Más que suficiente para piloto |
| Vehículos por solicitud | 25 | Límite del tier gratuito |
| Paradas por solicitud | 250 | Suficiente para piloto (≤50 paradas/día) |
| Timeout configurado | 30 s | Ver `GOOGLE_ROUTE_OPTIMIZATION_TIMEOUT_SECONDS` |

---

## Variables de entorno en servidor

Copiar en el archivo `.env` del servidor (NUNCA en el repo):

```env
# Autenticación — Application Default Credentials
GOOGLE_APPLICATION_CREDENTIALS=/ruta/absoluta/al/cortecero-sa.json

# Identificador del proyecto GCP
GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID=tu-gcp-project-id

# Ubicación de la API (no cambiar para uso global)
GOOGLE_ROUTE_OPTIMIZATION_LOCATION=global

# Timeout en segundos para llamadas a la API
GOOGLE_ROUTE_OPTIMIZATION_TIMEOUT_SECONDS=30

# Coordenadas del depósito (WGS-84) — punto de salida de los vehículos
ROUTE_OPTIMIZATION_DEPOT_LAT=39.5696
ROUTE_OPTIMIZATION_DEPOT_LNG=2.6502
```

---

## Verificación de configuración

Comprobar que la integración es real (no mock):

```bash
# Si GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID está vacío → usa mock automáticamente
# Si está configurado → llama a la API real

# Verificar desde el backend:
curl -s http://localhost:8000/routes/ROUTE_ID \
  -H "Authorization: Bearer TOKEN" | jq '.optimization_request_id'
# Si hay optimization_request_id → llamada real a Google realizada
```

---

## Placeholders en el repo

El archivo `backend/.env.example` ya contiene:

```env
GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID=   # dejar vacío → mock activo
# GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/service-account.json
```

**NUNCA** poner credenciales reales en `.env.example`, `.env`, o cualquier archivo versionado.

---

## Verificar `.gitignore`

Confirmar que las siguientes entradas están presentes en `.gitignore`:

```
*.json            # Credenciales descargadas
.env              # Variables de entorno locales
.env.local
.env.production
*-sa.json         # Service account keys
*-service-account.json
```

---

## Modo de fallback (desarrollo y tests)

Si `GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID` está vacío, el sistema usa automáticamente
`MockRouteOptimizationProvider` (`backend/app/optimization/mock_provider.py`).

El mock devuelve rutas en el orden original sin optimización real.
Todos los tests de CI usan el mock — **nunca** se llama a la API real en CI.
