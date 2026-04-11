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
    routing,
)


app = FastAPI(title=settings.app_name, version="1.0.0")

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
app.include_router(routing.router)
