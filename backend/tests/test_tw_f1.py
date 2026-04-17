"""
Bloque F1 — TW-001: Time windows por cliente en optimizer

Cubre:
  - _build_time_windows: sin ventana → None
  - _build_time_windows: ventana válida → timeWindows con RFC3339 correcto
  - _build_time_windows: window_end <= window_start → None (ventana inválida)
  - _build_time_windows: ventana fuera del rango global → recortada/None
  - optimize_route con mock provider: waypoint sin perfil → sin timeWindows
  - optimize_route con mock provider: waypoint con perfil → payload incluye timeWindows
  - OptimizationWaypoint acepta window_start/window_end opcionales
"""

import uuid
from datetime import UTC, date, datetime, time, timedelta

import pytest
from sqlalchemy import select

from app.models import (
    Customer,
    CustomerOperationalProfile,
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
from app.optimization.google_provider import GoogleRouteOptimizationProvider
from app.optimization.protocol import OptimizationRequest, OptimizationWaypoint
from app.security import hash_password
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


def _make_provider() -> GoogleRouteOptimizationProvider:
    """Instancia del provider (no hace llamadas HTTP — solo usamos _build_time_windows)."""
    return GoogleRouteOptimizationProvider(project_id="test-project")


def _global_window() -> tuple[datetime, datetime]:
    start = datetime(2026, 4, 17, 7, 0, 0, tzinfo=UTC)
    end = datetime(2026, 4, 17, 19, 0, 0, tzinfo=UTC)
    return start, end


def _waypoint_with_window(ws: time | None, we: time | None) -> OptimizationWaypoint:
    return OptimizationWaypoint(
        order_id=uuid.uuid4(),
        lat=39.5696,
        lng=2.6502,
        service_minutes=10,
        window_start=ws,
        window_end=we,
    )


# ── Unit: _build_time_windows ─────────────────────────────────────────────────


def test_build_time_windows_none_when_no_window():
    provider = _make_provider()
    wp = _waypoint_with_window(None, None)
    gs, ge = _global_window()
    result = provider._build_time_windows(wp, date(2026, 4, 17), gs, ge)
    assert result is None


def test_build_time_windows_none_when_only_start():
    provider = _make_provider()
    wp = _waypoint_with_window(time(9, 0), None)
    gs, ge = _global_window()
    result = provider._build_time_windows(wp, date(2026, 4, 17), gs, ge)
    assert result is None


def test_build_time_windows_valid_window():
    provider = _make_provider()
    wp = _waypoint_with_window(time(9, 0), time(12, 0))
    gs, ge = _global_window()
    result = provider._build_time_windows(wp, date(2026, 4, 17), gs, ge)
    assert result is not None
    assert len(result) == 1
    assert result[0]["startTime"] == "2026-04-17T09:00:00Z"
    assert result[0]["endTime"] == "2026-04-17T12:00:00Z"


def test_build_time_windows_invalid_end_before_start_returns_none():
    """window_end <= window_start → inválida → None."""
    provider = _make_provider()
    wp = _waypoint_with_window(time(14, 0), time(9, 0))
    gs, ge = _global_window()
    result = provider._build_time_windows(wp, date(2026, 4, 17), gs, ge)
    assert result is None


def test_build_time_windows_equal_start_end_returns_none():
    provider = _make_provider()
    wp = _waypoint_with_window(time(10, 0), time(10, 0))
    gs, ge = _global_window()
    result = provider._build_time_windows(wp, date(2026, 4, 17), gs, ge)
    assert result is None


def test_build_time_windows_clipped_by_global_end():
    """Ventana que supera globalEnd → recortada al límite global."""
    provider = _make_provider()
    # global_end = 19:00; ventana = 18:00-21:00 → recortada a 18:00-19:00
    wp = _waypoint_with_window(time(18, 0), time(21, 0))
    gs, ge = _global_window()
    result = provider._build_time_windows(wp, date(2026, 4, 17), gs, ge)
    assert result is not None
    assert result[0]["endTime"] == "2026-04-17T19:00:00Z"


def test_build_time_windows_entirely_outside_global_returns_none():
    """Ventana completamente antes del inicio global → None tras recorte."""
    provider = _make_provider()
    # global_start = 07:00; ventana = 04:00-06:00 → recortada → vacía
    wp = _waypoint_with_window(time(4, 0), time(6, 0))
    gs, ge = _global_window()
    result = provider._build_time_windows(wp, date(2026, 4, 17), gs, ge)
    assert result is None


def test_build_time_windows_no_service_date_uses_global_start_date():
    """Sin service_date → usa la fecha de global_start."""
    provider = _make_provider()
    wp = _waypoint_with_window(time(9, 0), time(12, 0))
    gs, ge = _global_window()
    result = provider._build_time_windows(wp, None, gs, ge)
    assert result is not None
    assert "2026-04-17" in result[0]["startTime"]


# ── Unit: OptimizationWaypoint con campos opcionales ─────────────────────────


def test_waypoint_defaults_have_no_window():
    wp = OptimizationWaypoint(order_id=uuid.uuid4(), lat=0.0, lng=0.0)
    assert wp.window_start is None
    assert wp.window_end is None


def test_waypoint_accepts_window_fields():
    wp = OptimizationWaypoint(
        order_id=uuid.uuid4(),
        lat=39.5696,
        lng=2.6502,
        window_start=time(8, 30),
        window_end=time(11, 0),
    )
    assert wp.window_start == time(8, 30)
    assert wp.window_end == time(11, 0)


# ── Integration: optimize_route con mock provider ─────────────────────────────


def _build_draft_route_with_customer(
    db_session,
    tenant_id: uuid.UUID,
    *,
    customer_lat: float = 39.5696,
    customer_lng: float = 2.6502,
    window_start: time | None = None,
    window_end: time | None = None,
) -> tuple[Route, Customer]:
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
        name=f"TW Customer {uuid.uuid4().hex[:6]}",
        zone_id=zone.id,
        lat=customer_lat,
        lng=customer_lng,
        created_at=now,
    )
    db_session.add(customer)
    db_session.flush()

    if window_start is not None and window_end is not None:
        profile = CustomerOperationalProfile(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            customer_id=customer.id,
            window_start=window_start,
            window_end=window_end,
            created_at=now,
            updated_at=now,
        )
        db_session.add(profile)
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
        external_ref=f"TW-F1-{uuid.uuid4()}",
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
    return route, customer


