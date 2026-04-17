"""
Bloque F2 — CAPACITY-001: Restricciones de capacidad de vehículo en optimizer

Cubre:
  - OptimizationWaypoint acepta weight_kg opcional
  - OptimizationRequest acepta vehicle_capacity_kg opcional
  - _build_body: sin capacidad/peso → no loadLimits/loadDemands
  - _build_body: con capacidad → loadLimits en vehículo (gramos)
  - _build_body: con peso → loadDemands en delivery (gramos)
  - _build_body: capacidad + peso → ambos presentes con conversión correcta
  - optimize_route: pasa vehicle_capacity_kg del vehículo al request
  - optimize_route: pasa weight_kg del pedido al waypoint
"""

import uuid
from datetime import UTC, date, datetime, time

import pytest
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
from app.optimization.google_provider import GoogleRouteOptimizationProvider
from app.optimization.protocol import OptimizationRequest, OptimizationWaypoint
from tests.helpers import auth_headers, login_as


# ── Helpers ───────────────────────────────────────────────────────────────────

_FUTURE_DATE = date(2030, 6, 15)  # fecha futura — evita floor now+5min en global_window


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


def _make_provider() -> GoogleRouteOptimizationProvider:
    return GoogleRouteOptimizationProvider(project_id="test-project")


def _base_request(
    *,
    weight_kg: float | None = None,
    vehicle_capacity_kg: float | None = None,
) -> OptimizationRequest:
    return OptimizationRequest(
        route_id=uuid.uuid4(),
        depot_lat=39.648,
        depot_lng=2.787,
        service_date=_FUTURE_DATE,
        vehicle_capacity_kg=vehicle_capacity_kg,
        waypoints=[
            OptimizationWaypoint(
                order_id=uuid.uuid4(),
                lat=39.5696,
                lng=2.6502,
                service_minutes=10,
                weight_kg=weight_kg,
            )
        ],
    )


# ── Unit: campos opcionales en dataclasses ───────────────────────────────────


def test_waypoint_defaults_no_weight():
    wp = OptimizationWaypoint(order_id=uuid.uuid4(), lat=0.0, lng=0.0)
    assert wp.weight_kg is None


def test_waypoint_accepts_weight():
    wp = OptimizationWaypoint(order_id=uuid.uuid4(), lat=0.0, lng=0.0, weight_kg=12.5)
    assert wp.weight_kg == 12.5


def test_request_defaults_no_capacity():
    req = OptimizationRequest(route_id=uuid.uuid4(), depot_lat=0.0, depot_lng=0.0)
    assert req.vehicle_capacity_kg is None


def test_request_accepts_capacity():
    req = OptimizationRequest(
        route_id=uuid.uuid4(), depot_lat=0.0, depot_lng=0.0, vehicle_capacity_kg=500.0
    )
    assert req.vehicle_capacity_kg == 500.0


# ── Unit: _build_body sin capacidad/peso ─────────────────────────────────────


def test_build_body_no_capacity_no_load_limits():
    """Sin vehicle_capacity_kg → el vehículo no lleva loadLimits."""
    provider = _make_provider()
    body = provider._build_body(_base_request(vehicle_capacity_kg=None))
    vehicle = body["model"]["vehicles"][0]
    assert "loadLimits" not in vehicle


def test_build_body_no_weight_no_load_demands():
    """Sin weight_kg → el delivery no lleva loadDemands."""
    provider = _make_provider()
    body = provider._build_body(_base_request(weight_kg=None))
    delivery = body["model"]["shipments"][0]["deliveries"][0]
    assert "loadDemands" not in delivery


# ── Unit: _build_body con capacidad y/o peso ─────────────────────────────────


def test_build_body_capacity_produces_load_limits():
    """vehicle_capacity_kg=1000 → loadLimits.weight_kg.maxLoad='1000000' (gramos)."""
    provider = _make_provider()
    body = provider._build_body(_base_request(vehicle_capacity_kg=1000.0))
    vehicle = body["model"]["vehicles"][0]
    assert "loadLimits" in vehicle
    assert vehicle["loadLimits"]["weight_kg"]["maxLoad"] == "1000000"


def test_build_body_weight_produces_load_demands():
    """weight_kg=5.5 → loadDemands.weight_kg.amount='5500' (gramos)."""
    provider = _make_provider()
    body = provider._build_body(_base_request(weight_kg=5.5))
    delivery = body["model"]["shipments"][0]["deliveries"][0]
    assert "loadDemands" in delivery
    assert delivery["loadDemands"]["weight_kg"]["amount"] == "5500"


def test_build_body_fractional_weight_rounds_to_grams():
    """weight_kg=0.001 → 1 gramo (round al entero más cercano)."""
    provider = _make_provider()
    body = provider._build_body(_base_request(weight_kg=0.001))
    delivery = body["model"]["shipments"][0]["deliveries"][0]
    assert delivery["loadDemands"]["weight_kg"]["amount"] == "1"


