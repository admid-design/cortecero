from datetime import UTC, datetime, timedelta

import pytest

from app.models import Customer, Order, OrderIntakeType, OrderStatus, SourceChannel, Tenant, Zone
from tests.helpers import auth_headers, create_order, login_as


def test_order_responses_expose_total_weight_kg(client):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )

    orders_res = client.get("/orders", headers=auth_headers(token))
    assert orders_res.status_code == 200, orders_res.text
    items = orders_res.json()["items"]
    assert items
    assert "total_weight_kg" in items[0]

    order_id = items[0]["id"]
    detail_res = client.get(f"/orders/{order_id}", headers=auth_headers(token))
    assert detail_res.status_code == 200, detail_res.text
    assert "total_weight_kg" in detail_res.json()


def test_order_weight_update_by_logistics_and_audit(client):
    office_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )
    logistics_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )

    orders_res = client.get("/orders", headers=auth_headers(office_token))
    assert orders_res.status_code == 200, orders_res.text
    customer_id = orders_res.json()["items"][0]["customer_id"]

    order_id = create_order(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="WEIGHT-OK",
        service_date="2099-12-26",
        created_at="2026-01-01T00:00:00Z",
        sku="SKU-WEIGHT-OK",
    )

    patch_res = client.patch(
        f"/orders/{order_id}/weight",
        json={"total_weight_kg": 123.456},
        headers=auth_headers(logistics_token),
    )
    assert patch_res.status_code == 200, patch_res.text
    body = patch_res.json()
    assert float(body["total_weight_kg"]) == pytest.approx(123.456)

    detail_res = client.get(f"/orders/{order_id}", headers=auth_headers(logistics_token))
    assert detail_res.status_code == 200, detail_res.text
    assert float(detail_res.json()["total_weight_kg"]) == pytest.approx(123.456)

    audit_res = client.get(
        "/audit",
        params={"entity_type": "order", "entity_id": order_id},
        headers=auth_headers(logistics_token),
    )
    assert audit_res.status_code == 200, audit_res.text
    weight_events = [item for item in audit_res.json()["items"] if item["action"] == "order.weight_updated"]
    assert len(weight_events) == 1
    metadata = weight_events[0]["metadata_json"]
    assert metadata["previous_total_weight_kg"] is None
    assert float(metadata["new_total_weight_kg"]) == pytest.approx(123.456)


def test_order_weight_update_rejects_negative_weight(client):
    office_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )
    logistics_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )

    orders_res = client.get("/orders", headers=auth_headers(office_token))
    assert orders_res.status_code == 200, orders_res.text
    customer_id = orders_res.json()["items"][0]["customer_id"]
    order_id = create_order(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="WEIGHT-NEG",
        service_date="2099-12-25",
        created_at="2026-01-01T00:00:00Z",
        sku="SKU-WEIGHT-NEG",
    )

    patch_res = client.patch(
        f"/orders/{order_id}/weight",
        json={"total_weight_kg": -1},
        headers=auth_headers(logistics_token),
    )
    assert patch_res.status_code == 422
    assert patch_res.json()["detail"]["code"] == "INVALID_WEIGHT_VALUE"


def test_order_weight_update_enforces_rbac_and_tenant_scope(client, db_session):
    office_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )
    logistics_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )

    orders_res = client.get("/orders", headers=auth_headers(office_token))
    assert orders_res.status_code == 200, orders_res.text
    order_id = orders_res.json()["items"][0]["id"]

    forbidden_res = client.patch(
        f"/orders/{order_id}/weight",
        json={"total_weight_kg": 10},
        headers=auth_headers(office_token),
    )
    assert forbidden_res.status_code == 403
    assert forbidden_res.json()["detail"]["code"] == "RBAC_FORBIDDEN"

    now = datetime.now(UTC)
    tenant_b = Tenant(
        name="Tenant B Weight",
        slug="tenant-b-weight",
        default_cutoff_time=now.time().replace(microsecond=0),
        default_timezone="Europe/Madrid",
        auto_lock_enabled=False,
        created_at=now,
    )
    db_session.add(tenant_b)
    db_session.flush()

    zone_b = Zone(
        tenant_id=tenant_b.id,
        name="Zona B Weight",
        default_cutoff_time=now.time().replace(microsecond=0),
        timezone="Europe/Madrid",
        active=True,
        created_at=now,
    )
    db_session.add(zone_b)
    db_session.flush()

    customer_b = Customer(
        tenant_id=tenant_b.id,
        zone_id=zone_b.id,
        name="Cliente B Weight",
        priority=0,
        cutoff_override_time=None,
        active=True,
        created_at=now,
    )
    db_session.add(customer_b)
    db_session.flush()

    tenant_b_order = Order(
        tenant_id=tenant_b.id,
        customer_id=customer_b.id,
        zone_id=zone_b.id,
        external_ref="TENANTB-WEIGHT-001",
        requested_date=(now + timedelta(days=1)).date(),
        service_date=(now + timedelta(days=1)).date(),
        created_at=now,
        status=OrderStatus.ready_for_planning,
        is_late=False,
        lateness_reason=None,
        effective_cutoff_at=now,
        source_channel=SourceChannel.office,
        intake_type=OrderIntakeType.new_order,
        total_weight_kg=None,
        ingested_at=now,
        updated_at=now,
    )
    db_session.add(tenant_b_order)
    db_session.commit()

    tenant_scope_res = client.patch(
        f"/orders/{tenant_b_order.id}/weight",
        json={"total_weight_kg": 50},
        headers=auth_headers(logistics_token),
    )
    assert tenant_scope_res.status_code == 404
    assert tenant_scope_res.json()["detail"]["code"] == "ORDER_NOT_FOUND"
