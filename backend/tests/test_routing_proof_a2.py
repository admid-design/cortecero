"""
Bloque A2 — Proof of Delivery (POD-001)

Cubre:
  - POST /stops/{id}/proof  happy path (arrived, completed)
  - POST /stops/{id}/proof  signature_data obligatoria para type=signature
  - POST /stops/{id}/proof  stop en estado incorrecto → 409
  - POST /stops/{id}/proof  stop de otro tenant → 404
  - GET  /stops/{id}/proof  happy path
  - GET  /stops/{id}/proof  sin proof → 404
  - GET  /stops/{id}/proof  stop de otro tenant → 404
"""

import uuid
from datetime import UTC, date, datetime, time

from sqlalchemy import select

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


# ── Fixtures helpers ──────────────────────────────────────────────────────────


def _demo_tenant(db_session) -> Tenant:
    tenant = db_session.scalar(select(Tenant).where(Tenant.slug == "demo-cortecero"))
    assert tenant is not None
    return tenant


def _driver_token(client, *, tenant_slug: str, email: str, password: str = "driver123") -> str:
    return login_as(client, tenant_slug=tenant_slug, email=email, password=password)


def _logistics_token(client, tenant_slug: str = "demo-cortecero") -> str:
    return login_as(client, tenant_slug=tenant_slug, email="logistics@demo.cortecero.app", password="logistics123")


def _create_driver_user(db_session, tenant: Tenant, *, email: str, password: str = "driver123") -> Driver:
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
    return driver


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


