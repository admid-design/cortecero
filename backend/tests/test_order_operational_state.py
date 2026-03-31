import uuid
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select

from app.models import (
    Customer,
    CustomerOperationalProfile,
    Order,
    OrderIntakeType,
    OperationalReasonCatalog,
    OrderStatus,
    SourceChannel,
    Tenant,
    User,
    UserRole,
    Zone,
)
from app.routers.orders import _resolve_timezone
from app.security import hash_password
from tests.helpers import auth_headers, create_order, login_as


def _first_zone_and_customer(client, token: str) -> tuple[str, str]:
    zones_res = client.get("/admin/zones", headers=auth_headers(token))
    assert zones_res.status_code == 200, zones_res.text
    zones = zones_res.json()["items"]
    assert zones
    zone_id = zones[0]["id"]

    customers_res = client.get(
        "/admin/customers",
        params={"zone_id": zone_id},
        headers=auth_headers(token),
    )
    assert customers_res.status_code == 200, customers_res.text
    customers = customers_res.json()["items"]
    assert customers
    return zone_id, customers[0]["id"]


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
            "ops_note": "R5-BE-003 test profile",
        },
        headers=auth_headers(token),
    )
    assert res.status_code == 200, res.text


def _create_operational_exception(
    client,
    token: str,
    customer_id: str,
    *,
    exception_date: date,
    exception_type: str,
) -> None:
    res = client.post(
        f"/admin/customers/{customer_id}/operational-exceptions",
        json={
            "date": exception_date.isoformat(),
            "type": exception_type,
            "note": "R5-BE-003 test exception",
        },
        headers=auth_headers(token),
    )
    assert res.status_code == 201, res.text


def test_operational_reason_precedence_and_status_not_mutated(client, db_session):
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
    _, customer_id = _first_zone_and_customer(client, admin_token)

    service_date = date(2100, 2, 10)
    _put_profile(
        client,
        admin_token,
        customer_id,
        accept_orders=False,
        window_start="08:00:00",
        window_end="10:00:00",
        min_lead_hours=6,
    )
    _create_operational_exception(
        client,
        admin_token,
        customer_id,
        exception_date=service_date,
        exception_type="blocked",
    )

    order_id = create_order(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="OPS-PRECEDENCE",
        service_date=service_date.isoformat(),
        created_at=f"{service_date.isoformat()}T03:00:00Z",
        sku="SKU-OPS-PRECEDENCE",
    )

    db_order = db_session.scalar(select(Order).where(Order.id == uuid.UUID(str(order_id))))
    assert db_order is not None
    status_before = db_order.status

    detail_res = client.get(f"/orders/{order_id}", headers=auth_headers(office_token))
    assert detail_res.status_code == 200, detail_res.text
    detail_body = detail_res.json()
    assert detail_body["operational_state"] == "restricted"
    assert detail_body["operational_reason"] == "CUSTOMER_DATE_BLOCKED"
    assert detail_body["operational_explanation"]["reason_code"] == "CUSTOMER_DATE_BLOCKED"
    assert detail_body["operational_explanation"]["reason_category"] == "customer_calendar"
    assert detail_body["operational_explanation"]["severity"] == "critical"
    assert detail_body["operational_explanation"]["catalog_status"] == "active"
    assert detail_body["operational_explanation"]["rule_version"] == "r6-operational-eval-v1"
    assert detail_body["status"] == status_before.value

    list_res = client.get(
        "/orders",
        params={"service_date": service_date.isoformat()},
        headers=auth_headers(office_token),
    )
    assert list_res.status_code == 200, list_res.text
    item = next(row for row in list_res.json()["items"] if row["id"] == str(order_id))
    assert item["operational_state"] == "restricted"
    assert item["operational_reason"] == "CUSTOMER_DATE_BLOCKED"
    assert item["operational_explanation"]["reason_code"] == "CUSTOMER_DATE_BLOCKED"
    assert item["operational_explanation"]["reason_category"] == "customer_calendar"
    assert item["operational_explanation"]["severity"] == "critical"
    assert item["operational_explanation"]["catalog_status"] == "active"
    assert item["status"] == status_before.value

    db_session.expire_all()
    db_after = db_session.scalar(select(Order).where(Order.id == uuid.UUID(str(order_id))))
    assert db_after is not None
    assert db_after.status == status_before


