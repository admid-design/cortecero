from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
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


@app.get("/debug/db")
def debug_db(db: Session = Depends(get_db)):
    from sqlalchemy import text
    results = {}
    # Test 1: raw orders columns
    try:
        row = db.execute(text("SELECT id, status FROM orders LIMIT 1")).fetchone()
        results["orders_basic"] = {"ok": True, "row": str(row)}
    except Exception as e:
        results["orders_basic"] = {"ok": False, "error": type(e).__name__, "detail": str(e)}
    # Test 2: requires_adr column (migration 024)
    try:
        row = db.execute(text("SELECT id, requires_adr FROM orders LIMIT 1")).fetchone()
        results["orders_requires_adr"] = {"ok": True, "row": str(row)}
    except Exception as e:
        results["orders_requires_adr"] = {"ok": False, "error": type(e).__name__, "detail": str(e)}
    # Test 3: source_channel column
    try:
        row = db.execute(text("SELECT id, source_channel FROM orders LIMIT 1")).fetchone()
        results["orders_source_channel"] = {"ok": True, "row": str(row)}
    except Exception as e:
        results["orders_source_channel"] = {"ok": False, "error": type(e).__name__, "detail": str(e)}
    # Test 4: routes trip_number (migration 023)
    try:
        row = db.execute(text("SELECT id, trip_number FROM routes LIMIT 1")).fetchone()
        results["routes_trip_number"] = {"ok": True, "row": str(row)}
    except Exception as e:
        results["routes_trip_number"] = {"ok": False, "error": type(e).__name__, "detail": str(e)}
    # Test 5: order_status enum values in DB
    try:
        rows = db.execute(text("SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE pg_type.typname = 'order_status' ORDER BY enumsortorder")).fetchall()
        results["order_status_values"] = {"ok": True, "values": [r[0] for r in rows]}
    except Exception as e:
        results["order_status_values"] = {"ok": False, "error": type(e).__name__, "detail": str(e)}
    # Test 6: full ORM Order load
    try:
        from app.models import Order
        from sqlalchemy import select
        order = db.execute(select(Order).limit(1)).scalar_one_or_none()
        results["orm_order"] = {"ok": True, "id": str(order.id) if order else None}
    except Exception as e:
        results["orm_order"] = {"ok": False, "error": type(e).__name__, "detail": str(e)}
    return results


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
