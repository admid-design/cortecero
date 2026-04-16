"""
Bloque B1 — REALTIME-001: SSE transport layer

Cubre:
  - RouteEventBus: publish + subscribe emite el frame correcto
  - RouteEventBus: tenant isolation (evento de tenant A no llega a suscriptor de tenant B)
  - RouteEventBus: active_subscriber_count decrementa tras disconnect
  - GET /routes/{id}/stream  token inválido → 401
  - GET /routes/{id}/stream  ruta de otro tenant → 404
  - stop_arrive emite stop_status_changed via event_bus
  - update_driver_location emite driver_position_updated via event_bus

Nota de autenticación SSE (B1):
  El endpoint acepta JWT en query param ?token=<jwt>.
  Esto es SOLO válido para smoke/local/pilot de B1.
  La autenticación definitiva requiere decisión explícita en bloque posterior.
"""

import asyncio
import json
import uuid
from datetime import UTC, date, datetime, time

import pytest
from sqlalchemy import select

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
from app.realtime import RouteEventBus
from app.security import create_access_token, hash_password
from tests.helpers import auth_headers, login_as


# ── Helpers ───────────────────────────────────────────────────────────────────


def _demo_tenant(db_session) -> Tenant:
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


def _build_route_with_stop(
    db_session,
    tenant_id: uuid.UUID,
    *,
    route_status: RouteStatus = RouteStatus.dispatched,
    stop_status: RouteStopStatus = RouteStopStatus.pending,
) -> tuple[Route, RouteStop]:
    now = datetime.now(UTC)
    svc_date = date.today()

    vehicle = db_session.scalar(
        select(Vehicle).where(Vehicle.tenant_id == tenant_id, Vehicle.active.is_(True))
    )
    assert vehicle is not None, "No hay vehículos activos en seed"

    driver = db_session.scalar(
        select(Driver).where(Driver.tenant_id == tenant_id, Driver.is_active.is_(True))
    )
    assert driver is not None, "No hay choferes activos en seed"

    zone = db_session.scalar(select(Zone).where(Zone.tenant_id == tenant_id))
    assert zone is not None

    customer = db_session.scalar(select(Customer).where(Customer.tenant_id == tenant_id))
    assert customer is not None

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
        external_ref=f"RT-B1-{uuid.uuid4()}",
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
        status=stop_status,
        arrived_at=now if stop_status in (RouteStopStatus.arrived, RouteStopStatus.completed, RouteStopStatus.failed) else None,
        completed_at=now if stop_status == RouteStopStatus.completed else None,
        failed_at=now if stop_status == RouteStopStatus.failed else None,
        failure_reason="setup" if stop_status == RouteStopStatus.failed else None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(stop)
    db_session.commit()
    db_session.refresh(route)
    db_session.refresh(stop)
    return route, stop


def _make_logistics_user(db_session, tenant: Tenant) -> User:
    """Crea un usuario logistics adicional para el tenant dado."""
    now = datetime.now(UTC)
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=f"b1-log-{uuid.uuid4().hex[:6]}@test.cortecero.app",
        full_name="B1 Logistics",
        password_hash=hash_password("pass123"),
        role=UserRole.logistics,
        is_active=True,
        created_at=now,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ── Unit tests: RouteEventBus ─────────────────────────────────────────────────


def test_event_bus_publish_subscribe_emits_frame():
    """publish() → subscribe() recibe el frame SSE correctamente."""
    bus = RouteEventBus()
    tenant_id = str(uuid.uuid4())
    route_id = str(uuid.uuid4())

    payload = {"route_id": route_id, "stop_id": str(uuid.uuid4()), "status": "arrived"}

    async def _run():
        frames = []

        async def _consumer():
            async for frame in bus.subscribe(tenant_id, route_id):
                frames.append(frame)
                break  # solo queremos el primer frame

        consumer_task = asyncio.create_task(_consumer())
        # Dar tiempo al consumer de registrarse
        await asyncio.sleep(0)
        bus.publish(tenant_id, route_id, "stop_status_changed", payload)
        await consumer_task
        return frames

    frames = asyncio.run(_run())
    assert len(frames) == 1
    frame = frames[0]
    assert "event: stop_status_changed" in frame
    body = json.loads(frame.split("data: ")[1].split("\n")[0])
    assert body["status"] == "arrived"
    assert body["route_id"] == route_id


