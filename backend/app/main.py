# cortecero-api — fuerza redeploy con seed fix (f4cdd8f)
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    admin_customers,
    admin_products,
    admin_tenant_settings,
    admin_users,
    admin_zones,
    audit,
    auth,
    dashboard,
    drivers,
    exports,
    exceptions,
    orders,
    plans,
    route_templates,
    routing,
)

_INSECURE_JWT_DEFAULT = "change-me-in-production"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Guard: rechaza arranque en producción con secret por defecto.
    if settings.environment != "dev" and settings.jwt_secret_key == _INSECURE_JWT_DEFAULT:
        raise RuntimeError(
            "JWT_SECRET_KEY no puede ser el valor por defecto en entornos no-dev. "
            "Setea JWT_SECRET_KEY en las variables de entorno."
        )
    # Seed idempotente: aplica datos demo en cada cold start (Vercel serverless).
    # En local/tests la llamada es no-op si los datos ya existen.
    from app.seed import seed
    seed()
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(orders.router)
app.include_router(exports.router)
app.include_router(plans.router)
app.include_router(exceptions.router)
app.include_router(dashboard.router)
app.include_router(audit.router)
app.include_router(admin_zones.router)
app.include_router(admin_customers.router)
app.include_router(admin_products.router)
app.include_router(admin_users.router)
app.include_router(admin_tenant_settings.router)
app.include_router(drivers.router)
app.include_router(route_templates.router)
app.include_router(routing.router)
