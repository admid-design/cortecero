"""
Bloque A3 — GPS Driver Position (GPS-001)

Cubre:
  - POST /driver/location   happy path (conductor con ruta in_progress)
  - POST /driver/location   ruta no in_progress → 409 ROUTE_NOT_IN_PROGRESS
  - POST /driver/location   ruta de otro tenant → 404
  - POST /driver/location   sin autenticación → 401
  - GET  /routes/{id}/driver-position  happy path
  - GET  /routes/{id}/driver-position  sin posición → 404
  - GET  /routes/{id}/driver-position  ruta de otro tenant → 404
  - GET  /routes/active-positions      happy path (logistics)
"""

import uuid
from datetime import UTC, date, datetime, time

import pytest
from sqlalchemy import select

from app.models import (
    Customer,
    Driver,
    DriverPosition,
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


# ── Helpers ───────────────────────────────────────────────────────────────────


def _demo_tenant(db_session) -> Tenant:
    tenant = db_session.scalar(select(Tenant).where(Tenant.slug == "demo-cortecero"))
    assert tenant is not None
    return tenant


def _logistics_token(client, tenant_slug: str = "demo-cortecero") -> str:
    return login_as(client, tenant_slug=tenant_slug, email="logistics@demo.cortecero.app", password="logistics123")


def _create_driver_user(db_session, tenant: Tenant, *, email: str, password: str = "driver123") -> tuple[User, Driver]:
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
        password_hash=hash_password(password),
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
        phone=f"+34000{str(uuid.uuid4().int)[:8]}",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(driver)
    db_session.commit()
    db_session.refresh(driver)
    return user, driver


def _create_tenant(db_session, *, slug: str) -> Tenant:
    tenant = Tenant(
        id=uuid.uuid4(),
        name=f"Tenant {slug}",
        slug=slug,
        default_cutoff_time=time(17, 0),
        default_timezone="Europe/Madrid",
        created_at=datetime.now(UTC),
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _build_route(
    db_session,
    tenant_id: uuid.UUID,
    driver: Driver,
    *,
    route_status: RouteStatus = RouteStatus.in_progress,
) -> Route:
    now = datetime.now(UTC)
    svc_date = date.today()

    zone = db_session.scalar(select(Zone).where(Zone.tenant_id == tenant_id))
    assert zone is not None

    plan = Plan(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        service_date=svc_date,
        zone_id=zone.id,
        status=PlanStatus.locked,
        version=1,
        created_at=now,
        updated_at=now,
    )
    db_session.add(plan)
    db_session.flush()

    route = Route(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        plan_id=plan.id,
        vehicle_id=driver.vehicle_id,
        driver_id=driver.id,
        service_date=svc_date,
        status=route_status,
        version=1,
        optimization_request_id=None,
        optimization_response_json=None,
        created_at=now,
        updated_at=now,
        dispatched_at=now if route_status not in (RouteStatus.draft, RouteStatus.planned) else None,
        completed_at=None,
    )
    db_session.add(route)
    db_session.commit()
    db_session.refresh(route)
    return route


# ── POST /driver/location ─────────────────────────────────────────────────────


def test_driver_location_happy_path(client, db_session):
    """Conductor con ruta in_progress → 204, posición guardada en DB."""
    tenant = _demo_tenant(db_session)
    email = f"gps-d1-{uuid.uuid4().hex[:6]}@test.cortecero.app"
    user, driver = _create_driver_user(db_session, tenant, email=email)
    route = _build_route(db_session, tenant.id, driver, route_status=RouteStatus.in_progress)

    token = login_as(client, tenant_slug="demo-cortecero", email=email, password="driver123")

    payload = {
        "route_id": str(route.id),
        "lat": 40.4168,
        "lng": -3.7038,
        "accuracy_m": 12.5,
        "speed_kmh": 35.0,
        "heading": 90.0,
    }
    res = client.post("/driver/location", json=payload, headers=auth_headers(token))
    assert res.status_code == 204, res.text

    # Verificar que se persistió en DB
    saved = db_session.scalar(
        select(DriverPosition).where(DriverPosition.route_id == route.id)
    )
    assert saved is not None
    assert float(saved.lat) == pytest.approx(40.4168, abs=1e-4)
    assert float(saved.lng) == pytest.approx(-3.7038, abs=1e-4)


def test_driver_location_optional_fields(client, db_session):
    """Solo lat/lng son obligatorios; accuracy/speed/heading son opcionales."""
    tenant = _demo_tenant(db_session)
    email = f"gps-d2-{uuid.uuid4().hex[:6]}@test.cortecero.app"
    user, driver = _create_driver_user(db_session, tenant, email=email)
    route = _build_route(db_session, tenant.id, driver, route_status=RouteStatus.in_progress)

    token = login_as(client, tenant_slug="demo-cortecero", email=email, password="driver123")

    payload = {
        "route_id": str(route.id),
        "lat": 40.4168,
        "lng": -3.7038,
    }
    res = client.post("/driver/location", json=payload, headers=auth_headers(token))
    assert res.status_code == 204, res.text


def test_driver_location_route_not_in_progress_returns_409(client, db_session):
    """Ruta en estado dispatched (no in_progress) → 409 ROUTE_NOT_IN_PROGRESS."""
    tenant = _demo_tenant(db_session)
    email = f"gps-d3-{uuid.uuid4().hex[:6]}@test.cortecero.app"
    user, driver = _create_driver_user(db_session, tenant, email=email)
    route = _build_route(db_session, tenant.id, driver, route_status=RouteStatus.dispatched)

    token = login_as(client, tenant_slug="demo-cortecero", email=email, password="driver123")

    payload = {
        "route_id": str(route.id),
        "lat": 40.4168,
        "lng": -3.7038,
    }
    res = client.post("/driver/location", json=payload, headers=auth_headers(token))
    assert res.status_code == 409, res.text
    assert res.json()["detail"]["code"] == "ROUTE_NOT_IN_PROGRESS"


def test_driver_location_unauthenticated_returns_401(client, db_session):
    """Sin token → 401."""
    payload = {
        "route_id": str(uuid.uuid4()),
        "lat": 40.4168,
        "lng": -3.7038,
    }
    res = client.post("/driver/location", json=payload)
    assert res.status_code == 401, res.text


def test_driver_location_route_of_other_tenant_returns_404(client, db_session):
    """Conductor intenta publicar posición en ruta de otro tenant → 404."""
    tenant = _demo_tenant(db_session)
    email = f"gps-d4-{uuid.uuid4().hex[:6]}@test.cortecero.app"
    user, driver = _create_driver_user(db_session, tenant, email=email)

    # Crear ruta en otro tenant
    other_tenant = _create_tenant(db_session, slug=f"other-gps-{uuid.uuid4().hex[:6]}")
    # Route mínima en otro tenant sin driver real asignado
    now = datetime.now(UTC)
    zone_other = Zone(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        name="Zona GPS other",
        default_cutoff_time=time(17, 0),
        timezone="Europe/Madrid",
        active=True,
        created_at=now,
    )
    db_session.add(zone_other)
    vehicle_other = Vehicle(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        name="Van GPS other",
        code="VGPSO",
        capacity_kg=1000.0,
        active=True,
        created_at=now,
    )
    db_session.add(vehicle_other)
    db_session.flush()

    plan_other = Plan(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        service_date=date.today(),
        zone_id=zone_other.id,
        status=PlanStatus.locked,
        version=1,
        created_at=now,
        updated_at=now,
    )
    db_session.add(plan_other)
    db_session.flush()

    route_other = Route(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        plan_id=plan_other.id,
        vehicle_id=vehicle_other.id,
        driver_id=None,
        service_date=date.today(),
        status=RouteStatus.in_progress,
        version=1,
        optimization_request_id=None,
        optimization_response_json=None,
        created_at=now,
        updated_at=now,
        dispatched_at=now,
        completed_at=None,
    )
    db_session.add(route_other)
    db_session.commit()

    token = login_as(client, tenant_slug="demo-cortecero", email=email, password="driver123")
    payload = {
        "route_id": str(route_other.id),
        "lat": 40.4168,
        "lng": -3.7038,
    }
    res = client.post("/driver/location", json=payload, headers=auth_headers(token))
    assert res.status_code == 404, res.text


# ── GET /routes/{id}/driver-position ─────────────────────────────────────────


def test_get_driver_position_happy_path(client, db_session):
    """Dispatcher recupera la última posición del conductor."""
    tenant = _demo_tenant(db_session)
    email = f"gps-d5-{uuid.uuid4().hex[:6]}@test.cortecero.app"
    user, driver = _create_driver_user(db_session, tenant, email=email)
    route = _build_route(db_session, tenant.id, driver, route_status=RouteStatus.in_progress)

    driver_token = login_as(client, tenant_slug="demo-cortecero", email=email, password="driver123")
    client.post(
        "/driver/location",
        json={"route_id": str(route.id), "lat": 40.42, "lng": -3.71},
        headers=auth_headers(driver_token),
    )

    logistics_token = _logistics_token(client)
    res = client.get(f"/routes/{route.id}/driver-position", headers=auth_headers(logistics_token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["route_id"] == str(route.id)
    assert abs(body["lat"] - 40.42) < 0.001
    assert abs(body["lng"] - (-3.71)) < 0.001


def test_get_driver_position_no_position_returns_404(client, db_session):
    """Ruta sin posición publicada → 404."""
    tenant = _demo_tenant(db_session)
    email = f"gps-d6-{uuid.uuid4().hex[:6]}@test.cortecero.app"
    user, driver = _create_driver_user(db_session, tenant, email=email)
    route = _build_route(db_session, tenant.id, driver, route_status=RouteStatus.in_progress)

    token = _logistics_token(client)
    res = client.get(f"/routes/{route.id}/driver-position", headers=auth_headers(token))
    assert res.status_code == 404, res.text


def test_get_driver_position_nonexistent_route_returns_404(client, db_session):
    """Ruta que no existe → 404."""
    token = _logistics_token(client)
    res = client.get(f"/routes/{uuid.uuid4()}/driver-position", headers=auth_headers(token))
    assert res.status_code == 404, res.text


# ── GET /routes/active-positions ─────────────────────────────────────────────


def test_get_active_positions_happy_path(client, db_session):
    """Logistics obtiene lista de posiciones activas."""
    tenant = _demo_tenant(db_session)
    email = f"gps-d7-{uuid.uuid4().hex[:6]}@test.cortecero.app"
    user, driver = _create_driver_user(db_session, tenant, email=email)
    route = _build_route(db_session, tenant.id, driver, route_status=RouteStatus.in_progress)

    driver_token = login_as(client, tenant_slug="demo-cortecero", email=email, password="driver123")
    client.post(
        "/driver/location",
        json={"route_id": str(route.id), "lat": 40.40, "lng": -3.70},
        headers=auth_headers(driver_token),
    )

    logistics_token = _logistics_token(client)
    res = client.get("/driver/active-positions", headers=auth_headers(logistics_token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert isinstance(body, list)
    route_ids = [item["route_id"] for item in body]
    assert str(route.id) in route_ids


def test_get_active_positions_unauthenticated_returns_401(client, db_session):
    """Sin token → 401."""
    res = client.get("/driver/active-positions")
    assert res.status_code == 401, res.text


