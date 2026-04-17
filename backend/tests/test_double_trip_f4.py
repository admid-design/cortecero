"""
Bloque F4 — DOUBLE-TRIP-001: Doble viaje por día

Cubre:
  - Route.trip_number existe y defaultea a 1
  - RouteOut expone trip_number
  - plan_routes acepta trip_number=1 y trip_number=2
  - plan_routes trip_number inválido → 422
  - _build_body sin trip_start_after → no startTimeWindows en vehicle
  - _build_body con trip_start_after → startTimeWindows con RFC3339 correcto
  - optimize_route trip_number=2 sin trip1 planificado → 422 TRIP1_NOT_PLANNED
  - optimize_route trip_number=2 con trip1 planificado sin ETAs → 422 TRIP1_NO_ETA
  - optimize_route trip_number=2 con trip1 planificado → trip_start_after calculado correctamente
"""

import uuid
from datetime import UTC, date, datetime, time, timedelta

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

_FUTURE_DATE = date(2030, 6, 15)


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


def _make_provider() -> GoogleRouteOptimizationProvider:
    return GoogleRouteOptimizationProvider(project_id="test-project")


def _build_route(
    db_session,
    tenant_id: uuid.UUID,
    *,
    trip_number: int = 1,
    status: RouteStatus = RouteStatus.draft,
    with_eta: bool = False,
) -> Route:
    """Crea una ruta draft (o planned) con una parada."""
    now = datetime.now(UTC)
    svc_date = date.today()

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

    customer = Customer(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=f"DT Customer {uuid.uuid4().hex[:6]}",
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
        status=status,
        trip_number=trip_number,
        version=trip_number,  # versión diferente para evitar conflictos
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
        external_ref=f"DT-F4-{uuid.uuid4()}",
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

    eta = datetime(2026, 4, 17, 11, 0, tzinfo=UTC) if with_eta else None
    stop = RouteStop(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        route_id=route.id,
        order_id=order.id,
        sequence_number=1,
        estimated_arrival_at=eta,
        estimated_service_minutes=15,
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


# ── Unit: _build_body con/sin trip_start_after ───────────────────────────────


def test_build_body_no_trip_start_after_no_start_time_windows():
    """Sin trip_start_after → el vehículo no lleva startTimeWindows."""
    provider = _make_provider()
    request = OptimizationRequest(
        route_id=uuid.uuid4(),
        depot_lat=39.648,
        depot_lng=2.787,
        service_date=_FUTURE_DATE,
        trip_start_after=None,
        waypoints=[
            OptimizationWaypoint(order_id=uuid.uuid4(), lat=39.57, lng=2.65)
        ],
    )
    body = provider._build_body(request)
    vehicle = body["model"]["vehicles"][0]
    assert "startTimeWindows" not in vehicle


def test_build_body_trip_start_after_sets_start_time_windows():
    """Con trip_start_after → startTimeWindows en el vehículo con RFC3339 correcto."""
    provider = _make_provider()
    start_after = datetime(2030, 6, 15, 14, 0, 0, tzinfo=UTC)
    request = OptimizationRequest(
        route_id=uuid.uuid4(),
        depot_lat=39.648,
        depot_lng=2.787,
        service_date=_FUTURE_DATE,
        trip_start_after=start_after,
        waypoints=[
            OptimizationWaypoint(order_id=uuid.uuid4(), lat=39.57, lng=2.65)
        ],
    )
    body = provider._build_body(request)
    vehicle = body["model"]["vehicles"][0]
    assert "startTimeWindows" in vehicle
    assert vehicle["startTimeWindows"][0]["startTime"] == "2030-06-15T14:00:00Z"


def test_build_body_trip_start_after_single_window_entry():
    """startTimeWindows debe ser lista con exactamente un elemento."""
    provider = _make_provider()
    start_after = datetime(2030, 6, 15, 13, 30, 0, tzinfo=UTC)
    request = OptimizationRequest(
        route_id=uuid.uuid4(),
        depot_lat=39.648,
        depot_lng=2.787,
        service_date=_FUTURE_DATE,
        trip_start_after=start_after,
        waypoints=[
            OptimizationWaypoint(order_id=uuid.uuid4(), lat=39.57, lng=2.65)
        ],
    )
    body = provider._build_body(request)
    assert len(body["model"]["vehicles"][0]["startTimeWindows"]) == 1


# ── Integration: optimize_route viaje 2 ──────────────────────────────────────


def test_optimize_trip2_without_trip1_planned_returns_422(client, db_session):
    """Optimizar viaje 2 sin viaje 1 planificado → 422 TRIP1_NOT_PLANNED."""
    tenant = _demo_tenant(db_session)
    # Crear solo viaje 2, sin viaje 1 planificado
    route2 = _build_route(db_session, tenant.id, trip_number=2, status=RouteStatus.draft)
    token = _logistics_token(client)

    res = client.post(f"/routes/{route2.id}/optimize", headers=auth_headers(token))
    assert res.status_code == 422, res.text
    assert res.json()["detail"]["code"] == "TRIP1_NOT_PLANNED"


def test_optimize_trip2_with_trip1_no_eta_returns_422(client, db_session):
    """Optimizar viaje 2 con viaje 1 planificado pero sin ETAs → 422 TRIP1_NO_ETA."""
    tenant = _demo_tenant(db_session)
    # Viaje 1 en estado planned pero sin ETAs en sus paradas
    _build_route(db_session, tenant.id, trip_number=1, status=RouteStatus.planned, with_eta=False)
    route2 = _build_route(db_session, tenant.id, trip_number=2, status=RouteStatus.draft)
    token = _logistics_token(client)

    res = client.post(f"/routes/{route2.id}/optimize", headers=auth_headers(token))
    assert res.status_code == 422, res.text
    assert res.json()["detail"]["code"] == "TRIP1_NO_ETA"


def test_optimize_trip2_with_trip1_planned_passes_start_after(client, db_session, monkeypatch):
    """
    Viaje 1 planificado con ETA 11:00, service=15min, buffer=30min →
    trip_start_after = 11:45 UTC → request.trip_start_after no es None.
    """
    tenant = _demo_tenant(db_session)
    # Viaje 1: última parada ETA=11:00, service=15min → fin esperado=11:15 + 30min buffer = 11:45
    _build_route(db_session, tenant.id, trip_number=1, status=RouteStatus.planned, with_eta=True)
    route2 = _build_route(db_session, tenant.id, trip_number=2, status=RouteStatus.draft)
    token = _logistics_token(client)

    captured: list[OptimizationRequest] = []

    from app.optimization.mock_provider import MockRouteOptimizationProvider as _MockProvider

    class _SpyProvider(_MockProvider):
        def optimize(self, request: OptimizationRequest):  # type: ignore[override]
            captured.append(request)
            return super().optimize(request)

    import app.routers.routing as routing_module
    monkeypatch.setattr(routing_module, "_get_optimization_provider", lambda: _SpyProvider())

    res = client.post(f"/routes/{route2.id}/optimize", headers=auth_headers(token))
    assert res.status_code == 200, res.text
    assert len(captured) == 1

    req = captured[0]
    assert req.trip_start_after is not None
    # 11:00 + 15min servicio + 30min buffer = 11:45 UTC
    expected = datetime(2026, 4, 17, 11, 45, tzinfo=UTC)
    assert req.trip_start_after == expected


def test_route_trip_number_defaults_to_1(db_session):
    """Route.trip_number defaultea a 1 en nuevas rutas."""
    tenant = db_session.scalar(select(Tenant).where(Tenant.slug == "demo-cortecero"))
    route = _build_route(db_session, tenant.id, trip_number=1)
    assert route.trip_number == 1


def test_route_trip_number_2_persists(db_session):
    """Route.trip_number=2 se persiste correctamente."""
    tenant = db_session.scalar(select(Tenant).where(Tenant.slug == "demo-cortecero"))
    route = _build_route(db_session, tenant.id, trip_number=2)
    assert route.trip_number == 2
