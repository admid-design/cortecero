"""
Bloque C — Vistas/acciones de conductor

Cubre:
  - GET  /driver/routes (scope driver y compatibilidad logistics)
  - GET  /routes/{id}/next-stop (lectura sin side effects + scope driver)
  - POST /stops/{id}/skip (happy path, idempotencia, conflictos, compatibilidad logistics/admin)
  - POST /incidents/{id}/review
  - POST /incidents/{id}/resolve
  - tenant isolation en endpoints de Bloque C
"""

import uuid
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select

from app.models import (
    Customer,
    Driver,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    IncidentType,
    Order,
    OrderIntakeType,
    OrderStatus,
    Plan,
    PlanStatus,
    Route,
    RouteEvent,
    RouteEventType,
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


def _demo_tenant(db_session) -> Tenant:
    tenant = db_session.scalar(select(Tenant).where(Tenant.slug == "demo-cortecero"))
    assert tenant is not None
    return tenant


def _token(
    client,
    *,
    tenant_slug: str,
    email: str,
    password: str,
) -> str:
    return login_as(client, tenant_slug=tenant_slug, email=email, password=password)


def _create_driver_user(
    db_session,
    tenant: Tenant,
    *,
    email: str,
    password: str = "driver123",
) -> Driver:
    """Crea un par (User con role=driver, Driver) con vínculo explícito via user_id.

    Actualizado en PILOT-HARDEN-001: User y Driver tienen UUIDs independientes;
    Driver.user_id → User.id (migration 018_driver_user_id).
    """
    now = datetime.now(UTC)
    vehicle = db_session.scalar(
        select(Vehicle).where(Vehicle.tenant_id == tenant.id, Vehicle.active.is_(True))
    )
    assert vehicle is not None

    name = f"Driver {email.split('@')[0]}"

    # 1. Crear la cuenta de acceso (User) — UUID propio
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=email,
        full_name=name,
        password_hash=hash_password(password),
        role=UserRole.driver,
        is_active=True,
        created_at=now,
    )
    db_session.add(user)
    db_session.flush()  # user.id disponible antes del driver

    # 2. Crear la ficha operativa (Driver) con vínculo explícito user_id → user.id
    driver = Driver(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=user.id,        # vínculo explícito (018_driver_user_id)
        vehicle_id=vehicle.id,
        name=name,
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
        auto_lock_enabled=False,
        created_at=datetime.now(UTC),
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _ensure_base_entities(db_session, tenant: Tenant) -> tuple[Zone, Customer, Vehicle]:
    now = datetime.now(UTC)

    zone = db_session.scalar(select(Zone).where(Zone.tenant_id == tenant.id))
    if zone is None:
        zone = Zone(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            name=f"Zone {tenant.slug}",
            default_cutoff_time=time(18, 0),
            timezone="Europe/Madrid",
            active=True,
            created_at=now,
        )
        db_session.add(zone)
        db_session.flush()

    customer = db_session.scalar(select(Customer).where(Customer.tenant_id == tenant.id))
    if customer is None:
        customer = Customer(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            zone_id=zone.id,
            name=f"Customer {tenant.slug}",
            priority=0,
            cutoff_override_time=None,
            active=True,
            lat=41.3874,
            lng=2.1686,
            delivery_address="Demo Address",
            created_at=now,
        )
        db_session.add(customer)
        db_session.flush()

    vehicle = db_session.scalar(
        select(Vehicle).where(Vehicle.tenant_id == tenant.id, Vehicle.active.is_(True))
    )
    if vehicle is None:
        vehicle = Vehicle(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            code=f"{tenant.slug[:4].upper()}-{str(uuid.uuid4())[:8]}",
            name=f"Vehicle {tenant.slug}",
            capacity_kg=1200,
            active=True,
            created_at=now,
        )
        db_session.add(vehicle)
        db_session.flush()

    db_session.commit()
    return zone, customer, vehicle


def _create_route_with_stops(
    db_session,
    tenant: Tenant,
    *,
    driver_id: uuid.UUID | None,
    route_status: RouteStatus = RouteStatus.dispatched,
    stop_statuses: list[RouteStopStatus] | None = None,
    service_date: date | None = None,
) -> tuple[Route, list[RouteStop]]:
    now = datetime.now(UTC)
    svc_date = service_date or (date.today() + timedelta(days=(uuid.uuid4().int % 300) + 1))
    stop_states = stop_statuses or [RouteStopStatus.pending]

    zone, customer, vehicle = _ensure_base_entities(db_session, tenant)

    plan = db_session.scalar(
        select(Plan).where(
            Plan.tenant_id == tenant.id,
            Plan.service_date == svc_date,
            Plan.zone_id == zone.id,
        )
    )
    if plan is None:
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
        status=route_status,
        version=1,
        optimization_request_id=None,
        optimization_response_json=None,
        created_at=now,
        updated_at=now,
        dispatched_at=now if route_status in (RouteStatus.dispatched, RouteStatus.in_progress, RouteStatus.completed) else None,
        completed_at=now if route_status == RouteStatus.completed else None,
    )
    db_session.add(route)
    db_session.flush()

    stops: list[RouteStop] = []
    for i, stop_status in enumerate(stop_states, start=1):
        if stop_status == RouteStopStatus.completed:
            order_status = OrderStatus.delivered
        elif stop_status == RouteStopStatus.failed:
            order_status = OrderStatus.failed_delivery
        else:
            order_status = OrderStatus.dispatched

        order = Order(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            customer_id=customer.id,
            zone_id=zone.id,
            external_ref=f"C-{uuid.uuid4()}",
            requested_date=svc_date,
            service_date=svc_date,
            created_at=now,
            status=order_status,
            is_late=False,
            lateness_reason=None,
            effective_cutoff_at=now,
            source_channel=SourceChannel.office,
            intake_type=OrderIntakeType.new_order,
            total_weight_kg=5,
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
            sequence_number=i,
            estimated_arrival_at=None,
            estimated_service_minutes=10,
            status=stop_status,
            arrived_at=now if stop_status in (RouteStopStatus.arrived, RouteStopStatus.completed, RouteStopStatus.failed) else None,
            completed_at=now if stop_status == RouteStopStatus.completed else None,
            failed_at=now if stop_status == RouteStopStatus.failed else None,
            failure_reason="setup fail" if stop_status == RouteStopStatus.failed else None,
            created_at=now,
            updated_at=now,
        )
        db_session.add(stop)
        db_session.flush()
        stops.append(stop)

    db_session.commit()
    db_session.refresh(route)
    for stop in stops:
        db_session.refresh(stop)
    return route, stops


