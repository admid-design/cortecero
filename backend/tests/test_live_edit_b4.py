"""
Bloque B4 — LIVE-EDIT-001: Edición de ruta en vivo

Cubre:
  - add-stop: logistics añade pedido a ruta dispatched → 201
  - add-stop: añadir a ruta in_progress → 201
  - add-stop: pedido ya en ruta activa → 409 RESOURCE_CONFLICT
  - add-stop: ruta no encontrada → 404
  - add-stop: pedido no encontrado → 404
  - add-stop: ruta completed → 422 INVALID_STATE_TRANSITION
  - remove-stop: logistics elimina parada pending → 200
  - remove-stop: parada en estado en_route → 422 INVALID_STATE_TRANSITION
  - remove-stop: parada de otra ruta → 404
  - remove-stop: ruta completed → 422 INVALID_STATE_TRANSITION
  - move-stop: funciona con ruta in_progress (extensión B4)
"""

import uuid
from datetime import UTC, date, datetime

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
    Vehicle,
    Zone,
)
from tests.helpers import auth_headers, login_as


# ── Helpers ───────────────────────────────────────────────────────────────────


def _demo_tenant(db_session) -> Tenant:
    t = db_session.scalar(select(Tenant).where(Tenant.slug == "demo-cortecero"))
    assert t is not None
    return t


def _logistics_token(client) -> str:
    return login_as(
        client,
        tenant_slug="demo-cortecero",
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )


def _get_base_objects(db_session, tenant_id: uuid.UUID):
    """Devuelve vehicle, driver, zone para construir rutas."""
    vehicle = db_session.scalar(
        select(Vehicle).where(Vehicle.tenant_id == tenant_id, Vehicle.active.is_(True))
    )
    assert vehicle is not None

    driver = db_session.scalar(
        select(Driver).where(Driver.tenant_id == tenant_id, Driver.is_active.is_(True))
    )
    assert driver is not None

    zone = db_session.scalar(select(Zone).where(Zone.tenant_id == tenant_id))
    assert zone is not None

    return vehicle, driver, zone


def _get_or_create_plan(db_session, tenant_id: uuid.UUID, zone_id: uuid.UUID) -> Plan:
    now = datetime.now(UTC)
    plan = db_session.scalar(
        select(Plan).where(
            Plan.tenant_id == tenant_id,
            Plan.status.in_([PlanStatus.locked, PlanStatus.open]),
        )
    )
    if plan is None:
        plan = Plan(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            service_date=date.today(),
            zone_id=zone_id,
            status=PlanStatus.locked,
            version=1,
            created_at=now,
            updated_at=now,
        )
        db_session.add(plan)
        db_session.flush()
    return plan


def _build_route(db_session, tenant_id: uuid.UUID, *, status: RouteStatus = RouteStatus.dispatched) -> Route:
    now = datetime.now(UTC)
    vehicle, driver, zone = _get_base_objects(db_session, tenant_id)
    plan = _get_or_create_plan(db_session, tenant_id, zone.id)

    route = Route(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        plan_id=plan.id,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        service_date=date.today(),
        status=status,
        trip_number=1,
        version=1,
        optimization_request_id=None,
        optimization_response_json=None,
        created_at=now,
        updated_at=now,
        dispatched_at=now if status != RouteStatus.draft else None,
        completed_at=None,
    )
    db_session.add(route)
    db_session.flush()
    return route


def _build_order(db_session, tenant_id: uuid.UUID, zone_id: uuid.UUID, customer_id: uuid.UUID) -> Order:
    now = datetime.now(UTC)
    order = Order(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        customer_id=customer_id,
        zone_id=zone_id,
        external_ref=f"LIVE-B4-{uuid.uuid4()}",
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
        requires_adr=False,
        ingested_at=now,
        updated_at=now,
    )
    db_session.add(order)
    db_session.flush()
    return order


def _build_customer(db_session, tenant_id: uuid.UUID, zone_id: uuid.UUID) -> Customer:
    now = datetime.now(UTC)
    customer = Customer(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=f"Live-Edit Customer {uuid.uuid4().hex[:6]}",
        zone_id=zone_id,
        lat=39.5696,
        lng=2.6502,
        created_at=now,
    )
    db_session.add(customer)
    db_session.flush()
    return customer


