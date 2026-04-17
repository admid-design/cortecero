"""
Bloque B2 — ETA-001: Recálculo de ETA y alertas de retraso

Cubre:
  - Calculator: haversine_km con distancias conocidas
  - Calculator: calculate_eta produce datetime futuro coherente
  - Calculator: delay_minutes positivo/negativo/cero
  - POST /routes/{id}/recalculate-eta → 404 si ruta no existe
  - POST /routes/{id}/recalculate-eta → 409 si ruta en estado draft
  - POST /routes/{id}/recalculate-eta → 404 si no hay posición GPS del conductor
  - POST /routes/{id}/recalculate-eta → 200 con resultados correctos
  - POST /routes/{id}/recalculate-eta → crea delay_alert si retraso ≥ 15 min
  - GET  /routes/{id}/delay-alerts    → lista alertas correctamente
  - GET  /routes/{id}/delay-alerts    → 404 si ruta no existe
"""

import math
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.eta.calculator import calculate_eta, delay_minutes, haversine_km
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
from app.security import create_access_token, hash_password
from tests.helpers import auth_headers, login_as


# ── Helpers ───────────────────────────────────────────────────────────────────


def _demo_tenant(db_session) -> Tenant:
    t = db_session.scalar(select(Tenant).where(Tenant.slug == "demo-cortecero"))
    assert t is not None, "Tenant demo-cortecero no encontrado"
    return t


def _logistics_token(client) -> str:
    return login_as(
        client,
        tenant_slug="demo-cortecero",
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )


def _build_route_with_geo_stop(
    db_session,
    tenant_id: uuid.UUID,
    *,
    route_status: RouteStatus = RouteStatus.in_progress,
    stop_status: RouteStopStatus = RouteStopStatus.pending,
    customer_lat: float = 39.5696,
    customer_lng: float = 2.6502,
    original_eta: datetime | None = None,
) -> tuple[Route, RouteStop, Customer]:
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

    # Customer con coordenadas explícitas
    customer = Customer(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=f"Test ETA Customer {uuid.uuid4().hex[:6]}",
        zone_id=zone.id,
        lat=customer_lat,
        lng=customer_lng,
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

    dispatched_at = now if route_status not in (RouteStatus.draft, RouteStatus.planned) else None
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
        dispatched_at=dispatched_at,
        completed_at=None,
    )
    db_session.add(route)
    db_session.flush()

    order = Order(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        customer_id=customer.id,
        zone_id=zone.id,
        external_ref=f"ETA-B2-{uuid.uuid4()}",
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
        estimated_arrival_at=original_eta,
        estimated_service_minutes=10,
        status=stop_status,
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
    db_session.refresh(stop)
    return route, stop, customer


def _publish_driver_position(
    db_session,
    tenant_id: uuid.UUID,
    driver_id: uuid.UUID,
    route_id: uuid.UUID,
    lat: float,
    lng: float,
) -> DriverPosition:
    now = datetime.now(UTC)
    pos = DriverPosition(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        driver_id=driver_id,
        route_id=route_id,
        lat=lat,
        lng=lng,
        accuracy_m=None,
        speed_kmh=None,
        heading=None,
        recorded_at=now,
        created_at=now,
    )
    db_session.add(pos)
    db_session.commit()
    return pos


# ── Unit tests: calculator ────────────────────────────────────────────────────


def test_haversine_palma_santa_maria():
    """Palma → Santa Maria del Camí ≈ 17 km."""
    palma_lat, palma_lng = 39.5696, 2.6502
    santa_maria_lat, santa_maria_lng = 39.648, 2.787
    d = haversine_km(palma_lat, palma_lng, santa_maria_lat, santa_maria_lng)
    assert 14.0 < d < 20.0, f"Distancia inesperada: {d:.2f} km"


def test_haversine_same_point_is_zero():
    lat, lng = 39.5696, 2.6502
    assert haversine_km(lat, lng, lat, lng) == pytest.approx(0.0, abs=1e-6)


def test_calculate_eta_returns_future_datetime():
    now = datetime.now(UTC)
    eta = calculate_eta(
        current_lat=39.5696, current_lng=2.6502,
        stop_lat=39.648, stop_lng=2.787,
        reference_time=now,
    )
    assert eta > now


def test_calculate_eta_plausible_travel_time():
    """~17 km a 40 km/h ≈ 25 min de viaje."""
    now = datetime.now(UTC)
    eta = calculate_eta(
        current_lat=39.5696, current_lng=2.6502,
        stop_lat=39.648, stop_lng=2.787,
        average_speed_kmh=40.0,
        reference_time=now,
    )
    minutes = (eta - now).total_seconds() / 60
    assert 20 < minutes < 35, f"ETA fuera de rango plausible: {minutes:.1f} min"


def test_delay_minutes_positive():
    original = datetime(2026, 4, 17, 10, 0, 0, tzinfo=UTC)
    recalculated = datetime(2026, 4, 17, 10, 20, 0, tzinfo=UTC)
    assert delay_minutes(original, recalculated) == pytest.approx(20.0)


def test_delay_minutes_negative_is_advance():
    original = datetime(2026, 4, 17, 10, 30, 0, tzinfo=UTC)
    recalculated = datetime(2026, 4, 17, 10, 15, 0, tzinfo=UTC)
    assert delay_minutes(original, recalculated) == pytest.approx(-15.0)


def test_delay_minutes_zero():
    t = datetime(2026, 4, 17, 10, 0, 0, tzinfo=UTC)
    assert delay_minutes(t, t) == pytest.approx(0.0)


# ── HTTP tests ────────────────────────────────────────────────────────────────


def test_recalculate_eta_route_not_found(client, db_session):
    token = _logistics_token(client)
    fake_id = uuid.uuid4()
    res = client.post(f"/routes/{fake_id}/recalculate-eta", headers=auth_headers(token))
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "ROUTE_NOT_FOUND"


def test_recalculate_eta_draft_route_returns_409(client, db_session):
    tenant = _demo_tenant(db_session)
    route, _, _ = _build_route_with_geo_stop(
        db_session, tenant.id, route_status=RouteStatus.draft
    )
    token = _logistics_token(client)
    res = client.post(f"/routes/{route.id}/recalculate-eta", headers=auth_headers(token))
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "ROUTE_NOT_ACTIVE"


def test_recalculate_eta_no_driver_position_returns_404(client, db_session):
    tenant = _demo_tenant(db_session)
    route, _, _ = _build_route_with_geo_stop(
        db_session, tenant.id, route_status=RouteStatus.in_progress
    )
    token = _logistics_token(client)
    res = client.post(f"/routes/{route.id}/recalculate-eta", headers=auth_headers(token))
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "DRIVER_POSITION_NOT_FOUND"


def test_recalculate_eta_returns_results(client, db_session):
    """Con posición GPS publicada → recalcula ETA y devuelve resultados."""
    tenant = _demo_tenant(db_session)
    route, stop, customer = _build_route_with_geo_stop(
        db_session, tenant.id,
        route_status=RouteStatus.in_progress,
        customer_lat=39.648,
        customer_lng=2.787,
    )
    driver = db_session.scalar(
        select(Driver).where(Driver.tenant_id == tenant.id, Driver.is_active.is_(True))
    )
    # Conductor en Palma (~17 km del cliente)
    _publish_driver_position(
        db_session, tenant.id, driver.id, route.id,
        lat=39.5696, lng=2.6502,
    )

    token = _logistics_token(client)
    res = client.post(f"/routes/{route.id}/recalculate-eta", headers=auth_headers(token))
    assert res.status_code == 200, res.text

    body = res.json()
    assert body["route_id"] == str(route.id)
    assert body["stops_updated"] == 1
    assert len(body["results"]) == 1
    result = body["results"][0]
    assert result["stop_id"] == str(stop.id)
    assert result["recalculated_eta"] is not None
    # Sin ETA original → no hay delay_alert
    assert result["delay_alert"] is False
    assert result["original_eta"] is None

    # Verificar que se guardó en DB
    db_session.refresh(stop)
    assert stop.recalculated_eta_at is not None


def test_recalculate_eta_creates_delay_alert_when_overdue(client, db_session):
    """ETA original en 5 min, conductor lejos → retraso ≥ 15 min → delay_alert."""
    tenant = _demo_tenant(db_session)
    now = datetime.now(UTC)
    original_eta = now + timedelta(minutes=5)  # ETA original: en 5 min

    route, stop, customer = _build_route_with_geo_stop(
        db_session, tenant.id,
        route_status=RouteStatus.in_progress,
        customer_lat=39.648,
        customer_lng=2.787,
        original_eta=original_eta,
    )
    driver = db_session.scalar(
        select(Driver).where(Driver.tenant_id == tenant.id, Driver.is_active.is_(True))
    )
    # Conductor en Palma: ~25 min de viaje → retraso ≈ 20 min sobre original de 5 min
    _publish_driver_position(
        db_session, tenant.id, driver.id, route.id,
        lat=39.5696, lng=2.6502,
    )

    token = _logistics_token(client)
    res = client.post(f"/routes/{route.id}/recalculate-eta", headers=auth_headers(token))
    assert res.status_code == 200, res.text

    body = res.json()
    assert body["delay_alerts_created"] == 1
    result = body["results"][0]
    assert result["delay_alert"] is True
    assert result["delay_minutes"] >= 15.0

    # Verificar evento en DB
    event = db_session.scalar(
        select(RouteEvent).where(
            RouteEvent.route_id == route.id,
            RouteEvent.event_type == RouteEventType.delay_alert,
        )
    )
    assert event is not None
    assert event.metadata_json["delay_minutes"] >= 15.0


def test_get_delay_alerts_empty(client, db_session):
    tenant = _demo_tenant(db_session)
    route, _, _ = _build_route_with_geo_stop(
        db_session, tenant.id, route_status=RouteStatus.in_progress
    )
    token = _logistics_token(client)
    res = client.get(f"/routes/{route.id}/delay-alerts", headers=auth_headers(token))
    assert res.status_code == 200
    assert res.json() == []


def test_get_delay_alerts_returns_created_alerts(client, db_session):
    """Tras recalculate-eta con retraso → delay-alerts devuelve el evento."""
    tenant = _demo_tenant(db_session)
    now = datetime.now(UTC)
    original_eta = now + timedelta(minutes=5)

    route, _, _ = _build_route_with_geo_stop(
        db_session, tenant.id,
        route_status=RouteStatus.in_progress,
        customer_lat=39.648,
        customer_lng=2.787,
        original_eta=original_eta,
    )
    driver = db_session.scalar(
        select(Driver).where(Driver.tenant_id == tenant.id, Driver.is_active.is_(True))
    )
    _publish_driver_position(
        db_session, tenant.id, driver.id, route.id,
        lat=39.5696, lng=2.6502,
    )

    token = _logistics_token(client)
    client.post(f"/routes/{route.id}/recalculate-eta", headers=auth_headers(token))

    res = client.get(f"/routes/{route.id}/delay-alerts", headers=auth_headers(token))
    assert res.status_code == 200
    alerts = res.json()
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["route_id"] == str(route.id)
    assert alert["delay_minutes"] >= 15.0
    assert alert["recalculated_eta"] is not None
    assert alert["original_eta"] is not None


def test_get_delay_alerts_route_not_found(client, db_session):
    token = _logistics_token(client)
    fake_id = uuid.uuid4()
    res = client.get(f"/routes/{fake_id}/delay-alerts", headers=auth_headers(token))
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "ROUTE_NOT_FOUND"