def test_event_bus_tenant_isolation():
    """Evento de tenant_A no llega a suscriptor de tenant_B (mismo route_id)."""
    bus = RouteEventBus()
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())
    route_id = str(uuid.uuid4())  # mismo route_id, distintos tenants

    async def _run():
        frames_b = []
        received = asyncio.Event()

        async def _consumer_b():
            async for frame in bus.subscribe(tenant_b, route_id):
                frames_b.append(frame)
                received.set()
                break

        consumer_task = asyncio.create_task(_consumer_b())
        await asyncio.sleep(0)

        # Publicar para tenant_A — tenant_B no debe recibirlo
        bus.publish(tenant_a, route_id, "stop_status_changed", {"status": "arrived"})

        # Esperar brevemente y cancelar el consumer sin que haya recibido nada
        await asyncio.sleep(0.05)
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
        return frames_b

    frames_b = asyncio.run(_run())
    assert frames_b == [], "tenant_B recibió evento de tenant_A — aislamiento roto"


def test_event_bus_subscriber_count_decrements_on_disconnect():
    """active_subscriber_count decrementa cuando el suscriptor se desconecta."""
    bus = RouteEventBus()
    tenant_id = str(uuid.uuid4())
    route_id = str(uuid.uuid4())

    async def _run():
        assert bus.active_subscriber_count(tenant_id, route_id) == 0

        async def _consumer():
            async for _ in bus.subscribe(tenant_id, route_id):
                break  # salir inmediatamente tras el primer evento

        consumer_task = asyncio.create_task(_consumer())
        await asyncio.sleep(0)
        assert bus.active_subscriber_count(tenant_id, route_id) == 1

        # Enviar evento para que el consumer salga
        bus.publish(tenant_id, route_id, "ping", {})
        await consumer_task
        # El aclose() del generador async se procesa en el siguiente tick del event loop
        await asyncio.sleep(0)

        assert bus.active_subscriber_count(tenant_id, route_id) == 0

    asyncio.run(_run())


# ── HTTP tests: GET /routes/{id}/stream (auth) ───────────────────────────────


def test_sse_stream_invalid_token_returns_401(client, db_session):
    """Token inválido en query param → 401 INVALID_TOKEN."""
    fake_route_id = str(uuid.uuid4())
    res = client.get(f"/routes/{fake_route_id}/stream?token=not-a-valid-jwt")
    assert res.status_code == 401
    assert res.json()["detail"]["code"] == "INVALID_TOKEN"


def test_sse_stream_route_not_in_tenant_returns_404(client, db_session):
    """Ruta existente en otro tenant → 404 para el usuario del tenant correcto."""
    demo_tenant = _demo_tenant(db_session)

    # Crear un segundo tenant con su ruta
    now = datetime.now(UTC)
    other_tenant = Tenant(
        id=uuid.uuid4(),
        name="Other Tenant B1",
        slug=f"other-b1-{uuid.uuid4().hex[:6]}",
        default_cutoff_time=datetime.strptime("17:00", "%H:%M").time(),
        default_timezone="Europe/Madrid",
        created_at=now,
    )
    db_session.add(other_tenant)
    db_session.flush()

    zone = Zone(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        name="Zona B1",
        default_cutoff_time=time(17, 0),
        timezone="Europe/Madrid",
        active=True,
        created_at=now,
    )
    db_session.add(zone)
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

    other_route = Route(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        plan_id=plan.id,
        vehicle_id=uuid.uuid4(),  # Route.vehicle_id no tiene FK constraint
        driver_id=None,
        service_date=date.today(),
        status=RouteStatus.draft,
        version=1,
        optimization_request_id=None,
        optimization_response_json=None,
        created_at=now,
        updated_at=now,
        dispatched_at=None,
        completed_at=None,
    )
    db_session.add(other_route)
    db_session.commit()

    # Crear token válido para un usuario del tenant demo (no del other_tenant)
    log_user = _make_logistics_user(db_session, demo_tenant)
    token = create_access_token(
        subject=str(log_user.id),
        tenant_id=str(demo_tenant.id),
        role="logistics",
    )

    # El usuario del demo_tenant intenta suscribirse a la ruta del other_tenant → 404
    res = client.get(f"/routes/{other_route.id}/stream?token={token}")
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "ROUTE_NOT_FOUND"


# ── Integración: publish hooks ────────────────────────────────────────────────


