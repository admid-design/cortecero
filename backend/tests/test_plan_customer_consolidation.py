from datetime import UTC, datetime
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
from tests.helpers import auth_headers, create_order, far_future_service_date, login_as


def _zone_and_two_customers(client, token: str) -> tuple[str, str, str]:
    zones_res = client.get("/admin/zones", headers=auth_headers(token))
    assert zones_res.status_code == 200, zones_res.text
    zones = zones_res.json()["items"]
    assert zones
    zone_id = zones[0]["id"]

    customers_res = client.get(
        "/admin/customers",
        params={"zone_id": zone_id, "active": True},
        headers=auth_headers(token),
    )
    assert customers_res.status_code == 200, customers_res.text
    customers = customers_res.json()["items"]
    assert len(customers) >= 2
    return zone_id, customers[0]["id"], customers[1]["id"]


def test_plan_customer_consolidation_is_derived_and_deterministic(client, db_session):
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

    zone_id, customer_a_id, customer_b_id = _zone_and_two_customers(client, office_token)
    service_date = far_future_service_date(7500)

    create_plan_res = client.post(
        "/plans",
        json={"service_date": service_date, "zone_id": zone_id},
        headers=auth_headers(logistics_token),
    )
    assert create_plan_res.status_code == 201, create_plan_res.text
    plan_id = create_plan_res.json()["id"]

    empty_res = client.get(f"/plans/{plan_id}/customer-consolidation", headers=auth_headers(logistics_token))
    assert empty_res.status_code == 200, empty_res.text
    assert empty_res.json()["items"] == []
    assert empty_res.json()["total_customers"] == 0

    a1 = create_order(
        client,
        office_token,
        customer_id=customer_a_id,
        external_ref_prefix="CONS-A1",
        service_date=service_date,
        created_at="2026-01-01T08:00:00Z",
    )
    a2 = create_order(
        client,
        office_token,
        customer_id=customer_a_id,
        external_ref_prefix="CONS-A2",
        service_date=service_date,
        created_at="2026-01-01T08:05:00Z",
    )
    a3 = create_order(
        client,
        office_token,
        customer_id=customer_a_id,
        external_ref_prefix="CONS-A3",
        service_date=service_date,
        created_at="2026-01-01T08:10:00Z",
    )
    b1 = create_order(
        client,
        office_token,
        customer_id=customer_b_id,
        external_ref_prefix="CONS-B1",
        service_date=service_date,
        created_at="2026-01-01T08:15:00Z",
    )
    b2 = create_order(
        client,
        office_token,
        customer_id=customer_b_id,
        external_ref_prefix="CONS-B2",
        service_date=service_date,
        created_at="2026-01-01T08:20:00Z",
    )

    # Interleaved inclusion order to verify per-customer order_refs are stable by added_at.
    for order_id in (b1, a1, a2, b2, a3):
        include_res = client.post(
            f"/plans/{plan_id}/orders",
            json={"order_id": order_id},
            headers=auth_headers(logistics_token),
        )
        assert include_res.status_code == 200, include_res.text

    tracked_ids = [UUID(a1), UUID(a2), UUID(a3), UUID(b1), UUID(b2)]
    orders = list(db_session.scalars(select(Order).where(Order.id.in_(tracked_ids))))
    assert len(orders) == 5
    by_id = {str(row.id): row for row in orders}
    by_id[a1].total_weight_kg = 10
    by_id[a2].total_weight_kg = None
    by_id[a3].total_weight_kg = 5
    by_id[b1].total_weight_kg = None
    by_id[b2].total_weight_kg = None
    status_before = {str(row.id): row.status for row in orders}

    plan_row = db_session.scalar(select(Plan).where(Plan.id == UUID(plan_id)))
    assert plan_row is not None
    version_before = plan_row.version
    db_session.commit()

    refs_by_id = {str(row.id): row.external_ref for row in orders}

    res = client.get(f"/plans/{plan_id}/customer-consolidation", headers=auth_headers(logistics_token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["plan_id"] == plan_id
    assert body["service_date"] == service_date
    assert body["zone_id"] == zone_id
    assert body["total_customers"] == 2
    assert len(body["items"]) == 2

    first = body["items"][0]
    second = body["items"][1]

    assert first["customer_id"] == customer_a_id
    assert first["total_orders"] == 3
    assert first["order_refs"] == [refs_by_id[a1], refs_by_id[a2], refs_by_id[a3]]
    assert first["orders_with_weight"] == 2
    assert first["orders_missing_weight"] == 1
    assert float(first["total_weight_kg"]) == pytest.approx(15)

    assert second["customer_id"] == customer_b_id
    assert second["total_orders"] == 2
    assert second["order_refs"] == [refs_by_id[b1], refs_by_id[b2]]
    assert second["orders_with_weight"] == 0
    assert second["orders_missing_weight"] == 2
    assert second["total_weight_kg"] is None

    db_session.expire_all()
    after_orders = list(db_session.scalars(select(Order).where(Order.id.in_(tracked_ids))))
    status_after = {str(row.id): row.status for row in after_orders}
    assert status_after == status_before

    plan_after = db_session.scalar(select(Plan).where(Plan.id == UUID(plan_id)))
    assert plan_after is not None
    assert plan_after.version == version_before


def test_plan_customer_consolidation_is_tenant_isolated(client, db_session):
    logistics_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )

    now = datetime.now(UTC)
    tenant_b = Tenant(
        name="Tenant B Consolidation",
        slug="tenant-b-consolidation",
        default_cutoff_time=now.time().replace(microsecond=0),
        default_timezone="Europe/Madrid",
        auto_lock_enabled=False,
        created_at=now,
    )
    db_session.add(tenant_b)
    db_session.flush()

    user_b = User(
        tenant_id=tenant_b.id,
        email="logistics@tenantb-consolidation.cortecero.app",
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
        name="Zona Tenant B Consolidation",
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
        name="Cliente Tenant B Consolidation",
        priority=0,
        cutoff_override_time=None,
        active=True,
        created_at=now,
    )
    db_session.add(customer_b)
    db_session.flush()

    service_date = now.date()
    order_b = Order(
        tenant_id=tenant_b.id,
        customer_id=customer_b.id,
        zone_id=zone_b.id,
        external_ref="TENANTB-CONS-001",
        requested_date=service_date,
        service_date=service_date,
        created_at=now,
        status=OrderStatus.planned,
        is_late=False,
        lateness_reason=None,
        effective_cutoff_at=now,
        source_channel=SourceChannel.office,
        intake_type=OrderIntakeType.new_order,
        total_weight_kg=12,
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

    denied = client.get(f"/plans/{plan_b.id}/customer-consolidation", headers=auth_headers(logistics_token))
    assert denied.status_code == 404
    assert denied.json()["detail"]["code"] == "PLAN_NOT_FOUND"

    tenant_b_token = login_as(
        client,
        tenant_slug="tenant-b-consolidation",
        email="logistics@tenantb-consolidation.cortecero.app",
        password="tenantb123",
    )
    allowed = client.get(f"/plans/{plan_b.id}/customer-consolidation", headers=auth_headers(tenant_b_token))
    assert allowed.status_code == 200, allowed.text
    body = allowed.json()
    assert body["total_customers"] == 1
    assert body["items"][0]["customer_id"] == str(customer_b.id)
    assert body["items"][0]["order_refs"] == ["TENANTB-CONS-001"]
    assert float(body["items"][0]["total_weight_kg"]) == pytest.approx(12)