def _build_stop(db_session, tenant_id: uuid.UUID, route_id: uuid.UUID, order_id: uuid.UUID,
                seq: int = 1, status: RouteStopStatus = RouteStopStatus.pending) -> RouteStop:
    now = datetime.now(UTC)
    stop = RouteStop(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        route_id=route_id,
        order_id=order_id,
        sequence_number=seq,
        estimated_arrival_at=None,
        estimated_service_minutes=10,
        status=status,
        arrived_at=None,
        completed_at=None,
        failed_at=None,
        failure_reason=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(stop)
    db_session.flush()
    return stop


# ── add-stop ─────────────────────────────────────────────────────────────────


def test_add_stop_to_dispatched_route(client, db_session):
    """logistics añade pedido a ruta dispatched → 201 con stop_id y sequence."""
    tenant = _demo_tenant(db_session)
    _, _, zone = _get_base_objects(db_session, tenant.id)
    route = _build_route(db_session, tenant.id, status=RouteStatus.dispatched)
    customer = _build_customer(db_session, tenant.id, zone.id)
    order = _build_order(db_session, tenant.id, zone.id, customer.id)
    db_session.commit()

    token = _logistics_token(client)
    res = client.post(
        f"/routes/{route.id}/add-stop",
        json={"order_id": str(order.id)},
        headers=auth_headers(token),
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["order_id"] == str(order.id)
    assert data["route_id"] == str(route.id)
    assert "stop_id" in data
    assert data["sequence_number"] == 1


def test_add_stop_to_in_progress_route(client, db_session):
    """Añadir parada a ruta in_progress → 201."""
    tenant = _demo_tenant(db_session)
    _, _, zone = _get_base_objects(db_session, tenant.id)
    route = _build_route(db_session, tenant.id, status=RouteStatus.in_progress)
    customer = _build_customer(db_session, tenant.id, zone.id)
    order = _build_order(db_session, tenant.id, zone.id, customer.id)
    db_session.commit()

    token = _logistics_token(client)
    res = client.post(
        f"/routes/{route.id}/add-stop",
        json={"order_id": str(order.id)},
        headers=auth_headers(token),
    )
    assert res.status_code == 201, res.text


def test_add_stop_order_already_in_route_returns_409(client, db_session):
    """Pedido ya en una ruta activa → 409 RESOURCE_CONFLICT."""
    tenant = _demo_tenant(db_session)
    _, _, zone = _get_base_objects(db_session, tenant.id)
    route = _build_route(db_session, tenant.id, status=RouteStatus.dispatched)
    customer = _build_customer(db_session, tenant.id, zone.id)
    order = _build_order(db_session, tenant.id, zone.id, customer.id)
    _build_stop(db_session, tenant.id, route.id, order.id)
    db_session.commit()

    token = _logistics_token(client)
    res = client.post(
        f"/routes/{route.id}/add-stop",
        json={"order_id": str(order.id)},
        headers=auth_headers(token),
    )
    assert res.status_code == 409, res.text
    assert res.json()["detail"]["code"] == "RESOURCE_CONFLICT"


def test_add_stop_route_not_found_returns_404(client, db_session):
    """Ruta inexistente → 404."""
    token = _logistics_token(client)
    res = client.post(
        f"/routes/{uuid.uuid4()}/add-stop",
        json={"order_id": str(uuid.uuid4())},
        headers=auth_headers(token),
    )
    assert res.status_code == 404, res.text


def test_add_stop_order_not_found_returns_404(client, db_session):
    """Pedido inexistente → 404."""
    tenant = _demo_tenant(db_session)
    route = _build_route(db_session, tenant.id, status=RouteStatus.dispatched)
    db_session.commit()

    token = _logistics_token(client)
    res = client.post(
        f"/routes/{route.id}/add-stop",
        json={"order_id": str(uuid.uuid4())},
        headers=auth_headers(token),
    )
    assert res.status_code == 404, res.text


def test_add_stop_to_completed_route_returns_422(client, db_session):
    """Ruta completed → 422 INVALID_STATE_TRANSITION."""
    tenant = _demo_tenant(db_session)
    _, _, zone = _get_base_objects(db_session, tenant.id)
    route = _build_route(db_session, tenant.id, status=RouteStatus.completed)
    customer = _build_customer(db_session, tenant.id, zone.id)
    order = _build_order(db_session, tenant.id, zone.id, customer.id)
    db_session.commit()

    token = _logistics_token(client)
    res = client.post(
        f"/routes/{route.id}/add-stop",
        json={"order_id": str(order.id)},
        headers=auth_headers(token),
    )
    assert res.status_code == 422, res.text
    assert res.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"


# ── remove-stop ───────────────────────────────────────────────────────────────


def test_remove_pending_stop(client, db_session):
    """Eliminar parada pending → 200 con removed_stop_id."""
    tenant = _demo_tenant(db_session)
    _, _, zone = _get_base_objects(db_session, tenant.id)
    route = _build_route(db_session, tenant.id, status=RouteStatus.in_progress)
    customer = _build_customer(db_session, tenant.id, zone.id)
    order = _build_order(db_session, tenant.id, zone.id, customer.id)
    stop = _build_stop(db_session, tenant.id, route.id, order.id, status=RouteStopStatus.pending)
    db_session.commit()

    token = _logistics_token(client)
    res = client.post(
        f"/routes/{route.id}/stops/{stop.id}/remove",
        headers=auth_headers(token),
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["removed_stop_id"] == str(stop.id)
    assert data["order_id"] == str(order.id)

    # Verificar que la parada ya no existe
    gone = db_session.scalar(select(RouteStop).where(RouteStop.id == stop.id))
    assert gone is None


def test_remove_non_pending_stop_returns_422(client, db_session):
    """Parada en estado en_route → 422."""
    tenant = _demo_tenant(db_session)
    _, _, zone = _get_base_objects(db_session, tenant.id)
    route = _build_route(db_session, tenant.id, status=RouteStatus.in_progress)
    customer = _build_customer(db_session, tenant.id, zone.id)
    order = _build_order(db_session, tenant.id, zone.id, customer.id)
    stop = _build_stop(db_session, tenant.id, route.id, order.id, status=RouteStopStatus.en_route)
    db_session.commit()

    token = _logistics_token(client)
    res = client.post(
        f"/routes/{route.id}/stops/{stop.id}/remove",
        headers=auth_headers(token),
    )
    assert res.status_code == 422, res.text
    assert res.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"


def test_remove_stop_wrong_route_returns_404(client, db_session):
    """Parada que no pertenece a esta ruta → 404."""
    tenant = _demo_tenant(db_session)
    _, _, zone = _get_base_objects(db_session, tenant.id)
    route_a = _build_route(db_session, tenant.id, status=RouteStatus.dispatched)
    route_b = _build_route(db_session, tenant.id, status=RouteStatus.dispatched)
    customer = _build_customer(db_session, tenant.id, zone.id)
    order = _build_order(db_session, tenant.id, zone.id, customer.id)
    stop = _build_stop(db_session, tenant.id, route_b.id, order.id)
    db_session.commit()

    token = _logistics_token(client)
    res = client.post(
        f"/routes/{route_a.id}/stops/{stop.id}/remove",
        headers=auth_headers(token),
    )
    assert res.status_code == 404, res.text


def test_remove_stop_completed_route_returns_422(client, db_session):
    """Ruta completed → 422."""
    tenant = _demo_tenant(db_session)
    _, _, zone = _get_base_objects(db_session, tenant.id)
    route = _build_route(db_session, tenant.id, status=RouteStatus.completed)
    customer = _build_customer(db_session, tenant.id, zone.id)
    order = _build_order(db_session, tenant.id, zone.id, customer.id)
    stop = _build_stop(db_session, tenant.id, route.id, order.id)
    db_session.commit()

    token = _logistics_token(client)
    res = client.post(
        f"/routes/{route.id}/stops/{stop.id}/remove",
        headers=auth_headers(token),
    )
    assert res.status_code == 422, res.text


# ── move-stop extendido a in_progress ────────────────────────────────────────


def test_move_stop_from_in_progress_route(client, db_session):
    """move-stop funciona con ruta origen in_progress (extensión B4)."""
    tenant = _demo_tenant(db_session)
    _, _, zone = _get_base_objects(db_session, tenant.id)
    route_src = _build_route(db_session, tenant.id, status=RouteStatus.in_progress)
    route_dst = _build_route(db_session, tenant.id, status=RouteStatus.dispatched)
    customer = _build_customer(db_session, tenant.id, zone.id)
    order = _build_order(db_session, tenant.id, zone.id, customer.id)
    stop = _build_stop(db_session, tenant.id, route_src.id, order.id)
    db_session.commit()

    token = _logistics_token(client)
    res = client.post(
        f"/routes/{route_src.id}/move-stop",
        json={"stop_id": str(stop.id), "target_route_id": str(route_dst.id)},
        headers=auth_headers(token),
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["to_route_id"] == str(route_dst.id)
