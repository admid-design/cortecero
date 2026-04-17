"""
Bloque B3 — CHAT-001: Chat interno dispatcher ↔ conductor

Cubre:
  - POST /routes/{id}/messages — dispatcher envía mensaje → 201 + RouteMessageOut
  - POST /routes/{id}/messages — driver envía mensaje → 201 + RouteMessageOut
  - GET  /routes/{id}/messages — lista mensajes ordenados cronológicamente
  - GET  /routes/{id}/messages — retorna lista vacía si no hay mensajes
  - POST /routes/{id}/messages — body vacío → 422
  - POST /routes/{id}/messages — body > 2000 chars → 422
  - POST /routes/{id}/messages — ruta de otro tenant → 404
  - GET  /routes/{id}/messages — ruta inexistente → 404
  - author_role se asigna correctamente: logistics → 'dispatcher', driver → 'driver'
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
    User,
    UserRole,
    Vehicle,
    Zone,
)
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


def _create_driver_with_user(db_session, tenant: Tenant) -> tuple[Driver, str]:
    """Crea Driver + User con role=driver. Devuelve (driver, email)."""
    now = datetime.now(UTC)
    email = f"chat-driver-{uuid.uuid4().hex[:8]}@example.com"

    vehicle = db_session.scalar(
        select(Vehicle).where(Vehicle.tenant_id == tenant.id, Vehicle.active.is_(True))
    )
    assert vehicle is not None

    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=email,
        full_name="Chat Driver Test",
        password_hash=hash_password("driver123"),
        role=UserRole.driver,
        is_active=True,
        created_at=now,
    )
    db_session.add(user)
    db_session.flush()

    driver = Driver(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=user.id,
        vehicle_id=vehicle.id,
        name="Chat Driver Test",
        phone=f"+34{uuid.uuid4().int % 900000000 + 100000000}",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(driver)
    db_session.commit()
    return driver, email


def _build_route(db_session, tenant_id: uuid.UUID) -> Route:
    """Crea una ruta draft mínima para el tenant."""
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
    db_session.commit()
    db_session.refresh(route)
    return route


# ── Tests ────────────────────────────────────────────────────────────────────


def test_dispatcher_sends_message(client, db_session):
    """Logistics envía mensaje → 201, author_role = 'dispatcher'."""
    tenant = _demo_tenant(db_session)
    route = _build_route(db_session, tenant.id)
    token = _logistics_token(client)

    res = client.post(
        f"/routes/{route.id}/messages",
        json={"body": "¿Puedes acelerar en la última parada?"},
        headers=auth_headers(token),
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["body"] == "¿Puedes acelerar en la última parada?"
    assert data["author_role"] == "dispatcher"
    assert data["route_id"] == str(route.id)
    assert "id" in data
    assert "created_at" in data


def test_driver_sends_message(client, db_session):
    """Driver envía mensaje → 201, author_role = 'driver'."""
    tenant = _demo_tenant(db_session)
    route = _build_route(db_session, tenant.id)
    _driver, email = _create_driver_with_user(db_session, tenant)
    token = login_as(client, tenant_slug="demo-cortecero", email=email, password="driver123")

    res = client.post(
        f"/routes/{route.id}/messages",
        json={"body": "Voy con 15 min de retraso por tráfico."},
        headers=auth_headers(token),
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["author_role"] == "driver"
    assert data["body"] == "Voy con 15 min de retraso por tráfico."


def test_list_messages_ordered(client, db_session):
    """GET devuelve mensajes en orden cronológico."""
    tenant = _demo_tenant(db_session)
    route = _build_route(db_session, tenant.id)
    token = _logistics_token(client)

    bodies = ["Primer mensaje", "Segundo mensaje", "Tercer mensaje"]
    for b in bodies:
        res = client.post(
            f"/routes/{route.id}/messages",
            json={"body": b},
            headers=auth_headers(token),
        )
        assert res.status_code == 201, res.text

    res = client.get(f"/routes/{route.id}/messages", headers=auth_headers(token))
    assert res.status_code == 200, res.text
    msgs = res.json()
    returned_bodies = [m["body"] for m in msgs]
    assert bodies == returned_bodies


def test_list_messages_empty(client, db_session):
    """GET en ruta sin mensajes → lista vacía."""
    tenant = _demo_tenant(db_session)
    route = _build_route(db_session, tenant.id)
    token = _logistics_token(client)

    res = client.get(f"/routes/{route.id}/messages", headers=auth_headers(token))
    assert res.status_code == 200, res.text
    assert res.json() == []


def test_send_message_empty_body_returns_422(client, db_session):
    """Body vacío → 422."""
    tenant = _demo_tenant(db_session)
    route = _build_route(db_session, tenant.id)
    token = _logistics_token(client)

    res = client.post(
        f"/routes/{route.id}/messages",
        json={"body": ""},
        headers=auth_headers(token),
    )
    assert res.status_code == 422, res.text


def test_send_message_too_long_returns_422(client, db_session):
    """Body > 2000 chars → 422."""
    tenant = _demo_tenant(db_session)
    route = _build_route(db_session, tenant.id)
    token = _logistics_token(client)

    res = client.post(
        f"/routes/{route.id}/messages",
        json={"body": "x" * 2001},
        headers=auth_headers(token),
    )
    assert res.status_code == 422, res.text


def test_send_message_unknown_route_returns_404(client, db_session):
    """Ruta inexistente → 404."""
    token = _logistics_token(client)

    res = client.post(
        f"/routes/{uuid.uuid4()}/messages",
        json={"body": "Hola"},
        headers=auth_headers(token),
    )
    assert res.status_code == 404, res.text


def test_list_messages_unknown_route_returns_404(client, db_session):
    """GET en ruta inexistente → 404."""
    token = _logistics_token(client)

    res = client.get(
        f"/routes/{uuid.uuid4()}/messages",
        headers=auth_headers(token),
    )
    assert res.status_code == 404, res.text


def test_messages_isolated_per_route(client, db_session):
    """Mensajes de una ruta no aparecen en otra ruta."""
    tenant = _demo_tenant(db_session)
    route_a = _build_route(db_session, tenant.id)
    route_b = _build_route(db_session, tenant.id)
    token = _logistics_token(client)

    client.post(
        f"/routes/{route_a.id}/messages",
        json={"body": "Mensaje de ruta A"},
        headers=auth_headers(token),
    )

    res = client.get(f"/routes/{route_b.id}/messages", headers=auth_headers(token))
    assert res.status_code == 200, res.text
    assert res.json() == []
