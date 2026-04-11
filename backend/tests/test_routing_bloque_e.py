"""
Bloque E.1 — Tests de optimización de rutas (mock provider)

Cubre:
  - POST /routes/plan → rutas se crean en estado 'draft'  (regresión fix)
  - POST /routes/{id}/optimize → happy path: draft → planned
  - POST /routes/{id}/optimize → reorden de sequence_number por mock
  - POST /routes/{id}/optimize → estimated_arrival_at populado en paradas
  - POST /routes/{id}/optimize → optimization_request_id y optimization_response_json persistidos
  - POST /routes/{id}/optimize → evento route.planned emitido (actor_type: system)
  - POST /routes/{id}/optimize → 409 si ruta no está en draft
  - POST /routes/{id}/optimize → 404 si ruta de otro tenant
  - POST /routes/{id}/optimize → 422 MISSING_GEO si cliente sin coordenadas
  - POST /routes/{id}/optimize → 403 si rol sin permisos (office)
"""

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from app.models import (
    Customer,
    Order,
    OrderIntakeType,
    OrderStatus,
    Plan,
    PlanStatus,
    Route,
    RouteEvent,
    RouteEventActorType,
    RouteEventType,
    RouteStatus,
    RouteStop,
    RouteStopStatus,
    SourceChannel,
    Tenant,
    Vehicle,
    Zone,
)
from tests.helpers import auth_headers, login_as

# ---------------------------------------------------------------------------
# Helpers de sesión
# ---------------------------------------------------------------------------


def _get_tenant(db_session) -> Tenant:
    t = db_session.scalar(select(Tenant).where(Tenant.slug == "demo-cortecero"))
    assert t is not None, "Tenant demo-cortecero no encontrado (seed no ejecutado)"
    return t


def _logistics_token(client) -> str:
    return login_as(
        client,
        tenant_slug="demo-cortecero",
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )


def _office_token(client) -> str:
    return login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )


# ---------------------------------------------------------------------------
# Builder de ruta en estado draft con clientes que tienen lat/lng
# ---------------------------------------------------------------------------


def _build_draft_route_with_geo(
    db_session,
    tenant_id: uuid.UUID,
    n_stops: int = 2,
) -> tuple[Route, list[RouteStop]]:
    """
    Crea un Route en estado draft + RouteStops cuyos pedidos tienen clientes con lat/lng.
    Reutiliza vehículo del seed.  Los clientes del seed (Bloque G) ya tienen coordenadas.
    """
    now = datetime.now(UTC)
    svc_date = date.today()

    vehicle = db_session.scalar(
        select(Vehicle).where(Vehicle.tenant_id == tenant_id, Vehicle.active.is_(True))
    )
    assert vehicle is not None, "No hay vehículos activos en seed"

    zone = db_session.scalar(select(Zone).where(Zone.tenant_id == tenant_id))
    assert zone is not None

    # Usar clientes del seed con coordenadas
    customers_with_geo = list(
        db_session.scalars(
            select(Customer)
            .where(
                Customer.tenant_id == tenant_id,
                Customer.lat.is_not(None),
                Customer.lng.is_not(None),
            )
            .limit(n_stops)
        )
    )
    assert len(customers_with_geo) >= n_stops, (
        f"Se necesitan {n_stops} clientes con geo en seed, solo hay {len(customers_with_geo)}"
    )

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
        driver_id=None,
        service_date=svc_date,
        status=RouteStatus.draft,
        version=1,
        optimization_request_id=None,
        optimization_response_json=None,
        created_at=now,
        updated_at=now,
        dispatched_at=None,
        completed_at=None,
    )
    db_session.add(route)
    db_session.flush()

    stops: list[RouteStop] = []
    for i, customer in enumerate(customers_with_geo[:n_stops]):
        order = Order(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            customer_id=customer.id,
            zone_id=zone.id,
            external_ref=f"BLK-E-{uuid.uuid4()}",
            requested_date=svc_date,
            service_date=svc_date,
            created_at=now,
            status=OrderStatus.assigned,
            is_late=False,
            lateness_reason=None,
            effective_cutoff_at=now,
            source_channel=SourceChannel.office,
            intake_type=OrderIntakeType.new_order,
            total_weight_kg=10.0,
            ingested_at=now,
            updated_at=now,
        )
        db_session.add(order)
        db_session.flush()

        stop = RouteStop(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            route_id=route.id,
            order_id=order.id,
            sequence_number=i + 1,
            estimated_arrival_at=None,
            estimated_service_minutes=10,
            status=RouteStopStatus.pending,
            arrived_at=None,
            completed_at=None,
            failed_at=None,
            failure_reason=None,
            created_at=now,
            updated_at=now,
        )
        db_session.add(stop)
        db_session.flush()
        stops.append(stop)

    db_session.commit()
    db_session.refresh(route)
    for s in stops:
        db_session.refresh(s)
    return route, stops