def test_operational_reason_temporal_edges_and_precedence_rules(client, db_session):
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
    zone_id, customer_id = _first_zone_and_customer(client, admin_token)

    # Zone timezone has precedence over tenant.default_timezone for operational evaluation.
    zone = db_session.scalar(select(Zone).where(Zone.id == zone_id))
    assert zone is not None
    zone.timezone = "UTC"
    db_session.commit()

    service_date = date(2100, 3, 15)
    base_service_date = service_date.isoformat()

    _put_profile(
        client,
        admin_token,
        customer_id,
        accept_orders=False,
        window_start=None,
        window_end=None,
        min_lead_hours=0,
    )
    not_accepting_order = create_order(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="OPS-NO-ACCEPT",
        service_date=base_service_date,
        created_at="2000-01-01T00:00:00Z",
    )
    not_accepting_res = client.get(f"/orders/{not_accepting_order}", headers=auth_headers(office_token))
    assert not_accepting_res.status_code == 200, not_accepting_res.text
    assert not_accepting_res.json()["operational_reason"] == "CUSTOMER_NOT_ACCEPTING_ORDERS"

    _put_profile(
        client,
        admin_token,
        customer_id,
        accept_orders=True,
        window_start="08:00:00",
        window_end="10:00:00",
        min_lead_hours=0,
    )
    same_day_start = create_order(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="OPS-WIN-SAME-START",
        service_date=base_service_date,
        created_at=f"{base_service_date}T08:00:00Z",
    )
    same_day_end = create_order(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="OPS-WIN-SAME-END",
        service_date=base_service_date,
        created_at=f"{base_service_date}T10:00:00Z",
    )
    same_day_out = create_order(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="OPS-WIN-SAME-OUT",
        service_date=base_service_date,
        created_at=f"{base_service_date}T10:00:01Z",
    )

    assert client.get(f"/orders/{same_day_start}", headers=auth_headers(office_token)).json()["operational_reason"] is None
    assert client.get(f"/orders/{same_day_end}", headers=auth_headers(office_token)).json()["operational_reason"] is None
    assert (
        client.get(f"/orders/{same_day_out}", headers=auth_headers(office_token)).json()["operational_reason"]
        == "OUTSIDE_CUSTOMER_WINDOW"
    )

    _put_profile(
        client,
        admin_token,
        customer_id,
        accept_orders=True,
        window_start="22:00:00",
        window_end="02:00:00",
        min_lead_hours=0,
    )
    cross_midnight_start = create_order(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="OPS-WIN-CROSS-START",
        service_date=base_service_date,
        created_at=f"{base_service_date}T22:00:00Z",
    )
    cross_midnight_end = create_order(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="OPS-WIN-CROSS-END",
        service_date=base_service_date,
        created_at=f"{base_service_date}T02:00:00Z",
    )
    cross_midnight_out = create_order(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="OPS-WIN-CROSS-OUT",
        service_date=base_service_date,
        created_at=f"{base_service_date}T14:00:00Z",
    )

    assert client.get(f"/orders/{cross_midnight_start}", headers=auth_headers(office_token)).json()["operational_reason"] is None
    assert client.get(f"/orders/{cross_midnight_end}", headers=auth_headers(office_token)).json()["operational_reason"] is None
    assert (
        client.get(f"/orders/{cross_midnight_out}", headers=auth_headers(office_token)).json()["operational_reason"]
        == "OUTSIDE_CUSTOMER_WINDOW"
    )

    _put_profile(
        client,
        admin_token,
        customer_id,
        accept_orders=True,
        window_start=None,
        window_end=None,
        min_lead_hours=4,
    )
    next_day = service_date + timedelta(days=1)
    next_day_str = next_day.isoformat()
    lead_exact = create_order(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="OPS-LEAD-EXACT",
        service_date=next_day_str,
        created_at=f"{service_date.isoformat()}T20:00:00Z",
    )
    lead_insufficient = create_order(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="OPS-LEAD-LOW",
        service_date=next_day_str,
        created_at=f"{service_date.isoformat()}T20:00:01Z",
    )

    assert client.get(f"/orders/{lead_exact}", headers=auth_headers(office_token)).json()["operational_reason"] is None
    assert (
        client.get(f"/orders/{lead_insufficient}", headers=auth_headers(office_token)).json()["operational_reason"]
        == "INSUFFICIENT_LEAD_TIME"
    )