def test_build_body_capacity_and_weight_both_present():
    """Con ambos → loadLimits en vehicle + loadDemands en delivery."""
    provider = _make_provider()
    body = provider._build_body(
        _base_request(vehicle_capacity_kg=500.0, weight_kg=10.0)
    )
    vehicle = body["model"]["vehicles"][0]
    delivery = body["model"]["shipments"][0]["deliveries"][0]
    assert vehicle["loadLimits"]["weight_kg"]["maxLoad"] == "500000"
    assert delivery["loadDemands"]["weight_kg"]["amount"] == "10000"


def test_build_body_load_limits_key_matches_load_demands_key():
    """La clave del tipo de carga debe ser idéntica en vehicle y shipment."""
    provider = _make_provider()
    body = provider._build_body(
        _base_request(vehicle_capacity_kg=200.0, weight_kg=3.0)
    )
    vehicle_key = list(body["model"]["vehicles"][0]["loadLimits"].keys())[0]
    demand_key = list(
        body["model"]["shipments"][0]["deliveries"][0]["loadDemands"].keys()
    )[0]
    assert vehicle_key == demand_key


# ── Integration: optimize_route pasa capacidad y peso ────────────────────────


def _build_route_with_vehicle_and_order(
    db_session,
    tenant_id: uuid.UUID,
    *,
    vehicle_capacity_kg: float | None = None,
    order_weight_kg: float | None = None,
) -> Route:
    now = datetime.now(UTC)
    svc_date = date.today()

    vehicle = db_session.scalar(
        select(Vehicle).where(Vehicle.tenant_id == tenant_id, Vehicle.active.is_(True))
    )
    assert vehicle is not None
    # Sobreescribir capacidad del vehículo para el test
    vehicle.capacity_kg = vehicle_capacity_kg
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
        name=f"CAP Customer {uuid.uuid4().hex[:6]}",
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
        external_ref=f"CAP-F2-{uuid.uuid4()}",
        requested_date=svc_date,
        service_date=svc_date,
        created_at=now,
        status=OrderStatus.dispatched,
        is_late=False,
        lateness_reason=None,
        effective_cutoff_at=now,
        source_channel=SourceChannel.office,
        intake_type=OrderIntakeType.new_order,
        total_weight_kg=order_weight_kg,
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


def test_optimize_passes_vehicle_capacity_and_order_weight(client, db_session, monkeypatch):
    """
    optimize_route pasa vehicle_capacity_kg y weight_kg al provider.
    El spy captura el OptimizationRequest y verifica los valores.
    """
    tenant = _demo_tenant(db_session)
    route = _build_route_with_vehicle_and_order(
        db_session, tenant.id,
        vehicle_capacity_kg=750.0,
        order_weight_kg=8.5,
    )
    token = _logistics_token(client)

    captured_requests: list[OptimizationRequest] = []

    from app.optimization.mock_provider import MockRouteOptimizationProvider as _MockProvider

    class _SpyProvider(_MockProvider):
        def optimize(self, request: OptimizationRequest):  # type: ignore[override]
            captured_requests.append(request)
            return super().optimize(request)

    import app.routers.routing as routing_module
    monkeypatch.setattr(routing_module, "_get_optimization_provider", lambda: _SpyProvider())

    res = client.post(f"/routes/{route.id}/optimize", headers=auth_headers(token))
    assert res.status_code == 200, res.text
    assert len(captured_requests) == 1

    req = captured_requests[0]
    assert req.vehicle_capacity_kg == 750.0
    assert len(req.waypoints) == 1
    assert req.waypoints[0].weight_kg == 8.5


def test_optimize_no_capacity_no_weight_passes_none(client, db_session, monkeypatch):
    """
    Vehículo sin capacity_kg y pedido sin peso → ambos campos son None en el request.
    """
    tenant = _demo_tenant(db_session)
    route = _build_route_with_vehicle_and_order(
        db_session, tenant.id,
        vehicle_capacity_kg=None,
        order_weight_kg=None,
    )
    token = _logistics_token(client)

    captured_requests: list[OptimizationRequest] = []

    from app.optimization.mock_provider import MockRouteOptimizationProvider as _MockProvider

    class _SpyProvider(_MockProvider):
        def optimize(self, request: OptimizationRequest):  # type: ignore[override]
            captured_requests.append(request)
            return super().optimize(request)

    import app.routers.routing as routing_module
    monkeypatch.setattr(routing_module, "_get_optimization_provider", lambda: _SpyProvider())

    res = client.post(f"/routes/{route.id}/optimize", headers=auth_headers(token))
    assert res.status_code == 200, res.text
    assert len(captured_requests) == 1

    req = captured_requests[0]
    assert req.vehicle_capacity_kg is None
    assert req.waypoints[0].weight_kg is None
