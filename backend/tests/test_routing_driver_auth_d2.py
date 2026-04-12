"""
D.2 — Auth real de conductor en ejecución de ruta.

Cubre:
  - Driver asignado puede ejecutar arrive/complete/fail e incident.
  - Driver no asignado recibe 403 DRIVER_SCOPE_FORBIDDEN.
  - Driver sin ficha activa recibe 403 DRIVER_NOT_LINKED.
  - Logistics/Admin mantienen compatibilidad de acceso.
  - Tenant isolation en endpoints de ejecución.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.models import (
    Customer,
    Driver,
    Incident,
    IncidentSeverity,
    IncidentType,
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


def _get_tenant(db_session) -> Tenant:
    tenant = db_session.scalar(select(Tenant).where(Tenant.slug == "demo-cortecero"))
    assert tenant is not None
    return tenant


def _driver_token(client, *, tenant_slug: str, email: str, password: str = "driver123") -> str:
    return login_as(client, tenant_slug=tenant_slug, email=email, password=password)


def _create_driver_with_user(db_session, tenant: Tenant, *, email: str) -> Driver:
    """Crea un par (User con role=driver, Driver) con vínculo explícito via user_id.

    Orden correcto post-018_driver_user_id:
      1. User  — identidad de autenticación; genera su propio UUID.
      2. Driver — ficha operativa; user_id apunta al User creado en (1).

    La FK fk_drivers_user_id es DEFERRABLE INITIALLY DEFERRED, por lo que
    User y Driver pueden insertarse en la misma transacción en cualquier orden.
    Usamos el orden semánticamente correcto (User primero).
    """
    now = datetime.now(UTC)
    vehicle = db_session.scalar(
        select(Vehicle).where(Vehicle.tenant_id == tenant.id, Vehicle.active.is_(True))
    )
    assert vehicle is not None

    driver_name = f"Driver {email.split('@')[0]}"

    # 1. Crear la cuenta de acceso (User) — UUID propio, independiente del Driver
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=email,
        full_name=driver_name,
        password_hash=hash_password("driver123"),
        role=UserRole.driver,
        is_active=True,
        created_at=now,
    )
    db_session.add(user)
    db_session.flush()  # user.id disponible antes del driver

    # 2. Crear la ficha operativa (Driver) con vínculo explícito user_id → user.id
    driver = Driver(
        id=uuid.uuid4(),        # UUID propio (no comparte ID con User)
        tenant_id=tenant.id,
        user_id=user.id,        # vínculo explícito (018_driver_user_id)
        vehicle_id=vehicle.id,
        name=driver_name,
        phone=f"+34000{str(uuid.uuid4().int)[:8]}",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(driver)
    db_session.commit()
    db_session.refresh(driver)
    return driver


def _build_route_stop_for_driver(
    db_session,
    tenant: Tenant,
    *,
    driver_id: uuid.UUID,
    stop_status: RouteStopStatus,
) -> tuple[Route, RouteStop]:
    now = datetime.now(UTC)
    svc_date = date.today() + timedelta(days=(uuid.uuid4().int % 400) + 1)

    zone = db_session.scalar(select(Zone).where(Zone.tenant_id == tenant.id))
    assert zone is not None
    customer = db_session.scalar(select(Customer).where(Customer.tenant_id == tenant.id))
    assert customer is not None
    vehicle = db_session.scalar(
        select(Vehicle).where(Vehicle.tenant_id == tenant.id, Vehicle.active.is_(True))
    )
    assert vehicle is not None

    plan = Plan(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
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
        tenant_id=tenant.id,
        plan_id=plan.id,
        vehicle_id=vehicle.id,
        driver_id=driver_id,
        service_date=svc_date,
        status=RouteStatus.dispatched,
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
        tenant_id=tenant.id,
        customer_id=customer.id,
        zone_id=zone.id,
        external_ref=f"D2-{uuid.uuid4()}",
        requested_date=svc_date,
        service_date=svc_date,
        created_at=now,
        status=OrderStatus.dispatched,
        is_late=False,
        lateness_reason=None,
        effective_cutoff_at=now,
        source_channel=SourceChannel.office,
        intake_type=OrderIntakeType.new_order,
        total_weight_kg=1,
        ingested_at=now,
        updated_at=now,
    )
    db_session.add(order)
    db_session.flush()

    stop = RouteStop(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        route_id=route.id,
        order_id=order.id,
        sequence_number=1,
        estimated_arrival_at=None,
        estimated_service_minutes=10,
        status=stop_status,
        arrived_at=now if stop_status == RouteStopStatus.arrived else None,
        completed_at=None,
        failed_at=None,
        failure_reason=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(stop)
    db_session.commit()
    return route, stop


def test_driver_assigned_can_arrive(client, db_session):
    tenant = _get_tenant(db_session)
    driver = _create_driver_with_user(db_session, tenant, email="driver.arrive@demo.cortecero.app")
    _, stop = _build_route_stop_for_driver(
        db_session, tenant, driver_id=driver.id, stop_status=RouteStopStatus.pending
    )

    token = _driver_token(client, tenant_slug=tenant.slug, email="driver.arrive@demo.cortecero.app")
    res = client.post(f"/stops/{stop.id}/arrive", json={}, headers=auth_headers(token))

    assert res.status_code == 200, res.text
    assert res.json()["status"] == "arrived"


def test_driver_assigned_can_complete(client, db_session):
    tenant = _get_tenant(db_session)
    driver = _create_driver_with_user(db_session, tenant, email="driver.complete@demo.cortecero.app")
    _, stop = _build_route_stop_for_driver(
        db_session, tenant, driver_id=driver.id, stop_status=RouteStopStatus.arrived
    )

    token = _driver_token(client, tenant_slug=tenant.slug, email="driver.complete@demo.cortecero.app")
    res = client.post(f"/stops/{stop.id}/complete", json={}, headers=auth_headers(token))

    assert res.status_code == 200, res.text
    assert res.json()["status"] == "completed"


def test_driver_assigned_can_fail(client, db_session):
    tenant = _get_tenant(db_session)
    driver = _create_driver_with_user(db_session, tenant, email="driver.fail@demo.cortecero.app")
    _, stop = _build_route_stop_for_driver(
        db_session, tenant, driver_id=driver.id, stop_status=RouteStopStatus.arrived
    )

    token = _driver_token(client, tenant_slug=tenant.slug, email="driver.fail@demo.cortecero.app")
    res = client.post(
        f"/stops/{stop.id}/fail",
        json={"failure_reason": "customer closed"},
        headers=auth_headers(token),
    )

    assert res.status_code == 200, res.text
    assert res.json()["status"] == "failed"


def test_driver_assigned_can_report_incident(client, db_session):
    tenant = _get_tenant(db_session)
    driver = _create_driver_with_user(db_session, tenant, email="driver.incident@demo.cortecero.app")
    route, _ = _build_route_stop_for_driver(
        db_session, tenant, driver_id=driver.id, stop_status=RouteStopStatus.pending
    )

    token = _driver_token(client, tenant_slug=tenant.slug, email="driver.incident@demo.cortecero.app")
    payload = {
        "route_id": str(route.id),
        "type": IncidentType.other.value,
        "severity": IncidentSeverity.low.value,
        "description": "small delay",
    }
    res = client.post("/incidents", json=payload, headers=auth_headers(token))

    assert res.status_code == 201, res.text
    assert res.json()["route_id"] == str(route.id)

    incidents = list(
        db_session.scalars(
            select(Incident).where(Incident.tenant_id == tenant.id, Incident.route_id == route.id)
        )
    )
    assert len(incidents) == 1


def test_driver_forbidden_on_other_driver_route(client, db_session):
    tenant = _get_tenant(db_session)
    assigned_driver = _create_driver_with_user(db_session, tenant, email="driver.a@demo.cortecero.app")
    other_driver = _create_driver_with_user(db_session, tenant, email="driver.b@demo.cortecero.app")
    route, stop = _build_route_stop_for_driver(
        db_session, tenant, driver_id=assigned_driver.id, stop_status=RouteStopStatus.pending
    )

    token = _driver_token(client, tenant_slug=tenant.slug, email="driver.b@demo.cortecero.app")
    arrive_res = client.post(f"/stops/{stop.id}/arrive", json={}, headers=auth_headers(token))
    assert arrive_res.status_code == 403, arrive_res.text
    assert arrive_res.json()["detail"]["code"] == "DRIVER_SCOPE_FORBIDDEN"

    payload = {
        "route_id": str(route.id),
        "type": IncidentType.other.value,
        "severity": IncidentSeverity.low.value,
        "description": "unauthorized test",
    }
    incident_res = client.post("/incidents", json=payload, headers=auth_headers(token))
    assert incident_res.status_code == 403, incident_res.text
    assert incident_res.json()["detail"]["code"] == "DRIVER_SCOPE_FORBIDDEN"

    # silenciar warning de variable sin uso lógica del test
    assert other_driver.id != assigned_driver.id


def test_driver_not_linked_returns_403(client, db_session):
    tenant = _get_tenant(db_session)
    assigned_driver = _create_driver_with_user(db_session, tenant, email="driver.linked@demo.cortecero.app")
    _, stop = _build_route_stop_for_driver(
        db_session, tenant, driver_id=assigned_driver.id, stop_status=RouteStopStatus.pending
    )

    now = datetime.now(UTC)
    unlinked = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="driver.unlinked@demo.cortecero.app",
        full_name="Driver Unlinked",
        password_hash=hash_password("driver123"),
        role=UserRole.driver,
        is_active=True,
        created_at=now,
    )
    db_session.add(unlinked)
    db_session.commit()

    token = _driver_token(client, tenant_slug=tenant.slug, email="driver.unlinked@demo.cortecero.app")
    res = client.post(f"/stops/{stop.id}/arrive", json={}, headers=auth_headers(token))

    assert res.status_code == 403, res.text
    assert res.json()["detail"]["code"] == "DRIVER_NOT_LINKED"


def test_logistics_and_admin_keep_access(client, db_session):
    tenant = _get_tenant(db_session)
    assigned_driver = _create_driver_with_user(db_session, tenant, email="driver.scope@demo.cortecero.app")

    _, stop_for_logistics = _build_route_stop_for_driver(
        db_session, tenant, driver_id=assigned_driver.id, stop_status=RouteStopStatus.pending
    )
    logistics_token = login_as(
        client,
        tenant_slug=tenant.slug,
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )
    logistics_res = client.post(
        f"/stops/{stop_for_logistics.id}/arrive",
        json={},
        headers=auth_headers(logistics_token),
    )
    assert logistics_res.status_code == 200, logistics_res.text

    _, stop_for_admin = _build_route_stop_for_driver(
        db_session, tenant, driver_id=assigned_driver.id, stop_status=RouteStopStatus.pending
    )
    admin_token = login_as(
        client,
        tenant_slug=tenant.slug,
        email="admin@demo.cortecero.app",
        password="admin123",
    )
    admin_res = client.post(
        f"/stops/{stop_for_admin.id}/arrive",
        json={},
        headers=auth_headers(admin_token),
    )
    assert admin_res.status_code == 200, admin_res.text


def test_driver_tenant_isolation_returns_404(client, db_session):
    tenant_a = _get_tenant(db_session)
    driver_a = _create_driver_with_user(db_session, tenant_a, email="driver.ta@demo.cortecero.app")
    _, stop_a = _build_route_stop_for_driver(
        db_session, tenant_a, driver_id=driver_a.id, stop_status=RouteStopStatus.pending
    )

    now = datetime.now(UTC)
    tenant_b = Tenant(
        id=uuid.uuid4(),
        name="Tenant D2",
        slug="tenant-d2",
        default_cutoff_time=datetime.strptime("10:00", "%H:%M").time(),
        default_timezone="Europe/Madrid",
        auto_lock_enabled=False,
        created_at=now,
    )
    db_session.add(tenant_b)
    driver_b = User(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        email="driver.tb@demo.cortecero.app",
        full_name="Driver Tenant B",
        password_hash=hash_password("driver123"),
        role=UserRole.driver,
        is_active=True,
        created_at=now,
    )
    db_session.add(driver_b)
    db_session.commit()

    token_b = _driver_token(client, tenant_slug=tenant_b.slug, email="driver.tb@demo.cortecero.app")
    res = client.post(f"/stops/{stop_a.id}/arrive", json={}, headers=auth_headers(token_b))

    assert res.status_code == 404, res.text
    assert res.json()["detail"]["code"] == "ENTITY_NOT_FOUND"