def test_operational_explanation_catalog_resolution_and_timezone_fallbacks(client, db_session):
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
    zone_id, customer_id = _first_zone_and_customer(client, admin_token)
    zone_uuid = uuid.UUID(zone_id)

    tenant = db_session.scalar(select(Tenant).where(Tenant.slug == "demo-cortecero"))
    zone = db_session.scalar(select(Zone).where(Zone.id == zone_uuid))
    assert tenant is not None
    assert zone is not None

    _put_profile(
        client,
        admin_token,
        customer_id,
        accept_orders=False,
        window_start=None,
        window_end=None,
        min_lead_hours=0,
    )

    service_date = date(2101, 1, 10)
    order_id = create_order(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="OPS-EXPLAIN",
        service_date=service_date.isoformat(),
        created_at=f"{service_date.isoformat()}T06:00:00Z",
    )

    active_detail = client.get(f"/orders/{order_id}", headers=auth_headers(office_token))
    assert active_detail.status_code == 200, active_detail.text
    active_explanation = active_detail.json()["operational_explanation"]
    assert active_explanation["reason_code"] == "CUSTOMER_NOT_ACCEPTING_ORDERS"
    assert active_explanation["reason_category"] == "customer_policy"
    assert active_explanation["severity"] == "critical"
    assert active_explanation["catalog_status"] == "active"
    assert active_explanation["rule_version"] == "r6-operational-eval-v1"
    assert active_explanation["timezone_source"] == "zone"

    catalog_row = db_session.scalar(
        select(OperationalReasonCatalog).where(
            OperationalReasonCatalog.code == "CUSTOMER_NOT_ACCEPTING_ORDERS"
        )
    )
    assert catalog_row is not None

    catalog_row.active = False
    db_session.commit()
    inactive_detail = client.get(f"/orders/{order_id}", headers=auth_headers(office_token))
    assert inactive_detail.status_code == 200, inactive_detail.text
    inactive_explanation = inactive_detail.json()["operational_explanation"]
    assert inactive_explanation["reason_code"] == "CUSTOMER_NOT_ACCEPTING_ORDERS"
    assert inactive_explanation["reason_category"] == "catalog_mismatch"
    assert inactive_explanation["severity"] == "critical"
    assert inactive_explanation["catalog_status"] == "inactive"

    db_session.delete(catalog_row)
    db_session.commit()
    missing_detail = client.get(f"/orders/{order_id}", headers=auth_headers(office_token))
    assert missing_detail.status_code == 200, missing_detail.text
    missing_explanation = missing_detail.json()["operational_explanation"]
    assert missing_explanation["reason_code"] == "CUSTOMER_NOT_ACCEPTING_ORDERS"
    assert missing_explanation["reason_category"] == "catalog_mismatch"
    assert missing_explanation["severity"] == "critical"
    assert missing_explanation["catalog_status"] == "missing"

    tenant_fallback = _resolve_timezone("Europe/Madrid", "Invalid/Zone")
    assert tenant_fallback.timezone_used == "Europe/Madrid"
    assert tenant_fallback.timezone_source == "tenant_default"

    utc_fallback = _resolve_timezone("Invalid/Tenant", "Invalid/Zone")
    assert utc_fallback.timezone_used == "UTC"
    assert utc_fallback.timezone_source == "utc_fallback"


def test_orders_operational_state_is_tenant_isolated(client, db_session):
    now = datetime.now(UTC)
    service_date = date(2100, 4, 20)

    tenant_b = Tenant(
        name="Tenant B Operational Orders",
        slug="tenant-b-operational-orders",
        default_cutoff_time=time(10, 0),
        default_timezone="Europe/Madrid",
        auto_lock_enabled=False,
        created_at=now,
    )
    db_session.add(tenant_b)
    db_session.flush()

    user_b = User(
        tenant_id=tenant_b.id,
        email="office@tenantb-operational-orders.cortecero.app",
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
        name="Zona Tenant B Operational Orders",
        default_cutoff_time=time(9, 0),
        timezone="UTC",
        active=True,
        created_at=now,
    )
    db_session.add(zone_b)
    db_session.flush()

    customer_b = Customer(
        tenant_id=tenant_b.id,
        zone_id=zone_b.id,
        name="Cliente Tenant B Operational Orders",
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
        tenant_slug="tenant-b-operational-orders",
        email="office@tenantb-operational-orders.cortecero.app",
        password="officeb123",
    )
    tenant_b_order_id = create_order(
        client,
        tenant_b_token,
        customer_id=str(customer_b.id),
        external_ref_prefix="TENANTB-OPS",
        service_date=service_date.isoformat(),
        created_at="2000-01-01T00:00:00Z",
    )

    tenant_b_detail = client.get(f"/orders/{tenant_b_order_id}", headers=auth_headers(tenant_b_token))
    assert tenant_b_detail.status_code == 200, tenant_b_detail.text
    assert tenant_b_detail.json()["operational_reason"] == "CUSTOMER_NOT_ACCEPTING_ORDERS"

    demo_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )
    demo_list = client.get(
        "/orders",
        params={"service_date": service_date.isoformat()},
        headers=auth_headers(demo_token),
    )
    assert demo_list.status_code == 200, demo_list.text
    demo_ids = {item["id"] for item in demo_list.json()["items"]}
    assert str(tenant_b_order_id) not in demo_ids

    demo_detail = client.get(f"/orders/{tenant_b_order_id}", headers=auth_headers(demo_token))
    assert demo_detail.status_code == 404
    assert demo_detail.json()["detail"]["code"] == "ORDER_NOT_FOUND"