def test_optimize_without_profile_succeeds(client, db_session, monkeypatch):
    """Cliente sin perfil operacional → optimize llama spy sin timeWindows → 200."""
    tenant = _demo_tenant(db_session)
    route, _ = _build_draft_route_with_customer(db_session, tenant.id)
    token = _logistics_token(client)

    captured_waypoints: list[OptimizationWaypoint] = []

    from app.optimization.mock_provider import MockRouteOptimizationProvider as _MockProvider

    class _SpyProvider(_MockProvider):
        def optimize(self, request: OptimizationRequest):  # type: ignore[override]
            captured_waypoints.extend(request.waypoints)
            return super().optimize(request)

    spy_instance = _SpyProvider()

    import app.routers.routing as routing_module
    monkeypatch.setattr(routing_module, "_get_optimization_provider", lambda: spy_instance)

    res = client.post(f"/routes/{route.id}/optimize", headers=auth_headers(token))
    assert res.status_code == 200, res.text
    assert len(captured_waypoints) == 1
    assert captured_waypoints[0].window_start is None
    assert captured_waypoints[0].window_end is None


def test_optimize_with_profile_passes_window_to_provider(client, db_session, monkeypatch):
    """Cliente con perfil 09:00-12:00 → waypoint lleva window_start/end correctos."""
    tenant = _demo_tenant(db_session)
    route, _ = _build_draft_route_with_customer(
        db_session, tenant.id,
        window_start=time(9, 0),
        window_end=time(12, 0),
    )
    token = _logistics_token(client)

    captured_waypoints: list[OptimizationWaypoint] = []

    from app.optimization.mock_provider import MockRouteOptimizationProvider as _MockProvider

    class _SpyProvider(_MockProvider):
        def optimize(self, request: OptimizationRequest):  # type: ignore[override]
            captured_waypoints.extend(request.waypoints)
            return super().optimize(request)

    spy_instance = _SpyProvider()

    import app.routers.routing as routing_module
    monkeypatch.setattr(routing_module, "_get_optimization_provider", lambda: spy_instance)

    res = client.post(f"/routes/{route.id}/optimize", headers=auth_headers(token))
    assert res.status_code == 200, res.text
    assert len(captured_waypoints) == 1
    wp = captured_waypoints[0]
    assert wp.window_start == time(9, 0)
    assert wp.window_end == time(12, 0)


def test_optimize_with_profile_google_payload_includes_time_windows():
    """
    _build_body incluye timeWindows en el delivery cuando el waypoint tiene ventana.
    Test puro — no hace llamadas HTTP.
    Usa fecha futura (2030) para que global_start = service_start (07:00) sin
    el floor de now+5min que aplica _build_global_window.
    """
    provider = _make_provider()
    future_date = date(2030, 6, 15)
    request = OptimizationRequest(
        route_id=uuid.uuid4(),
        depot_lat=39.648,
        depot_lng=2.787,
        service_date=future_date,
        waypoints=[
            OptimizationWaypoint(
                order_id=uuid.uuid4(),
                lat=39.5696,
                lng=2.6502,
                service_minutes=15,
                window_start=time(9, 0),
                window_end=time(12, 0),
            )
        ],
    )
    body = provider._build_body(request)
    shipment = body["model"]["shipments"][0]
    delivery = shipment["deliveries"][0]
    assert "timeWindows" in delivery
    assert delivery["timeWindows"][0]["startTime"] == "2030-06-15T09:00:00Z"
    assert delivery["timeWindows"][0]["endTime"] == "2030-06-15T12:00:00Z"


def test_optimize_no_profile_google_payload_no_time_windows():
    """Sin ventana → el delivery no incluye timeWindows."""
    provider = _make_provider()
    request = OptimizationRequest(
        route_id=uuid.uuid4(),
        depot_lat=39.648,
        depot_lng=2.787,
        service_date=date(2030, 6, 15),
        waypoints=[
            OptimizationWaypoint(
                order_id=uuid.uuid4(),
                lat=39.5696,
                lng=2.6502,
                service_minutes=10,
            )
        ],
    )
    body = provider._build_body(request)
    shipment = body["model"]["shipments"][0]
    delivery = shipment["deliveries"][0]
    assert "timeWindows" not in delivery
