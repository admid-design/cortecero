from datetime import UTC, date, datetime, time
from uuid import UUID, uuid4

from sqlalchemy import select

from app.models import (
    Customer,
    Order,
    OrderIntakeType,
    OrderOperationalSnapshot,
    OrderStatus,
    SourceChannel,
    Tenant,
    User,
    UserRole,
    Zone,
)
from app.security import hash_password
from tests.helpers import auth_headers, create_order, far_future_service_date, login_as


def _first_customer_id(client, token: str) -> str:
    zones_res = client.get("/admin/zones", headers=auth_headers(token))
    assert zones_res.status_code == 200, zones_res.text
    zones = zones_res.json()["items"]
    assert zones

    customers_res = client.get(
        "/admin/customers",
        params={"zone_id": zones[0]["id"], "active": True},
        headers=auth_headers(token),
    )
    assert customers_res.status_code == 200, customers_res.text
    customers = customers_res.json()["items"]
    assert customers
    return customers[0]["id"]


def test_order_operational_snapshots_timeline_is_read_only_and_deterministic(client, db_session):
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

    service_date = far_future_service_date(9600)
    customer_id = _first_customer_id(client, admin_token)
    order_id = create_order(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="SNAP-TL",
        service_date=service_date,
        created_at=f"{service_date}T08:00:00Z",
    )
    tracked_order = db_session.scalar(select(Order).where(Order.id == UUID(str(order_id))))
    assert tracked_order is not None
    status_before = tracked_order.status

    evaluation_ts_a = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    evaluation_ts_c = datetime(2026, 1, 1, 11, 0, tzinfo=UTC)
    snapshot_id_a = UUID("00000000-0000-0000-0000-000000000001")
    snapshot_id_b = UUID("00000000-0000-0000-0000-000000000002")
    snapshot_id_c = UUID("00000000-0000-0000-0000-000000000003")

    db_session.add(
        OrderOperationalSnapshot(
            id=snapshot_id_b,
            tenant_id=tracked_order.tenant_id,
            order_id=tracked_order.id,
            service_date=tracked_order.service_date,
            operational_state="restricted",
            operational_reason="OUTSIDE_CUSTOMER_WINDOW",
            evaluation_ts=evaluation_ts_a,
            timezone_used="Europe/Madrid",
            rule_version="r6-operational-eval-v1",
            evidence_json={
                "window_type": "same_day",
                "window_start": "08:00:00",
                "window_end": "09:00:00",
                "lead_hours_required": 0,
                "created_local": "2026-01-01T08:00:00+00:00",
                "service_local": "2026-01-02T00:00:00+00:00",
                "timezone_source": "zone",
            },
        )
    )
    db_session.add(
        OrderOperationalSnapshot(
            id=snapshot_id_a,
            tenant_id=tracked_order.tenant_id,
            order_id=tracked_order.id,
            service_date=tracked_order.service_date,
            operational_state="eligible",
            operational_reason=None,
            evaluation_ts=evaluation_ts_a,
            timezone_used="Europe/Madrid",
            rule_version="r6-operational-eval-v1",
            evidence_json={
                "window_type": "none",
                "window_start": None,
                "window_end": None,
                "lead_hours_required": 0,
                "created_local": "2026-01-01T08:00:00+00:00",
                "service_local": "2026-01-02T00:00:00+00:00",
                "timezone_source": "zone",
            },
        )
    )
    db_session.add(
        OrderOperationalSnapshot(
            id=snapshot_id_c,
            tenant_id=tracked_order.tenant_id,
            order_id=tracked_order.id,
            service_date=tracked_order.service_date,
            operational_state="restricted",
            operational_reason="INSUFFICIENT_LEAD_TIME",
            evaluation_ts=evaluation_ts_c,
            timezone_used="Europe/Madrid",
            rule_version="r6-operational-eval-v1",
            evidence_json={
                "window_type": "none",
                "window_start": None,
                "window_end": None,
                "lead_hours_required": 6,
                "created_local": "2026-01-01T08:00:00+00:00",
                "service_local": "2026-01-02T00:00:00+00:00",
                "timezone_source": "zone",
            },
        )
    )
    db_session.commit()

    response = client.get(
        f"/orders/{order_id}/operational-snapshots",
        params={"limit": 10},
        headers=auth_headers(office_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["order_id"] == str(order_id)
    assert body["service_date"] == service_date
    assert body["total"] == 3
    assert [item["id"] for item in body["items"]] == [
        str(snapshot_id_a),
        str(snapshot_id_b),
        str(snapshot_id_c),
    ]
    assert body["items"][0]["operational_state"] == "eligible"
    assert body["items"][1]["operational_reason"] == "OUTSIDE_CUSTOMER_WINDOW"
    assert body["items"][2]["operational_reason"] == "INSUFFICIENT_LEAD_TIME"

    db_session.expire_all()
    tracked_order_after = db_session.scalar(select(Order).where(Order.id == UUID(str(order_id))))
    assert tracked_order_after is not None
    assert tracked_order_after.status == status_before


def test_order_operational_snapshots_timeline_is_tenant_isolated(client, db_session):
    now = datetime.now(UTC)
    tenant_b = Tenant(
        name="Tenant B Snapshot Timeline",
        slug=f"tenant-b-snapshot-timeline-{uuid4()}",
        default_cutoff_time=time(10, 0),
        default_timezone="Europe/Madrid",
        auto_lock_enabled=False,
        created_at=now,
    )
    db_session.add(tenant_b)
    db_session.flush()

    user_b = User(
        tenant_id=tenant_b.id,
        email=f"office+{uuid4()}@tenantb-snapshot-timeline.cortecero.app",
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
        name="Zona Tenant B Snapshot Timeline",
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
        name="Cliente Tenant B Snapshot Timeline",
        priority=0,
        cutoff_override_time=None,
        active=True,
        created_at=now,
    )
    db_session.add(customer_b)
    db_session.flush()

    service_date = date.fromisoformat(far_future_service_date(9700))
    order_b = Order(
        tenant_id=tenant_b.id,
        customer_id=customer_b.id,
        zone_id=zone_b.id,
        external_ref=f"TL-TENANT-B-{uuid4()}",
        requested_date=None,
        service_date=service_date,
        created_at=now,
        status=OrderStatus.ready_for_planning,
        is_late=False,
        lateness_reason=None,
        effective_cutoff_at=now,
        source_channel=SourceChannel.office,
        intake_type=OrderIntakeType.new_order,
        ingested_at=now,
        updated_at=now,
    )
    db_session.add(order_b)
    db_session.flush()

    db_session.add(
        OrderOperationalSnapshot(
            tenant_id=tenant_b.id,
            order_id=order_b.id,
            service_date=order_b.service_date,
            operational_state="restricted",
            operational_reason="CUSTOMER_NOT_ACCEPTING_ORDERS",
            evaluation_ts=now,
            timezone_used="UTC",
            rule_version="r6-operational-eval-v1",
            evidence_json={
                "window_type": "none",
                "window_start": None,
                "window_end": None,
                "lead_hours_required": 0,
                "created_local": now.isoformat(),
                "service_local": now.isoformat(),
                "timezone_source": "zone",
            },
        )
    )
    db_session.commit()

    demo_office_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )
    forbidden_response = client.get(
        f"/orders/{order_b.id}/operational-snapshots",
        headers=auth_headers(demo_office_token),
    )
    assert forbidden_response.status_code == 404, forbidden_response.text
    assert forbidden_response.json()["detail"]["code"] == "ORDER_NOT_FOUND"


def test_order_operational_snapshots_timeline_validates_limit(client):
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

    service_date = far_future_service_date(9800)
    customer_id = _first_customer_id(client, admin_token)
    order_id = create_order(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="SNAP-TL-LIMIT",
        service_date=service_date,
        created_at=f"{service_date}T08:00:00Z",
    )

    response = client.get(
        f"/orders/{order_id}/operational-snapshots",
        params={"limit": 0},
        headers=auth_headers(office_token),
    )
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["detail"]["code"] == "INVALID_OPERATIONAL_FILTER"
