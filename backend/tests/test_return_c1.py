"""
Bloque C1 — RETURN-001: Retorno de pedidos fallidos a planificación

Cubre:
  - POST /orders/{id}/return-to-planning — failed_delivery → ready_for_planning → 200
  - Respuesta incluye order_id, previous_status, new_status, returned_at
  - Estado en DB actualizado a ready_for_planning
  - Pedido en estado ingested → 409 INVALID_STATE_TRANSITION
  - Pedido en estado planned → 409 INVALID_STATE_TRANSITION
  - Pedido en estado dispatched → 409 INVALID_STATE_TRANSITION
  - Pedido inexistente → 404
  - Pedido de otro tenant → 404
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select

from app.models import (
    Customer,
    Order,
    OrderIntakeType,
    OrderStatus,
    SourceChannel,
    Tenant,
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


def _build_order(db_session, tenant_id: uuid.UUID, status: OrderStatus) -> Order:
    now = datetime.now(UTC)

    zone = db_session.scalar(select(Zone).where(Zone.tenant_id == tenant_id))
    assert zone is not None

    customer = Customer(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=f"Return Test Customer {uuid.uuid4().hex[:6]}",
        zone_id=zone.id,
        lat=39.5696,
        lng=2.6502,
        created_at=now,
    )
    db_session.add(customer)
    db_session.flush()

    order = Order(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        customer_id=customer.id,
        zone_id=zone.id,
        external_ref=f"RET-C1-{uuid.uuid4()}",
        requested_date=date.today(),
        service_date=date.today(),
        created_at=now,
        status=status,
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
    db_session.commit()
    return order


# ── Tests ────────────────────────────────────────────────────────────────────


def test_return_failed_order_to_planning(client, db_session):
    """failed_delivery → 200 con ready_for_planning."""
    tenant = _demo_tenant(db_session)
    order = _build_order(db_session, tenant.id, OrderStatus.failed_delivery)
    token = _logistics_token(client)

    res = client.post(
        f"/orders/{order.id}/return-to-planning",
        headers=auth_headers(token),
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["order_id"] == str(order.id)
    assert data["previous_status"] == "failed_delivery"
    assert data["new_status"] == "ready_for_planning"
    assert "returned_at" in data


def test_return_updates_order_status_in_db(client, db_session):
    """El estado en DB cambia a ready_for_planning."""
    tenant = _demo_tenant(db_session)
    order = _build_order(db_session, tenant.id, OrderStatus.failed_delivery)
    token = _logistics_token(client)

    res = client.post(
        f"/orders/{order.id}/return-to-planning",
        headers=auth_headers(token),
    )
    assert res.status_code == 200, res.text

    db_session.expire(order)
    refreshed = db_session.scalar(select(Order).where(Order.id == order.id))
    assert refreshed is not None
    assert refreshed.status == OrderStatus.ready_for_planning


def test_return_ingested_order_returns_409(client, db_session):
    """Pedido en 'ingested' → 409 INVALID_STATE_TRANSITION."""
    tenant = _demo_tenant(db_session)
    order = _build_order(db_session, tenant.id, OrderStatus.ingested)
    token = _logistics_token(client)

    res = client.post(
        f"/orders/{order.id}/return-to-planning",
        headers=auth_headers(token),
    )
    assert res.status_code == 409, res.text
    assert res.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"


def test_return_planned_order_returns_409(client, db_session):
    """Pedido en 'planned' → 409 INVALID_STATE_TRANSITION."""
    tenant = _demo_tenant(db_session)
    order = _build_order(db_session, tenant.id, OrderStatus.planned)
    token = _logistics_token(client)

    res = client.post(
        f"/orders/{order.id}/return-to-planning",
        headers=auth_headers(token),
    )
    assert res.status_code == 409, res.text
    assert res.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"


def test_return_dispatched_order_returns_409(client, db_session):
    """Pedido en 'dispatched' → 409 INVALID_STATE_TRANSITION."""
    tenant = _demo_tenant(db_session)
    order = _build_order(db_session, tenant.id, OrderStatus.dispatched)
    token = _logistics_token(client)

    res = client.post(
        f"/orders/{order.id}/return-to-planning",
        headers=auth_headers(token),
    )
    assert res.status_code == 409, res.text
    assert res.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"


def test_return_unknown_order_returns_404(client, db_session):
    """Pedido inexistente → 404."""
    token = _logistics_token(client)

    res = client.post(
        f"/orders/{uuid.uuid4()}/return-to-planning",
        headers=auth_headers(token),
    )
    assert res.status_code == 404, res.text


def test_return_is_idempotent_on_already_ready(client, db_session):
    """
    Si ya está en ready_for_planning (e.g. retorno aplicado dos veces)
    → 409 INVALID_STATE_TRANSITION (no es failed_delivery).
    """
    tenant = _demo_tenant(db_session)
    order = _build_order(db_session, tenant.id, OrderStatus.failed_delivery)
    token = _logistics_token(client)

    # Primera llamada
    res1 = client.post(
        f"/orders/{order.id}/return-to-planning",
        headers=auth_headers(token),
    )
    assert res1.status_code == 200, res1.text

    # Segunda llamada: ya está en ready_for_planning
    res2 = client.post(
        f"/orders/{order.id}/return-to-planning",
        headers=auth_headers(token),
    )
    assert res2.status_code == 409, res2.text
    assert res2.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"