def _build_route_with_stop(
    db_session,
    tenant_id: uuid.UUID,
    *,
    route_status: RouteStatus = RouteStatus.in_progress,
    stop_status: RouteStopStatus = RouteStopStatus.arrived,
    driver: Driver | None = None,
) -> tuple[Route, RouteStop]:
    now = datetime.now(UTC)
    svc_date = date.today()

    vehicle = db_session.scalar(
        select(Vehicle).where(Vehicle.tenant_id == tenant_id, Vehicle.active.is_(True))
    )
    assert vehicle is not None

    if driver is None:
        driver = db_session.scalar(
            select(Driver).where(Driver.tenant_id == tenant_id, Driver.is_active.is_(True))
        )
    assert driver is not None

    zone = db_session.scalar(select(Zone).where(Zone.tenant_id == tenant_id))
    assert zone is not None

    customer = db_session.scalar(select(Customer).where(Customer.tenant_id == tenant_id))
    assert customer is not None

    # check-first: el seed crea un plan para today en la primera zona;
    # crear incondicionalmente viola la unique constraint (tenant, date, zone).
    plan = db_session.scalar(
        select(Plan).where(
            Plan.tenant_id == tenant_id,
            Plan.service_date == svc_date,
            Plan.zone_id == zone.id,
        )
    )
    if plan is None:
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
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        service_date=svc_date,
        status=route_status,
        version=1,
        optimization_request_id=None,
        optimization_response_json=None,
        created_at=now,
        updated_at=now,
        dispatched_at=now,
        completed_at=None,
    )
    db_session.add(route)
    db_session.flush()

    order = Order(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        customer_id=customer.id,
        zone_id=zone.id,
        external_ref=f"A2-{uuid.uuid4()}",
        requested_date=svc_date,
        service_date=svc_date,
        created_at=now,
        status=OrderStatus.dispatched,
        is_late=False,
        lateness_reason=None,
        effective_cutoff_at=now,
        source_channel=SourceChannel.office,
        intake_type=OrderIntakeType.new_order,
        total_weight_kg=5.0,
        ingested_at=now,
        updated_at=now,
    )
    db_session.add(order)
    db_session.flush()

    arrived_at = now if stop_status in (RouteStopStatus.arrived, RouteStopStatus.completed) else None
    stop = RouteStop(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        route_id=route.id,
        order_id=order.id,
        sequence_number=1,
        estimated_arrival_at=None,
        estimated_service_minutes=10,
        status=stop_status,
        arrived_at=arrived_at,
        completed_at=now if stop_status == RouteStopStatus.completed else None,
        failed_at=None,
        failure_reason=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(stop)
    db_session.commit()
    db_session.refresh(route)
    db_session.refresh(stop)
    return route, stop


# ── POST /stops/{id}/proof ────────────────────────────────────────────────────


def test_proof_create_happy_path_arrived(client, db_session):
    """Conductor crea proof en parada arrived → 201 con proof_type=signature."""
    tenant = _demo_tenant(db_session)
    token = _logistics_token(client)
    _, stop = _build_route_with_stop(db_session, tenant.id, stop_status=RouteStopStatus.arrived)

    payload = {
        "proof_type": "signature",
        "signature_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        "signed_by": "Juan García",
    }
    res = client.post(f"/stops/{stop.id}/proof", json=payload, headers=auth_headers(token))
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["proof_type"] == "signature"
    assert body["signed_by"] == "Juan García"
    assert body["route_stop_id"] == str(stop.id)
    assert "id" in body
    assert "captured_at" in body


def test_proof_create_happy_path_completed(client, db_session):
    """Proof también permitido en parada completed."""
    tenant = _demo_tenant(db_session)
    token = _logistics_token(client)
    _, stop = _build_route_with_stop(db_session, tenant.id, stop_status=RouteStopStatus.completed)

    payload = {
        "proof_type": "signature",
        "signature_data": "data:image/png;base64,abc123==",
        "signed_by": "Pedro López",
    }
    res = client.post(f"/stops/{stop.id}/proof", json=payload, headers=auth_headers(token))
    assert res.status_code == 201, res.text


def test_proof_create_missing_signature_data_returns_422(client, db_session):
    """proof_type=signature sin signature_data → 422."""
    tenant = _demo_tenant(db_session)
    token = _logistics_token(client)
    _, stop = _build_route_with_stop(db_session, tenant.id, stop_status=RouteStopStatus.arrived)

    payload = {"proof_type": "signature"}
    res = client.post(f"/stops/{stop.id}/proof", json=payload, headers=auth_headers(token))
    assert res.status_code == 422, res.text
    body = res.json()
    assert body["detail"]["code"] == "SIGNATURE_DATA_REQUIRED"


def test_proof_create_wrong_stop_status_returns_409(client, db_session):
    """Parada en estado pending → 409 STOP_NOT_ARRIVED."""
    tenant = _demo_tenant(db_session)
    token = _logistics_token(client)
    _, stop = _build_route_with_stop(db_session, tenant.id, stop_status=RouteStopStatus.pending)

    payload = {
        "proof_type": "signature",
        "signature_data": "data:image/png;base64,abc123==",
    }
    res = client.post(f"/stops/{stop.id}/proof", json=payload, headers=auth_headers(token))
    assert res.status_code == 409, res.text
    body = res.json()
    assert body["detail"]["code"] == "STOP_NOT_ARRIVED"


def test_proof_create_nonexistent_stop_returns_404(client, db_session):
    """Stop que no existe → 404."""
    token = _logistics_token(client)
    fake_id = uuid.uuid4()
    payload = {
        "proof_type": "signature",
        "signature_data": "data:image/png;base64,abc123==",
    }
    res = client.post(f"/stops/{fake_id}/proof", json=payload, headers=auth_headers(token))
    assert res.status_code == 404, res.text


def test_proof_create_other_tenant_stop_returns_404(client, db_session):
    """Stop de otro tenant → 404 (tenant isolation)."""
    other_tenant = _create_tenant(db_session, slug=f"other-a2-{uuid.uuid4().hex[:6]}")
    token = _logistics_token(client)

    # Crear stop en el otro tenant — necesitamos setup manual mínimo
    now = datetime.now(UTC)
    zone = Zone(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        name="Zona A2 other",
        default_cutoff_time=time(17, 0),
        timezone="Europe/Madrid",
        active=True,
        created_at=now,
    )
    db_session.add(zone)
    db_session.flush()

    customer = Customer(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        zone_id=zone.id,
        name="Cliente A2 other",
        delivery_address="Calle A2, 1",
        active=True,
        created_at=now,
    )
    db_session.add(customer)
    db_session.flush()

    vehicle = Vehicle(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        name="Van A2 other",
        code="VA2O",
        capacity_kg=1000.0,
        active=True,
        created_at=now,
    )
    db_session.add(vehicle)
    db_session.flush()

    plan = Plan(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        service_date=date.today(),
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
        tenant_id=other_tenant.id,
        plan_id=plan.id,
        vehicle_id=vehicle.id,
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
    db_session.add(route)
    db_session.flush()

    order = Order(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        customer_id=customer.id,
        zone_id=zone.id,
        external_ref=f"A2-iso-{uuid.uuid4()}",
        requested_date=date.today(),
        service_date=date.today(),
        created_at=now,
        status=OrderStatus.dispatched,
        is_late=False,
        lateness_reason=None,
        effective_cutoff_at=now,
        source_channel=SourceChannel.office,
        intake_type=OrderIntakeType.new_order,
        total_weight_kg=5.0,
        ingested_at=now,
        updated_at=now,
    )
    db_session.add(order)
    db_session.flush()

    other_stop = RouteStop(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        route_id=route.id,
        order_id=order.id,
        sequence_number=1,
        estimated_arrival_at=None,
        estimated_service_minutes=10,
        status=RouteStopStatus.arrived,
        arrived_at=now,
        completed_at=None,
        failed_at=None,
        failure_reason=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(other_stop)
    db_session.commit()

    payload = {
        "proof_type": "signature",
        "signature_data": "data:image/png;base64,abc123==",
    }
    res = client.post(f"/stops/{other_stop.id}/proof", json=payload, headers=auth_headers(token))
    assert res.status_code == 404, res.text


# ── GET /stops/{id}/proof ─────────────────────────────────────────────────────


def test_proof_get_happy_path(client, db_session):
    """Crear proof y luego recuperarlo."""
    tenant = _demo_tenant(db_session)
    token = _logistics_token(client)
    _, stop = _build_route_with_stop(db_session, tenant.id, stop_status=RouteStopStatus.arrived)

    sig = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    client.post(
        f"/stops/{stop.id}/proof",
        json={"proof_type": "signature", "signature_data": sig, "signed_by": "Ana Torres"},
        headers=auth_headers(token),
    )

    res = client.get(f"/stops/{stop.id}/proof", headers=auth_headers(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["proof_type"] == "signature"
    assert body["signed_by"] == "Ana Torres"
    assert body["route_stop_id"] == str(stop.id)


def test_proof_get_not_found_returns_404(client, db_session):
    """GET proof de parada sin proof → 404."""
    tenant = _demo_tenant(db_session)
    token = _logistics_token(client)
    _, stop = _build_route_with_stop(db_session, tenant.id, stop_status=RouteStopStatus.arrived)

    res = client.get(f"/stops/{stop.id}/proof", headers=auth_headers(token))
    assert res.status_code == 404, res.text


def test_proof_get_nonexistent_stop_returns_404(client, db_session):
    """GET proof de stop que no existe → 404."""
    token = _logistics_token(client)
    res = client.get(f"/stops/{uuid.uuid4()}/proof", headers=auth_headers(token))
    assert res.status_code == 404, res.text