# ---------------------------------------------------------------------------
# Regresión: POST /routes/plan crea rutas en estado 'draft'
# ---------------------------------------------------------------------------


def test_plan_routes_creates_routes_as_draft(client, db_session):
    """Regresión E.1: plan_routes ahora crea rutas en estado draft, no planned."""
    tenant = _get_tenant(db_session)
    token = _logistics_token(client)

    # Obtener plan y vehicle del seed
    plan = db_session.scalar(
        select(Plan).where(Plan.tenant_id == tenant.id, Plan.status == PlanStatus.locked)
    )
    vehicle = db_session.scalar(
        select(Vehicle).where(Vehicle.tenant_id == tenant.id, Vehicle.active.is_(True))
    )
    # Obtener pedido en estado planned del seed
    order = db_session.scalar(
        select(Order).where(Order.tenant_id == tenant.id, Order.status == OrderStatus.planned)
    )

    if not plan or not vehicle or not order:
        pytest.skip("Seed no tiene plan locked, vehicle activo o pedido planned")

    payload = {
        "plan_id": str(plan.id),
        "service_date": str(order.service_date),
        "routes": [
            {
                "vehicle_id": str(vehicle.id),
                "driver_id": None,
                "order_ids": [str(order.id)],
            }
        ],
    }

    res = client.post("/routes/plan", json=payload, headers=auth_headers(token))
    assert res.status_code == 201, res.text

    body = res.json()
    assert body["routes_created"][0]["status"] == "draft"


# ---------------------------------------------------------------------------
# Happy path: draft → planned
# ---------------------------------------------------------------------------


def test_optimize_happy_path(client, db_session):
    """Ruta en draft con clientes con geo → optimize → planned."""
    tenant = _get_tenant(db_session)
    route, _ = _build_draft_route_with_geo(db_session, tenant.id, n_stops=2)
    token = _logistics_token(client)

    res = client.post(f"/routes/{route.id}/optimize", headers=auth_headers(token))
    assert res.status_code == 200, res.text

    body = res.json()
    assert body["status"] == "planned"
    assert body["id"] == str(route.id)


def test_optimize_transitions_route_to_planned(client, db_session):
    """Verifica estado en DB tras optimize."""
    tenant = _get_tenant(db_session)
    route, _ = _build_draft_route_with_geo(db_session, tenant.id, n_stops=2)
    token = _logistics_token(client)

    client.post(f"/routes/{route.id}/optimize", headers=auth_headers(token))

    db_session.expire_all()
    updated = db_session.get(Route, route.id)
    assert updated.status == RouteStatus.planned


def test_optimize_populates_optimization_fields(client, db_session):
    """optimization_request_id y optimization_response_json se persisten."""
    tenant = _get_tenant(db_session)
    route, _ = _build_draft_route_with_geo(db_session, tenant.id, n_stops=2)
    token = _logistics_token(client)

    client.post(f"/routes/{route.id}/optimize", headers=auth_headers(token))

    db_session.expire_all()
    updated = db_session.get(Route, route.id)
    assert updated.optimization_request_id is not None
    assert updated.optimization_response_json is not None
    assert updated.optimization_response_json.get("provider") == "mock"


