import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.models import (
    Customer,
    CustomerOperationalProfile,
    Order,
    Tenant,
    User,
    UserRole,
    Zone,
)
from app.security import hash_password
from tests.helpers import auth_headers, create_order, far_future_service_date, login_as


def _zone_and_customers(client, token: str) -> tuple[str, list[str]]:
    zones_res = client.get("/admin/zones", headers=auth_headers(token))
    assert zones_res.status_code == 200, zones_res.text
    zones = zones_res.json()["items"]
    assert len(zones) >= 2
    zone_id = zones[0]["id"]

    customers_res = client.get(
        "/admin/customers",
        params={"zone_id": zone_id, "active": True},
        headers=auth_headers(token),
    )
    assert customers_res.status_code == 200, customers_res.text
    customers = customers_res.json()["items"]
    assert len(customers) >= 4
    return zone_id, [row["id"] for row in customers]


def _put_profile(
    client,
    token: str,
    customer_id: str,
    *,
    accept_orders: bool,
    window_start: str | None,
    window_end: str | None,
    min_lead_hours: int,
) -> None:
    res = client.put(
        f"/admin/customers/{customer_id}/operational-profile",
        json={
            "accept_orders": accept_orders,
            "window_start": window_start,
            "window_end": window_end,
            "min_lead_hours": min_lead_hours,
            "consolidate_by_default": False,
            "ops_note": "R5-BE-004 profile",
        },
        headers=auth_headers(token),
    )
    assert res.status_code == 200, res.text


def _create_operational_exception(
    client,
    token: str,
    customer_id: str,
    *,
    service_date: str,
    exception_type: str,
) -> None:
    res = client.post(
        f"/admin/customers/{customer_id}/operational-exceptions",
        json={
            "date": service_date,
            "type": exception_type,
            "note": "R5-BE-004 exception",
        },
        headers=auth_headers(token),
    )
    assert res.status_code == 201, res.text


def test_operational_queue_filters_and_deterministic_order(client, db_session):
    admin_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="admin@demo.cortecero.app",
        password="admin123",
    )
    office_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )

    zone_id, customer_ids = _zone_and_customers(client, admin_token)
    blocked_customer_id, no_accept_customer_id, window_customer_id, lead_customer_id = customer_ids[:4]

    zone = db_session.scalar(select(Zone).where(Zone.id == uuid.UUID(zone_id)))
    assert zone is not None
    zone.timezone = "UTC"
    db_session.commit()

    service_date = far_future_service_date(7000)
    service_date_obj = date.fromisoformat(service_date)
    previous_day = service_date_obj - timedelta(days=1)

    _put_profile(
        client,
        admin_token,
        blocked_customer_id,
        accept_orders=True,
        window_start=None,
        window_end=None,
        min_lead_hours=0,
    )
    _create_operational_exception(
        client,
        admin_token,
        blocked_customer_id,
        service_date=service_date,
        exception_type="blocked",
    )

    _put_profile(
        client,
        admin_token,
        no_accept_customer_id,
        accept_orders=False,
        window_start=None,
        window_end=None,
        min_lead_hours=0,
    )

    _put_profile(
        client,
        admin_token,
        window_customer_id,
        accept_orders=True,
        window_start="08:00:00",
        window_end="09:00:00",
        min_lead_hours=0,
    )

    _put_profile(
        client,
        admin_token,
        lead_customer_id,
        accept_orders=True,
        window_start=None,
        window_end=None,
        min_lead_hours=6,
    )

    blocked_order_id = create_order(
        client,
        office_token,
        customer_id=blocked_customer_id,
        external_ref_prefix="OPSQ-BLOCKED",
        service_date=service_date,
        created_at=f"{service_date}T08:30:00Z",
    )
    no_accept_order_id = create_order(
        client,
        office_token,
        customer_id=no_accept_customer_id,
        external_ref_prefix="OPSQ-NO-ACCEPT",
        service_date=service_date,
        created_at=f"{service_date}T08:35:00Z",
    )
    outside_window_order_id = create_order(
        client,
        office_token,
        customer_id=window_customer_id,
        external_ref_prefix="OPSQ-WINDOW",
        service_date=service_date,
        created_at=f"{service_date}T10:00:00Z",
    )
    lead_order_early_id = create_order(
        client,
        office_token,
        customer_id=lead_customer_id,
        external_ref_prefix="OPSQ-LEAD-EARLY",
        service_date=service_date,
        created_at=f"{previous_day.isoformat()}T20:00:00Z",
    )
    lead_order_late_id = create_order(
        client,
        office_token,
        customer_id=lead_customer_id,
        external_ref_prefix="OPSQ-LEAD-LATE",
        service_date=service_date,
        created_at=f"{previous_day.isoformat()}T21:00:00Z",
    )

    tracked_ids = [
        uuid.UUID(str(blocked_order_id)),
        uuid.UUID(str(no_accept_order_id)),
        uuid.UUID(str(outside_window_order_id)),
        uuid.UUID(str(lead_order_early_id)),
        uuid.UUID(str(lead_order_late_id)),
    ]
    status_before = {
        row.id: row.status
        for row in db_session.scalars(select(Order).where(Order.id.in_(tracked_ids))).all()
    }

    queue_res = client.get(
        "/orders/operational-queue",
        params={"service_date": service_date},
        headers=auth_headers(office_token),
    )
    assert queue_res.status_code == 200, queue_res.text
    body = queue_res.json()
    queue_items = body["items"]
    assert body["total"] == len(queue_items)

    queue_ids = [item["order_id"] for item in queue_items]
    assert set(queue_ids) == {
        str(blocked_order_id),
        str(no_accept_order_id),
        str(outside_window_order_id),
        str(lead_order_early_id),
        str(lead_order_late_id),
    }

    assert [item["reason"] for item in queue_items] == [
        "CUSTOMER_DATE_BLOCKED",
        "CUSTOMER_NOT_ACCEPTING_ORDERS",
        "OUTSIDE_CUSTOMER_WINDOW",
        "INSUFFICIENT_LEAD_TIME",
        "INSUFFICIENT_LEAD_TIME",
    ]

    # Same reason tie-break keeps created_at ascending.
    assert queue_items[3]["order_id"] == str(lead_order_early_id)
    assert queue_items[4]["order_id"] == str(lead_order_late_id)
    assert queue_items[3]["created_at"] < queue_items[4]["created_at"]

    reason_filtered = client.get(
        "/orders/operational-queue",
        params={"service_date": service_date, "reason": "INSUFFICIENT_LEAD_TIME"},
        headers=auth_headers(office_token),
    )
    assert reason_filtered.status_code == 200, reason_filtered.text
    reason_items = reason_filtered.json()["items"]
    assert [item["order_id"] for item in reason_items] == [str(lead_order_early_id), str(lead_order_late_id)]
    assert all(item["reason"] == "INSUFFICIENT_LEAD_TIME" for item in reason_items)

    zone_filtered = client.get(
        "/orders/operational-queue",
        params={"service_date": service_date, "zone_id": zone_id},
        headers=auth_headers(office_token),
    )
    assert zone_filtered.status_code == 200, zone_filtered.text
    assert zone_filtered.json()["total"] == body["total"]

    db_session.expire_all()
    status_after = {
        row.id: row.status
        for row in db_session.scalars(select(Order).where(Order.id.in_(tracked_ids))).all()
    }
    assert status_after == status_before


