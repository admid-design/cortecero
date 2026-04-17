"""
Bloque F5 — ADR-001: Restricciones de mercancías peligrosas

Cubre:
  - Vehicle.is_adr_certified defaultea a False
  - Order.requires_adr defaultea a False
  - OptimizationWaypoint.requires_adr defaultea a False
  - OptimizationRequest.vehicle_adr_certified defaultea a False
  - optimize_route: pedido ADR + vehículo no ADR → 422 ADR_VEHICLE_REQUIRED
  - optimize_route: pedido ADR + vehículo ADR → 200 OK
  - optimize_route: pedido no ADR + vehículo no ADR → 200 OK
  - optimize_route: requires_adr se pasa correctamente al waypoint
  - optimize_route: vehicle_adr_certified se pasa correctamente al request
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
from app.optimization.protocol import OptimizationRequest, OptimizationWaypoint
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


def _build_route_with_adr_flags(
    db_session,
    tenant_id: uuid.UUID,
    *,
    vehicle_adr: bool = False,
    order_adr: bool = False,
) -> Route:
    now = datetime.now(UTC)
    svc_date = date.today()

    vehicle = db_session.scalar(
        select(Vehicle).where(Vehicle.tenant_id == tenant_id, Vehicle.active.is_(True))
    )
    assert vehicle is not None
    vehicle.is_adr_certified = vehicle_adr
    db_session.flush()

    driver = db_session.scalar(
        select(Driver).where(Driver.tenant_id == tenant_id, Driver.is_active.is_(True))
    )
    assert driver is not None

    zone = db_session.scalar(select(Zone).where(Zone.tenant_id == tenant_id))
    assert zone is not None

    customer = Customer(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=f"ADR Customer {uuid.uuid4().hex[:6]}",
        zone_id=zone.id,
        lat=39.5696,
        lng=2.6502,
        created_at=now,
    )
    db_session.add(customer)
    db_session.flush()

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
        status=RouteStatus.draft,
        trip_number=1,
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
        tenant_id=tenant_id,
        customer_id=customer.id,
        zone_id=zone.id,
        external_ref=f"ADR-F5-{uuid.uuid4()}",
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
        requires_adr=order_adr,
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
    db_session.refresh(route)
    return route


# ── Unit: defaults ────────────────────────────────────────────────────────────


def test_waypoint_requires_adr_defaults_false():
    wp = OptimizationWaypoint(order_id=uuid.uuid4(), lat=0.0, lng=0.0)
    assert wp.requires_adr is False


def test_waypoint_accepts_requires_adr_true():
    wp = OptimizationWaypoint(order_id=uuid.uuid4(), lat=0.0, lng=0.0, requires_adr=True)
    assert wp.requires_adr is True


def test_request_vehicle_adr_certified_defaults_false():
    req = OptimizationRequest(route_id=uuid.uuid4(), depot_lat=0.0, depot_lng=0.0)
    assert req.vehicle_adr_certified is False


def test_request_accepts_vehicle_adr_certified_true():
    req = OptimizationRequest(
        route_id=uuid.uuid4(), depot_lat=0.0, depot_lng=0.0, vehicle_adr_certified=True
    )
    assert req.vehicle_adr_certified is True


# ── Integration: validación ADR en optimize_route ────────────────────────────


def test_optimize_adr_order_non_adr_vehicle_returns_422(client, db_session):
    """Pedido ADR + vehículo sin certificación → 422 ADR_VEHICLE_REQUIRED."""
    tenant = _demo_tenant(db_session)
    route = _build_route_with_adr_flags(
        db_session, tenant.id, vehicle_adr=False, order_adr=True
    )
    token = _logistics_token(client)

    res = client.post(f"/routes/{route.id}/optimize", headers=auth_headers(token))
    assert res.status_code == 422, res.text
    assert res.json()["detail"]["code"] == "ADR_VEHICLE_REQUIRED"


def test_optimize_adr_order_adr_vehicle_returns_200(client, db_session, monkeypatch):
    """Pedido ADR + vehículo certificado → 200 OK."""
    tenant = _demo_tenant(db_session)
    route = _build_route_with_adr_flags(
        db_session, tenant.id, vehicle_adr=True, order_adr=True
    )
    token = _logistics_token(client)

    from app.optimization.mock_provider import MockRouteOptimizationProvider as _MockProvider
    import app.routers.routing as routing_module
    monkeypatch.setattr(routing_module, "_get_optimization_provider", lambda: _MockProvider())

    res = client.post(f"/routes/{route.id}/optimize", headers=auth_headers(token))
    assert res.status_code == 200, res.text


def test_optimize_non_adr_order_non_adr_vehicle_returns_200(client, db_session, monkeypatch):
    """Pedido sin ADR + vehículo sin certificación → 200 OK (caso normal)."""
    tenant = _demo_tenant(db_session)
    route = _build_route_with_adr_flags(
        db_session, tenant.id, vehicle_adr=False, order_adr=False
    )
    token = _logistics_token(client)

    from app.optimization.mock_provider import MockRouteOptimizationProvider as _MockProvider
    import app.routers.routing as routing_module
    monkeypatch.setattr(routing_module, "_get_optimization_provider", lambda: _MockProvider())

    res = client.post(f"/routes/{route.id}/optimize", headers=auth_headers(token))
    assert res.status_code == 200, res.text


def test_optimize_adr_flags_passed_correctly_to_request(client, db_session, monkeypatch):
    """requires_adr y vehicle_adr_certified se propagan correctamente al OptimizationRequest."""
    tenant = _demo_tenant(db_session)
    route = _build_route_with_adr_flags(
        db_session, tenant.id, vehicle_adr=True, order_adr=True
    )
    token = _logistics_token(client)

    captured: list[OptimizationRequest] = []

    from app.optimization.mock_provider import MockRouteOptimizationProvider as _MockProvider

    class _SpyProvider(_MockProvider):
        def optimize(self, request: OptimizationRequest):  # type: ignore[override]
            captured.append(request)
            return super().optimize(request)

    import app.routers.routing as routing_module
    monkeypatch.setattr(routing_module, "_get_optimization_provider", lambda: _SpyProvider())

    res = client.post(f"/routes/{route.id}/optimize", headers=auth_headers(token))
    assert res.status_code == 200, res.text
    assert len(captured) == 1

    req = captured[0]
    assert req.vehicle_adr_certified is True
    assert len(req.waypoints) == 1
    assert req.waypoints[0].requires_adr is True