def test_optimize_populates_estimated_arrival_at(client, db_session):
    """estimated_arrival_at se popula en todas las paradas."""
    tenant = _get_tenant(db_session)
    route, stops = _build_draft_route_with_geo(db_session, tenant.id, n_stops=3)
    token = _logistics_token(client)

    client.post(f"/routes/{route.id}/optimize", headers=auth_headers(token))

    db_session.expire_all()
    for stop in stops:
        updated_stop = db_session.get(RouteStop, stop.id)
        assert updated_stop.estimated_arrival_at is not None, (
            f"Stop {stop.id} no tiene estimated_arrival_at tras optimize"
        )


def test_optimize_reorders_sequence_numbers(client, db_session):
    """Mock provider asigna sequence_number 1-based; paradas tienen secuencia válida."""
    tenant = _get_tenant(db_session)
    route, stops = _build_draft_route_with_geo(db_session, tenant.id, n_stops=3)
    token = _logistics_token(client)

    client.post(f"/routes/{route.id}/optimize", headers=auth_headers(token))

    db_session.expire_all()
    updated_stops = list(
        db_session.scalars(
            select(RouteStop)
            .where(RouteStop.route_id == route.id)
            .order_by(RouteStop.sequence_number)
        )
    )
    seqs = [s.sequence_number for s in updated_stops]
    assert seqs == list(range(1, len(stops) + 1)), f"Secuencia inválida: {seqs}"


def test_optimize_emits_route_planned_event(client, db_session):
    """Evento route.planned emitido con actor_type=system."""
    tenant = _get_tenant(db_session)
    route, _ = _build_draft_route_with_geo(db_session, tenant.id, n_stops=2)
    token = _logistics_token(client)

    client.post(f"/routes/{route.id}/optimize", headers=auth_headers(token))

    db_session.expire_all()
    events = list(
        db_session.scalars(
            select(RouteEvent).where(
                RouteEvent.route_id == route.id,
                RouteEvent.event_type == RouteEventType.route_planned,
            )
        )
    )
    assert len(events) == 1
    assert events[0].actor_type == RouteEventActorType.system
    assert events[0].actor_id is None


# ---------------------------------------------------------------------------
# Error: estado incorrecto
# ---------------------------------------------------------------------------


def test_optimize_409_if_not_draft(client, db_session):
    """Ruta en estado 'planned' devuelve 409 INVALID_STATE_TRANSITION."""
    tenant = _get_tenant(db_session)
    route, _ = _build_draft_route_with_geo(db_session, tenant.id, n_stops=1)
    token = _logistics_token(client)

    # Pasar a planned directamente en DB
    route.status = RouteStatus.planned
    db_session.commit()

    res = client.post(f"/routes/{route.id}/optimize", headers=auth_headers(token))
    assert res.status_code == 409, res.text
    assert res.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"


def test_optimize_409_if_dispatched(client, db_session):
    """Ruta en estado 'dispatched' devuelve 409."""
    tenant = _get_tenant(db_session)
    route, _ = _build_draft_route_with_geo(db_session, tenant.id, n_stops=1)
    token = _logistics_token(client)

    route.status = RouteStatus.dispatched
    db_session.commit()

    res = client.post(f"/routes/{route.id}/optimize", headers=auth_headers(token))
    assert res.status_code == 409, res.text


# ---------------------------------------------------------------------------
# Error: tenant isolation
# ---------------------------------------------------------------------------


