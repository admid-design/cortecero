from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select

from app.models import (
    Customer,
    InclusionType,
    Order,
    OrderIntakeType,
    OrderStatus,
    Plan,
    PlanOrder,
    PlanStatus,
    SourceChannel,
    Tenant,
    User,
    UserRole,
    Zone,
)
from app.security import hash_password
from tests.helpers import auth_headers, create_order, login_as


def _create_demo_plan_with_two_orders(client, db_session, service_date: str) -> tuple[str, str, str, str]:
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
    zone_id = orders_res.json()["items"][0]["zone_id"]

    create_plan_res = client.post(
        "/plans",
        json={"service_date": service_date, "zone_id": zone_id},
        headers=auth_headers(logistics_token),
    )
    assert create_plan_res.status_code == 201, create_plan_res.text
    plan_id = create_plan_res.json()["id"]

    order_a = create_order(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="PLAN-W-A",
        service_date=service_date,
        created_at="2026-01-01T00:00:00Z",
        sku="SKU-PLAN-W-A",
    )
    order_b = create_order(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="PLAN-W-B",
        service_date=service_date,
        created_at="2026-01-01T00:05:00Z",
        sku="SKU-PLAN-W-B",
    )

    include_a = client.post(
        f"/plans/{plan_id}/orders",
        json={"order_id": order_a},
        headers=auth_headers(logistics_token),
    )
    assert include_a.status_code == 200, include_a.text
    include_b = client.post(
        f"/plans/{plan_id}/orders",
        json={"order_id": order_b},
        headers=auth_headers(logistics_token),
    )
    assert include_b.status_code == 200, include_b.text

    return logistics_token, plan_id, order_a, order_b


def test_plan_weight_aggregation_complete(client, db_session):
    logistics_token, plan_id, order_a, order_b = _create_demo_plan_with_two_orders(client, db_session, "2099-12-10")

    order_rows = list(
        db_session.scalars(select(Order).where(Order.id.in_([UUID(order_a), UUID(order_b)])))
    )
    assert len(order_rows) == 2
    by_id = {str(row.id): row for row in order_rows}
    by_id[order_a].total_weight_kg = 12.5
    by_id[order_b].total_weight_kg = 7.25
    db_session.commit()

    detail_res = client.get(f"/plans/{plan_id}", headers=auth_headers(logistics_token))
    assert detail_res.status_code == 200, detail_res.text
    body = detail_res.json()
    assert body["orders_total"] == 2
    assert body["orders_with_weight"] == 2
    assert body["orders_missing_weight"] == 0
    assert float(body["total_weight_kg"]) == pytest.approx(19.75)


def test_plan_weight_aggregation_partial(client, db_session):
    logistics_token, plan_id, order_a, order_b = _create_demo_plan_with_two_orders(client, db_session, "2099-12-11")

    order_rows = list(
        db_session.scalars(select(Order).where(Order.id.in_([UUID(order_a), UUID(order_b)])))
    )
    assert len(order_rows) == 2
    by_id = {str(row.id): row for row in order_rows}
    by_id[order_a].total_weight_kg = 4
    by_id[order_b].total_weight_kg = None
    db_session.commit()

    detail_res = client.get(f"/plans/{plan_id}", headers=auth_headers(logistics_token))
    assert detail_res.status_code == 200, detail_res.text
    body = detail_res.json()
    assert body["orders_total"] == 2
    assert body["orders_with_weight"] == 1
    assert body["orders_missing_weight"] == 1
    assert float(body["total_weight_kg"]) == pytest.approx(4)


def test_plan_weight_aggregation_tenant_isolation(client, db_session):
    logistics_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )

    now = datetime.now(UTC)
    tenant_b = Tenant(
        name="Tenant B Plan Weight",
        slug="tenant-b-plan-weight",
        default_cutoff_time=now.time().replace(microsecond=0),
        default_timezone="Europe/Madrid",
        auto_lock_enabled=False,
        created_at=now,
    )
    db_session.add(tenant_b)
    db_session.flush()

    user_b = User(
        tenant_id=tenant_b.id,
        email="logistics@tenantb-planweight.cortecero.app",
        full_name="Tenant B Logistics",
        password_hash=hash_password("tenantb123"),
        role=UserRole.logistics,
        is_active=True,
        created_at=now,
    )
    db_session.add(user_b)
    db_session.flush()

    zone_b = Zone(
        tenant_id=tenant_b.id,
        name="Zona Tenant B Plan Weight",
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
        name="Cliente Tenant B Plan Weight",
        priority=0,
        cutoff_override_time=None,
        active=True,
        created_at=now,
    )
    db_session.add(customer_b)
    db_session.flush()

    service_date = (now + timedelta(days=1)).date()
    order_b = Order(
        tenant_id=tenant_b.id,
        customer_id=customer_b.id,
        zone_id=zone_b.id,
        external_ref="TENANTB-PLAN-W-001",
        requested_date=service_date,
        service_date=service_date,
        created_at=now,
        status=OrderStatus.ready_for_planning,
        is_late=False,
        lateness_reason=None,
        effective_cutoff_at=now,
        source_channel=SourceChannel.office,
        intake_type=OrderIntakeType.new_order,
        total_weight_kg=999,
        ingested_at=now,
        updated_at=now,
    )
    db_session.add(order_b)
    db_session.flush()

    plan_b = Plan(
        tenant_id=tenant_b.id,
        service_date=service_date,
        zone_id=zone_b.id,
        status=PlanStatus.open,
        version=1,
        locked_at=None,
        locked_by=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(plan_b)
    db_session.flush()

    db_session.add(
        PlanOrder(
            tenant_id=tenant_b.id,
            plan_id=plan_b.id,
            order_id=order_b.id,
            inclusion_type=InclusionType.normal,
            added_at=now,
            added_by=user_b.id,
        )
    )
    db_session.commit()

    detail_res = client.get(f"/plans/{plan_b.id}", headers=auth_headers(logistics_token))
    assert detail_res.status_code == 404
    assert detail_res.json()["detail"]["code"] == "PLAN_NOT_FOUND"

    list_res = client.get(
        "/plans",
        params={"service_date": service_date.isoformat()},
        headers=auth_headers(logistics_token),
    )
    assert list_res.status_code == 200, list_res.text
    returned_ids = {item["id"] for item in list_res.json()["items"]}
    assert str(plan_b.id) not in returned_ids