def _create_incident(
    db_session,
    tenant: Tenant,
    *,
    route: Route,
    route_stop_id: uuid.UUID | None,
    status: IncidentStatus,
) -> Incident:
    now = datetime.now(UTC)
    assert route.driver_id is not None, "Route must have driver_id to create incident"
    incident = Incident(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        route_id=route.id,
        route_stop_id=route_stop_id,
        driver_id=route.driver_id,
        type=IncidentType.other,
        severity=IncidentSeverity.medium,
        description="incident setup",
        status=status,
        reported_at=now,
        reviewed_at=now if status in (IncidentStatus.reviewed, IncidentStatus.resolved) else None,
        resolved_at=now if status == IncidentStatus.resolved else None,
        resolution_note="already resolved" if status == IncidentStatus.resolved else None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)
    return incident


def test_driver_routes_scope_only_assigned_routes(client, db_session):
    tenant = _demo_tenant(db_session)
    driver_a = _create_driver_user(db_session, tenant, email="driver.c.scope.a@demo.cortecero.app")
    driver_b = _create_driver_user(db_session, tenant, email="driver.c.scope.b@demo.cortecero.app")

    route_a, _ = _create_route_with_stops(db_session, tenant, driver_id=driver_a.id)
    _create_route_with_stops(db_session, tenant, driver_id=driver_b.id)

    token = _token(
        client,
        tenant_slug=tenant.slug,
        email="driver.c.scope.a@demo.cortecero.app",
        password="driver123",
    )
    res = client.get("/driver/routes", headers=auth_headers(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] >= 1
    assert {item["driver_id"] for item in body["items"]} == {str(driver_a.id)}
    assert str(route_a.id) in {item["id"] for item in body["items"]}


def test_driver_routes_logistics_can_filter_by_status(client, db_session):
    tenant = _demo_tenant(db_session)
    svc_date = date.today() + timedelta(days=(uuid.uuid4().int % 200) + 10)

    _create_route_with_stops(
        db_session,
        tenant,
        driver_id=None,
        route_status=RouteStatus.dispatched,
        service_date=svc_date,
    )
    _create_route_with_stops(
        db_session,
        tenant,
        driver_id=None,
        route_status=RouteStatus.completed,
        service_date=svc_date,
        stop_statuses=[RouteStopStatus.completed],
    )

    token = _token(
        client,
        tenant_slug=tenant.slug,
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )
    res = client.get(
        "/driver/routes",
        params={"service_date": svc_date.isoformat(), "status": "dispatched"},
        headers=auth_headers(token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "dispatched"


def test_get_next_stop_returns_first_non_terminal(client, db_session):
    tenant = _demo_tenant(db_session)
    route, stops = _create_route_with_stops(
        db_session,
        tenant,
        driver_id=None,
        route_status=RouteStatus.in_progress,
        stop_statuses=[
            RouteStopStatus.completed,
            RouteStopStatus.pending,
            RouteStopStatus.failed,
            RouteStopStatus.pending,
        ],
    )
    token = _token(
        client,
        tenant_slug=tenant.slug,
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )

    res = client.get(f"/routes/{route.id}/next-stop", headers=auth_headers(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["route_id"] == str(route.id)
    assert body["remaining_stops"] == 2
    assert body["next_stop"]["id"] == str(stops[1].id)
    assert body["next_stop"]["sequence_number"] == 2


def test_get_next_stop_driver_forbidden_for_other_driver(client, db_session):
    tenant = _demo_tenant(db_session)
    driver_a = _create_driver_user(db_session, tenant, email="driver.c.next.a@demo.cortecero.app")
    driver_b = _create_driver_user(db_session, tenant, email="driver.c.next.b@demo.cortecero.app")
    route, _ = _create_route_with_stops(db_session, tenant, driver_id=driver_a.id)

    token_b = _token(
        client,
        tenant_slug=tenant.slug,
        email="driver.c.next.b@demo.cortecero.app",
        password="driver123",
    )
    res = client.get(f"/routes/{route.id}/next-stop", headers=auth_headers(token_b))
    assert res.status_code == 403, res.text
    assert res.json()["detail"]["code"] == "DRIVER_SCOPE_FORBIDDEN"

    token_a = _token(
        client,
        tenant_slug=tenant.slug,
        email="driver.c.next.a@demo.cortecero.app",
        password="driver123",
    )
    res_ok = client.get(f"/routes/{route.id}/next-stop", headers=auth_headers(token_a))
    assert res_ok.status_code == 200, res_ok.text


def test_next_stop_tenant_isolation_returns_404(client, db_session):
    demo = _demo_tenant(db_session)
    isolated = _create_tenant(db_session, slug=f"tenant-c-{str(uuid.uuid4())[:8]}")
    route, _ = _create_route_with_stops(db_session, isolated, driver_id=None)

    token = _token(
        client,
        tenant_slug=demo.slug,
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )
    res = client.get(f"/routes/{route.id}/next-stop", headers=auth_headers(token))
    assert res.status_code == 404, res.text
    assert res.json()["detail"]["code"] == "ENTITY_NOT_FOUND"


def test_skip_happy_path_driver_route_started_and_event(client, db_session):
    tenant = _demo_tenant(db_session)
    driver = _create_driver_user(db_session, tenant, email="driver.c.skip.happy@demo.cortecero.app")
    route, stops = _create_route_with_stops(
        db_session,
        tenant,
        driver_id=driver.id,
        route_status=RouteStatus.dispatched,
        stop_statuses=[RouteStopStatus.pending],
    )
    stop = stops[0]

    token = _token(
        client,
        tenant_slug=tenant.slug,
        email="driver.c.skip.happy@demo.cortecero.app",
        password="driver123",
    )
    res = client.post(
        f"/stops/{stop.id}/skip",
        json={"reason": "customer closed"},
        headers=auth_headers(token),
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "skipped"

    db_session.expire_all()
    updated_route = db_session.get(Route, route.id)
    assert updated_route is not None
    assert updated_route.status == RouteStatus.completed

    started_events = list(
        db_session.scalars(
            select(RouteEvent).where(
                RouteEvent.route_id == route.id,
                RouteEvent.event_type == RouteEventType.route_started,
            )
        )
    )
    skipped_events = list(
        db_session.scalars(
            select(RouteEvent).where(
                RouteEvent.route_stop_id == stop.id,
                RouteEvent.event_type == RouteEventType.stop_skipped,
            )
        )
    )
    completed_events = list(
        db_session.scalars(
            select(RouteEvent).where(
                RouteEvent.route_id == route.id,
                RouteEvent.event_type == RouteEventType.route_completed,
            )
        )
    )
    assert len(started_events) == 1
    assert len(skipped_events) == 1
    assert len(completed_events) == 1


def test_skip_idempotency_same_key_no_duplicate_event(client, db_session):
    tenant = _demo_tenant(db_session)
    route, stops = _create_route_with_stops(
        db_session,
        tenant,
        driver_id=None,
        route_status=RouteStatus.in_progress,
        stop_statuses=[RouteStopStatus.pending],
    )
    stop = stops[0]
    token = _token(
        client,
        tenant_slug=tenant.slug,
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )
    idem = str(uuid.uuid4())

    res1 = client.post(
        f"/stops/{stop.id}/skip",
        json={"idempotency_key": idem, "reason": "blocked"},
        headers=auth_headers(token),
    )
    res2 = client.post(
        f"/stops/{stop.id}/skip",
        json={"idempotency_key": idem, "reason": "blocked"},
        headers=auth_headers(token),
    )
    assert res1.status_code == 200, res1.text
    assert res2.status_code == 200, res2.text
    assert res2.json()["status"] == "skipped"

    events = list(
        db_session.scalars(
            select(RouteEvent).where(
                RouteEvent.route_id == route.id,
                RouteEvent.route_stop_id == stop.id,
                RouteEvent.event_type == RouteEventType.stop_skipped,
            )
        )
    )
    assert len(events) == 1


def test_skip_invalid_state_transition_returns_409(client, db_session):
    tenant = _demo_tenant(db_session)
    _, stops = _create_route_with_stops(
        db_session,
        tenant,
        driver_id=None,
        route_status=RouteStatus.in_progress,
        stop_statuses=[RouteStopStatus.completed],
    )
    stop = stops[0]
    token = _token(
        client,
        tenant_slug=tenant.slug,
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )

    res = client.post(
        f"/stops/{stop.id}/skip",
        json={"reason": "already done"},
        headers=auth_headers(token),
    )
    assert res.status_code == 409, res.text
    assert res.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"


def test_incident_review_happy_path_logistics(client, db_session):
    tenant = _demo_tenant(db_session)
    driver = _create_driver_user(db_session, tenant, email="driver.c.inc.review@demo.cortecero.app")
    route, stops = _create_route_with_stops(db_session, tenant, driver_id=driver.id)
    incident = _create_incident(
        db_session,
        tenant,
        route=route,
        route_stop_id=stops[0].id,
        status=IncidentStatus.open,
    )
    token = _token(
        client,
        tenant_slug=tenant.slug,
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )

    res = client.post(f"/incidents/{incident.id}/review", headers=auth_headers(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "reviewed"
    assert body["reviewed_at"] is not None

    events = list(
        db_session.scalars(
            select(RouteEvent).where(
                RouteEvent.route_id == route.id,
                RouteEvent.event_type == RouteEventType.incident_reviewed,
            )
        )
    )
    assert len(events) == 1


def test_incident_review_resolved_returns_409(client, db_session):
    tenant = _demo_tenant(db_session)
    driver = _create_driver_user(db_session, tenant, email="driver.c.inc.resolved@demo.cortecero.app")
    route, stops = _create_route_with_stops(db_session, tenant, driver_id=driver.id)
    incident = _create_incident(
        db_session,
        tenant,
        route=route,
        route_stop_id=stops[0].id,
        status=IncidentStatus.resolved,
    )
    token = _token(
        client,
        tenant_slug=tenant.slug,
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )

    res = client.post(f"/incidents/{incident.id}/review", headers=auth_headers(token))
    assert res.status_code == 409, res.text
    assert res.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"


def test_incident_resolve_happy_path_admin(client, db_session):
    tenant = _demo_tenant(db_session)
    driver = _create_driver_user(db_session, tenant, email="driver.c.inc.resolve@demo.cortecero.app")
    route, stops = _create_route_with_stops(db_session, tenant, driver_id=driver.id)
    incident = _create_incident(
        db_session,
        tenant,
        route=route,
        route_stop_id=stops[0].id,
        status=IncidentStatus.reviewed,
    )
    token = _token(
        client,
        tenant_slug=tenant.slug,
        email="admin@demo.cortecero.app",
        password="admin123",
    )

    res = client.post(
        f"/incidents/{incident.id}/resolve",
        json={"resolution_note": "resolved by dispatcher"},
        headers=auth_headers(token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "resolved"
    assert body["resolution_note"] == "resolved by dispatcher"
    assert body["resolved_at"] is not None

    events = list(
        db_session.scalars(
            select(RouteEvent).where(
                RouteEvent.route_id == route.id,
                RouteEvent.event_type == RouteEventType.incident_resolved,
            )
        )
    )
    assert len(events) == 1


def test_incident_resolve_requires_reviewed(client, db_session):
    tenant = _demo_tenant(db_session)
    driver = _create_driver_user(db_session, tenant, email="driver.c.inc.open@demo.cortecero.app")
    route, stops = _create_route_with_stops(db_session, tenant, driver_id=driver.id)
    incident = _create_incident(
        db_session,
        tenant,
        route=route,
        route_stop_id=stops[0].id,
        status=IncidentStatus.open,
    )
    token = _token(
        client,
        tenant_slug=tenant.slug,
        email="admin@demo.cortecero.app",
        password="admin123",
    )

    res = client.post(
        f"/incidents/{incident.id}/resolve",
        json={"resolution_note": "attempt before review"},
        headers=auth_headers(token),
    )
    assert res.status_code == 409, res.text
    assert res.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"


def test_incident_review_driver_forbidden(client, db_session):
    tenant = _demo_tenant(db_session)
    driver = _create_driver_user(db_session, tenant, email="driver.c.review@demo.cortecero.app")
    route, stops = _create_route_with_stops(db_session, tenant, driver_id=driver.id)
    incident = _create_incident(
        db_session,
        tenant,
        route=route,
        route_stop_id=stops[0].id,
        status=IncidentStatus.open,
    )
    token = _token(
        client,
        tenant_slug=tenant.slug,
        email="driver.c.review@demo.cortecero.app",
        password="driver123",
    )

    review_res = client.post(f"/incidents/{incident.id}/review", headers=auth_headers(token))
    resolve_res = client.post(
        f"/incidents/{incident.id}/resolve",
        json={"resolution_note": "driver cannot resolve"},
        headers=auth_headers(token),
    )
    assert review_res.status_code == 403, review_res.text
    assert resolve_res.status_code == 403, resolve_res.text
    assert review_res.json()["detail"]["code"] == "RBAC_FORBIDDEN"
    assert resolve_res.json()["detail"]["code"] == "RBAC_FORBIDDEN"