def test_optimize_404_if_wrong_tenant(client, db_session):
    """Ruta de otro tenant devuelve 404."""
    now = datetime.now(UTC)
    svc_date = date.today()

    # Crear tenant alternativo con su propio vehicle y route
    tenant_b = Tenant(
        name="Tenant E Test",
        slug="tenant-e-test",
        default_cutoff_time=datetime.strptime("10:00", "%H:%M").time(),
        default_timezone="Europe/Madrid",
        auto_lock_enabled=False,
        created_at=now,
    )
    db_session.add(tenant_b)
    db_session.flush()

    vehicle_b = Vehicle(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        code="VEH-E-B",
        name="Vehículo Tenant B",
        capacity_kg=1000,
        active=True,
        created_at=now,
    )
    db_session.add(vehicle_b)
    db_session.flush()

    zone_b = Zone(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        name="Zona B",
        default_cutoff_time=datetime.strptime("08:00", "%H:%M").time(),
        timezone="Europe/Madrid",
        active=True,
        created_at=now,
    )
    db_session.add(zone_b)
    db_session.flush()

    plan_b = Plan(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        service_date=svc_date,
        zone_id=zone_b.id,
        status=PlanStatus.locked,
        version=1,
        created_at=now,
        updated_at=now,
    )
    db_session.add(plan_b)
    db_session.flush()

    route_b = Route(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        plan_id=plan_b.id,
        vehicle_id=vehicle_b.id,
        driver_id=None,
        service_date=svc_date,
        status=RouteStatus.draft,
        version=1,
        optimization_request_id=None,
        optimization_response_json=None,
        created_at=now,
        updated_at=now,
        dispatched_at=None,
        completed_at=None,
    )
    db_session.add(route_b)
    db_session.commit()

    # El token es de demo-cortecero, no de tenant_b
    token = _logistics_token(client)
    res = client.post(f"/routes/{route_b.id}/optimize", headers=auth_headers(token))
    assert res.status_code == 404, res.text


# ---------------------------------------------------------------------------
# Error: MISSING_GEO
# ---------------------------------------------------------------------------


def test_optimize_422_missing_geo(client, db_session):
    """Ruta con cliente sin lat/lng devuelve 422 MISSING_GEO."""
    tenant = _get_tenant(db_session)
    now = datetime.now(UTC)
    svc_date = date.today()
    token = _logistics_token(client)

    vehicle = db_session.scalar(
        select(Vehicle).where(Vehicle.tenant_id == tenant.id, Vehicle.active.is_(True))
    )
    zone = db_session.scalar(select(Zone).where(Zone.tenant_id == tenant.id))

    # Cliente explícitamente sin coordenadas
    customer_no_geo = Customer(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        zone_id=zone.id,
        name="Cliente Sin Geo",
        priority=0,
        cutoff_override_time=None,
        active=True,
        lat=None,
        lng=None,
        delivery_address=None,
        created_at=now,
    )
    db_session.add(customer_no_geo)
    db_session.flush()

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
        driver_id=None,
        service_date=svc_date,
        status=RouteStatus.draft,
        version=1,
        optimization_request_id=None,
        optimization_response_json=None,
        created_at=now,
        updated_at=now,
        dispatched_at=None,
        completed_at=None,
    )
    db_session.add(route)
    db_session.flush()

    order = Order(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        customer_id=customer_no_geo.id,
        zone_id=zone.id,
        external_ref=f"BLK-E-NOGEO-{uuid.uuid4()}",
        requested_date=svc_date,
        service_date=svc_date,
        created_at=now,
        status=OrderStatus.assigned,
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

    stop = RouteStop(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        route_id=route.id,
        order_id=order.id,
        sequence_number=1,
        estimated_arrival_at=None,
        estimated_service_minutes=10,
        status=RouteStopStatus.pending,
        arrived_at=None,
        completed_at=None,
        failed_at=None,
        failure_reason=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(stop)
    db_session.commit()

    res = client.post(f"/routes/{route.id}/optimize", headers=auth_headers(token))
    assert res.status_code == 422, res.text
    detail = res.json()["detail"]
    assert detail["code"] == "MISSING_GEO"
    assert str(order.id) in detail["message"]


# ---------------------------------------------------------------------------
# Error: rol sin permisos
# ---------------------------------------------------------------------------


def test_optimize_403_for_office_role(client, db_session):
    """Usuario con rol 'office' no puede llamar al endpoint de optimización."""
    tenant = _get_tenant(db_session)
    route, _ = _build_draft_route_with_geo(db_session, tenant.id, n_stops=1)
    token = _office_token(client)

    res = client.post(f"/routes/{route.id}/optimize", headers=auth_headers(token))
    assert res.status_code == 403, res.text
