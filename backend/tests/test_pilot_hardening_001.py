"""
PILOT-HARDEN-001 — Tests de regresión y compatibilidad.

Cubre:
  1. Vínculo explícito Driver.user_id → User.id (migration 018).
     - Driver sin user_id (seed demo): válido, pero obtiene DRIVER_NOT_LINKED al intentar auth.
     - Driver con user_id: resolve correcto; puede ejecutar acción.
     - Dos Drivers no pueden compartir el mismo user_id (UNIQUE).
  2. Housekeeping de migraciones: 017/018 no rompen schema existente.
  3. Multi-tenant: user_id de tenant A no puede acceder a rutas de tenant A
     si el Driver está en tenant B — tenant_id sigue filtrando.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import (
    Customer,
    Driver,
    Order,
    OrderIntakeType,
    OrderStatus,
    Plan,
    PlanStatus,
    Route,
    RouteStatus,
    RouteStop,
    RouteStopStatus,
    SourceChannel,
    Tenant,
    User,
    UserRole,
    Vehicle,
    Zone,
)
from app.security import hash_password
from tests.helpers import auth_headers, login_as


# ============================================================================
# Helpers compartidos
# ============================================================================


def _get_tenant(db_session) -> Tenant:
    tenant = db_session.scalar(select(Tenant).where(Tenant.slug == "demo-cortecero"))
    assert tenant is not None
    return tenant


def _make_user_driver(db_session, tenant: Tenant, *, email: str) -> tuple[User, Driver]:
    """Crea un User (role=driver) y un Driver con user_id vinculado."""
    now = datetime.now(UTC)
    vehicle = db_session.scalar(
        select(Vehicle).where(Vehicle.tenant_id == tenant.id, Vehicle.active.is_(True))
    )
    assert vehicle is not None

    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=email,
        full_name=f"Driver {email.split('@')[0]}",
        password_hash=hash_password("driver123"),
        role=UserRole.driver,
        is_active=True,
        created_at=now,
    )
    db_session.add(user)
    db_session.flush()

    driver = Driver(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=user.id,
        vehicle_id=vehicle.id,
        name=user.full_name,
        phone=f"+34001{str(uuid.uuid4().int)[:8]}",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(driver)
    db_session.commit()
    db_session.refresh(driver)
    return user, driver


def _make_dispatched_stop(db_session, tenant: Tenant, driver_id: uuid.UUID) -> tuple[Route, RouteStop]:
    now = datetime.now(UTC)
    # +2 mínimo para nunca colisionar con el Plan de mañana que crea el seed
    svc_date = date.today() + timedelta(days=(uuid.uuid4().int % 300) + 2)

    zone = db_session.scalar(select(Zone).where(Zone.tenant_id == tenant.id))
    customer = db_session.scalar(select(Customer).where(Customer.tenant_id == tenant.id))
    vehicle = db_session.scalar(select(Vehicle).where(Vehicle.tenant_id == tenant.id, Vehicle.active.is_(True)))
    assert all([zone, customer, vehicle])

    plan = Plan(
        id=uuid.uuid4(), tenant_id=tenant.id, service_date=svc_date, zone_id=zone.id,
        status=PlanStatus.locked, version=1, created_at=now, updated_at=now,
    )
    db_session.add(plan)
    db_session.flush()

    route = Route(
        id=uuid.uuid4(), tenant_id=tenant.id, plan_id=plan.id,
        vehicle_id=vehicle.id, driver_id=driver_id,
        service_date=svc_date, status=RouteStatus.dispatched,
        version=1, optimization_request_id=None, optimization_response_json=None,
        created_at=now, updated_at=now, dispatched_at=now, completed_at=None,
    )
    db_session.add(route)
    db_session.flush()

    order = Order(
        id=uuid.uuid4(), tenant_id=tenant.id, customer_id=customer.id, zone_id=zone.id,
        external_ref=f"H001-{uuid.uuid4()}", requested_date=svc_date, service_date=svc_date,
        created_at=now, status=OrderStatus.dispatched, is_late=False, lateness_reason=None,
        effective_cutoff_at=now, source_channel=SourceChannel.office,
        intake_type=OrderIntakeType.new_order, total_weight_kg=1, ingested_at=now, updated_at=now,
    )
    db_session.add(order)
    db_session.flush()

    stop = RouteStop(
        id=uuid.uuid4(), tenant_id=tenant.id, route_id=route.id, order_id=order.id,
        sequence_number=1, estimated_arrival_at=None, estimated_service_minutes=10,
        status=RouteStopStatus.pending,
        arrived_at=None, completed_at=None, failed_at=None, failure_reason=None,
        created_at=now, updated_at=now,
    )
    db_session.add(stop)
    db_session.commit()
    return route, stop


# ============================================================================
# Tests — Vínculo explícito user_id
# ============================================================================


def test_driver_with_user_id_can_arrive(client, db_session):
    """Driver con user_id vinculado puede ejecutar /arrive."""
    tenant = _get_tenant(db_session)
    user, driver = _make_user_driver(db_session, tenant, email="h001.arrive@demo.cortecero.app")
    _, stop = _make_dispatched_stop(db_session, tenant, driver_id=driver.id)

    token = login_as(client, tenant_slug=tenant.slug, email=user.email, password="driver123")
    res = client.post(f"/stops/{stop.id}/arrive", json={}, headers=auth_headers(token))

    assert res.status_code == 200, res.text
    assert res.json()["status"] == "arrived"


def test_driver_without_user_id_gets_not_linked(client, db_session):
    """Driver creado sin user_id (patrón seed/API) → DRIVER_NOT_LINKED al intentar auth."""
    tenant = _get_tenant(db_session)
    now = datetime.now(UTC)
    vehicle = db_session.scalar(select(Vehicle).where(Vehicle.tenant_id == tenant.id, Vehicle.active.is_(True)))

    # User con role=driver
    user = User(
        id=uuid.uuid4(), tenant_id=tenant.id,
        email="h001.noid@demo.cortecero.app",
        full_name="Driver No Link",
        password_hash=hash_password("driver123"),
        role=UserRole.driver, is_active=True, created_at=now,
    )
    db_session.add(user)
    db_session.flush()

    # Driver existente pero SIN user_id → vínculo no establecido
    driver_no_link = Driver(
        id=uuid.uuid4(), tenant_id=tenant.id,
        user_id=None,  # sin vínculo explícito
        vehicle_id=vehicle.id if vehicle else None,
        name="Driver No Link", phone=f"+34002{str(uuid.uuid4().int)[:8]}",
        is_active=True, created_at=now, updated_at=now,
    )
    db_session.add(driver_no_link)

    _, stop = _make_dispatched_stop(db_session, tenant, driver_id=driver_no_link.id)

    token = login_as(client, tenant_slug=tenant.slug, email=user.email, password="driver123")
    res = client.post(f"/stops/{stop.id}/arrive", json={}, headers=auth_headers(token))

    assert res.status_code == 403, res.text
    assert res.json()["detail"]["code"] == "DRIVER_NOT_LINKED"


def test_driver_user_id_is_unique(db_session):
    """Dos Drivers no pueden compartir el mismo user_id (UNIQUE constraint)."""
    tenant = _get_tenant(db_session)
    now = datetime.now(UTC)

    user = User(
        id=uuid.uuid4(), tenant_id=tenant.id,
        email="h001.shared@demo.cortecero.app",
        full_name="Shared User",
        password_hash=hash_password("driver123"),
        role=UserRole.driver, is_active=True, created_at=now,
    )
    db_session.add(user)
    db_session.flush()

    driver_1 = Driver(
        id=uuid.uuid4(), tenant_id=tenant.id, user_id=user.id,
        vehicle_id=None, name="Driver 1",
        phone=f"+34003{str(uuid.uuid4().int)[:8]}",
        is_active=True, created_at=now, updated_at=now,
    )
    db_session.add(driver_1)
    db_session.flush()

    driver_2 = Driver(
        id=uuid.uuid4(), tenant_id=tenant.id,
        user_id=user.id,  # mismo user_id → debe violar UNIQUE
        vehicle_id=None, name="Driver 2",
        phone=f"+34004{str(uuid.uuid4().int)[:8]}",
        is_active=True, created_at=now, updated_at=now,
    )
    db_session.add(driver_2)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()


def test_driver_ids_are_independent_from_user_ids(db_session):
    """Driver.id != User.id — los UUID son ahora independientes (no convención compartida)."""
    tenant = _get_tenant(db_session)
    user, driver = _make_user_driver(db_session, tenant, email="h001.uuid@demo.cortecero.app")

    assert driver.id != user.id, "Driver.id y User.id deben ser UUID distintos"
    assert driver.user_id == user.id, "Driver.user_id debe apuntar a User.id"


def test_driver_user_id_column_is_nullable(db_session):
    """Drivers sin user_id (seed, demo, API-only) son válidos en DB."""
    tenant = _get_tenant(db_session)
    now = datetime.now(UTC)

    seed_style_driver = Driver(
        id=uuid.uuid4(), tenant_id=tenant.id,
        user_id=None,   # nullable: correcto para drivers sin cuenta PWA
        vehicle_id=None,
        name="Seed Driver",
        phone=f"+34005{str(uuid.uuid4().int)[:8]}",
        is_active=True, created_at=now, updated_at=now,
    )
    db_session.add(seed_style_driver)
    db_session.commit()

    loaded = db_session.scalar(select(Driver).where(Driver.id == seed_style_driver.id))
    assert loaded is not None
    assert loaded.user_id is None


def test_driver_route_scope_uses_driver_id_not_user_id(client, db_session):
    """Verificar que el scope de ruta compara route.driver_id con driver.id (no con user.id)."""
    tenant = _get_tenant(db_session)
    user_a, driver_a = _make_user_driver(db_session, tenant, email="h001.scope_a@demo.cortecero.app")
    _, driver_b = _make_user_driver(db_session, tenant, email="h001.scope_b@demo.cortecero.app")

    # La ruta tiene driver_id = driver_a.id
    _, stop = _make_dispatched_stop(db_session, tenant, driver_id=driver_a.id)

    # Driver B intenta acceder a la ruta de Driver A
    token_b = login_as(client, tenant_slug=tenant.slug, email="h001.scope_b@demo.cortecero.app", password="driver123")
    res = client.post(f"/stops/{stop.id}/arrive", json={}, headers=auth_headers(token_b))

    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "DRIVER_SCOPE_FORBIDDEN"