def test_operational_queue_is_tenant_isolated(client, db_session):
    now = datetime.now(UTC)
    service_date = date(2100, 5, 1)

    tenant_b = Tenant(
        name="Tenant B Operational Queue",
        slug="tenant-b-operational-queue",
        default_cutoff_time=datetime.strptime("10:00", "%H:%M").time(),
        default_timezone="Europe/Madrid",
        auto_lock_enabled=False,
        created_at=now,
    )
    db_session.add(tenant_b)
    db_session.flush()

    user_b = User(
        tenant_id=tenant_b.id,
        email="office@tenantb-operational-queue.cortecero.app",
        full_name="Tenant B Office",
        password_hash=hash_password("officeb123"),
        role=UserRole.office,
        is_active=True,
        created_at=now,
    )
    db_session.add(user_b)
    db_session.flush()

    zone_b = Zone(
        tenant_id=tenant_b.id,
        name="Zona Tenant B Operational Queue",
        default_cutoff_time=datetime.strptime("09:00", "%H:%M").time(),
        timezone="UTC",
        active=True,
        created_at=now,
    )
    db_session.add(zone_b)
    db_session.flush()

    customer_b = Customer(
        tenant_id=tenant_b.id,
        zone_id=zone_b.id,
        name="Cliente Tenant B Operational Queue",
        priority=0,
        cutoff_override_time=None,
        active=True,
        created_at=now,
    )
    db_session.add(customer_b)
    db_session.flush()

    db_session.add(
        CustomerOperationalProfile(
            tenant_id=tenant_b.id,
            customer_id=customer_b.id,
            accept_orders=False,
            window_start=None,
            window_end=None,
            min_lead_hours=0,
            consolidate_by_default=False,
            ops_note=None,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.commit()

    tenant_b_token = login_as(
        client,
        tenant_slug="tenant-b-operational-queue",
        email="office@tenantb-operational-queue.cortecero.app",
        password="officeb123",
    )
    tenant_b_order_id = create_order(
        client,
        tenant_b_token,
        customer_id=str(customer_b.id),
        external_ref_prefix="TENANTB-OPSQ",
        service_date=service_date.isoformat(),
        created_at="2000-01-01T00:00:00Z",
    )

    tenant_b_queue = client.get(
        "/orders/operational-queue",
        params={"service_date": service_date.isoformat()},
        headers=auth_headers(tenant_b_token),
    )
    assert tenant_b_queue.status_code == 200, tenant_b_queue.text
    tenant_b_ids = {item["order_id"] for item in tenant_b_queue.json()["items"]}
    assert str(tenant_b_order_id) in tenant_b_ids

    demo_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )
    demo_queue = client.get(
        "/orders/operational-queue",
        params={"service_date": service_date.isoformat()},
        headers=auth_headers(demo_token),
    )
    assert demo_queue.status_code == 200, demo_queue.text
    demo_ids = {item["order_id"] for item in demo_queue.json()["items"]}
    assert str(tenant_b_order_id) not in demo_ids