def test_stop_arrive_publishes_stop_status_changed(client, db_session, monkeypatch):
    """
    POST /stops/{id}/arrive → event_bus.publish se llama con
    event_type='stop_status_changed' y status='arrived'.
    """
    tenant = _demo_tenant(db_session)
    route, stop = _build_route_with_stop(
        db_session, tenant.id,
        route_status=RouteStatus.dispatched,
        stop_status=RouteStopStatus.pending,
    )
    token = _logistics_token(client)

    published: list[dict] = []

    def _spy_publish(tid, rid, event_type, payload):
        published.append({"tenant_id": tid, "route_id": rid, "event_type": event_type, "payload": payload})

    # Patch el singleton importado en routing.py
    import app.routers.routing as routing_module
    monkeypatch.setattr(routing_module.event_bus, "publish", _spy_publish)

    res = client.post(f"/stops/{stop.id}/arrive", json={}, headers=auth_headers(token))
    assert res.status_code == 200, res.text

    # Debe haber exactamente una publicación de stop_status_changed
    sc_events = [e for e in published if e["event_type"] == "stop_status_changed"]
    assert len(sc_events) == 1, f"Esperado 1 evento stop_status_changed, recibidos: {[e['event_type'] for e in published]}"
    evt = sc_events[0]
    assert evt["payload"]["status"] == "arrived"
    assert evt["payload"]["route_id"] == str(route.id)
    assert evt["payload"]["stop_id"] == str(stop.id)
    assert evt["tenant_id"] == str(tenant.id)


def test_driver_location_publishes_driver_position_updated(client, db_session, monkeypatch):
    """
    POST /driver/location → event_bus.publish se llama con
    event_type='driver_position_updated' con lat/lng correctos.
    """
    tenant = _demo_tenant(db_session)
    now = datetime.now(UTC)

    # Crear conductor asociado a un usuario driver
    vehicle = db_session.scalar(
        select(Vehicle).where(Vehicle.tenant_id == tenant.id, Vehicle.active.is_(True))
    )
    assert vehicle is not None

    driver_email = f"b1-drv-{uuid.uuid4().hex[:6]}@test.cortecero.app"
    driver_user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=driver_email,
        full_name="B1 Driver",
        password_hash=hash_password("driver123"),
        role=UserRole.driver,
        is_active=True,
        created_at=now,
    )
    db_session.add(driver_user)
    db_session.flush()

    driver = Driver(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=driver_user.id,
        vehicle_id=vehicle.id,
        name="B1 Driver",
        phone=f"+34611{uuid.uuid4().int % 1000000:06d}",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(driver)
    db_session.flush()

    # Crear ruta in_progress para ese conductor
    zone = db_session.scalar(select(Zone).where(Zone.tenant_id == tenant.id))
    plan = db_session.scalar(
        select(Plan).where(Plan.tenant_id == tenant.id, Plan.status.in_([PlanStatus.locked, PlanStatus.open]))
    )
    if plan is None:
        plan = Plan(
            id=uuid.uuid4(), tenant_id=tenant.id, service_date=date.today(),
            zone_id=zone.id, status=PlanStatus.locked, version=1,
            created_at=now, updated_at=now,
        )
        db_session.add(plan)
        db_session.flush()

    route = Route(
        id=uuid.uuid4(), tenant_id=tenant.id, plan_id=plan.id,
        vehicle_id=vehicle.id, driver_id=driver.id,
        service_date=date.today(), status=RouteStatus.in_progress,
        version=1, optimization_request_id=None, optimization_response_json=None,
        created_at=now, updated_at=now, dispatched_at=now, completed_at=None,
    )
    db_session.add(route)
    db_session.commit()

    token = login_as(client, tenant_slug="demo-cortecero", email=driver_email, password="driver123")

    published: list[dict] = []

    def _spy_publish(tid, rid, event_type, payload):
        published.append({"tenant_id": tid, "route_id": rid, "event_type": event_type, "payload": payload})

    import app.routers.routing as routing_module
    monkeypatch.setattr(routing_module.event_bus, "publish", _spy_publish)

    res = client.post(
        "/driver/location",
        json={"route_id": str(route.id), "lat": 39.5696, "lng": 2.6502},
        headers=auth_headers(token),
    )
    assert res.status_code == 204, res.text

    pos_events = [e for e in published if e["event_type"] == "driver_position_updated"]
    assert len(pos_events) == 1
    evt = pos_events[0]
    assert evt["payload"]["lat"] == pytest.approx(39.5696, abs=1e-4)
    assert evt["payload"]["lng"] == pytest.approx(2.6502, abs=1e-4)
    assert evt["payload"]["route_id"] == str(route.id)
    assert evt["tenant_id"] == str(tenant.id)
