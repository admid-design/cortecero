import uuid
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import func, select, text

from app.models import (
    Customer,
    CustomerOperationalProfile,
    Order,
    OrderOperationalSnapshot,
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


def _set_not_accepting_profile(client, token: str, customer_id: str) -> None:
    res = client.put(
        f"/admin/customers/{customer_id}/operational-profile",
        json={
            "accept_orders": False,
            "window_start": None,
            "window_end": None,
            "min_lead_hours": 0,
            "consolidate_by_default": False,
            "ops_note": "R6-BE-002 snapshot test",
        },
        headers=auth_headers(token),
    )
    assert res.status_code == 200, res.text


def test_operational_snapshot_run_is_idempotent_and_audited(client, db_session):
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

    tenant = db_session.scalar(select(Tenant).where(Tenant.slug == "demo-cortecero"))
    assert tenant is not None

    customer_id = _first_customer_id(client, admin_token)
    _set_not_accepting_profile(client, admin_token, customer_id)

    service_date = far_future_service_date(9300)
    order_id = create_order(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="SNAP-IDEMP",
        service_date=service_date,
        created_at=f"{service_date}T08:00:00Z",
    )

    order_before = db_session.scalar(select(Order).where(Order.id == uuid.UUID(str(order_id))))
    assert order_before is not None
    status_before = order_before.status

    first_run = client.post(
        "/orders/operational-snapshots/run",
        params={"service_date": service_date},
        headers=auth_headers(admin_token),
    )
    assert first_run.status_code == 200, first_run.text
    first_body = first_run.json()
    assert first_body["rule_version"] == "r6-operational-eval-v1"
    assert first_body["considered_orders"] >= 1
    assert first_body["generated_snapshots"] >= 1

    snapshot = db_session.scalar(
        select(OrderOperationalSnapshot).where(
            OrderOperationalSnapshot.tenant_id == tenant.id,
            OrderOperationalSnapshot.order_id == uuid.UUID(str(order_id)),
            OrderOperationalSnapshot.service_date == date.fromisoformat(service_date),
            OrderOperationalSnapshot.rule_version == "r6-operational-eval-v1",
        )
    )
    assert snapshot is not None
    assert snapshot.operational_state == "restricted"
    assert snapshot.operational_reason == "CUSTOMER_NOT_ACCEPTING_ORDERS"
    for required_key in [
        "window_type",
        "window_start",
        "window_end",
        "lead_hours_required",
        "created_local",
        "service_local",
        "timezone_source",
    ]:
        assert required_key in snapshot.evidence_json

    second_run = client.post(
        "/orders/operational-snapshots/run",
        params={"service_date": service_date},
        headers=auth_headers(admin_token),
    )
    assert second_run.status_code == 200, second_run.text
    second_body = second_run.json()
    assert second_body["considered_orders"] == first_body["considered_orders"]
    first_bucket_start = datetime.fromisoformat(first_body["evaluation_ts_bucket"]).astimezone(UTC)
    first_bucket_end = first_bucket_start + timedelta(hours=1)
    second_bucket_start = datetime.fromisoformat(second_body["evaluation_ts_bucket"]).astimezone(UTC)

    if second_bucket_start == first_bucket_start:
        assert second_body["generated_snapshots"] == 0
        assert second_body["skipped_existing"] >= 1
        bucket_count = db_session.scalar(
            select(func.count(OrderOperationalSnapshot.id)).where(
                OrderOperationalSnapshot.tenant_id == tenant.id,
                OrderOperationalSnapshot.order_id == uuid.UUID(str(order_id)),
                OrderOperationalSnapshot.rule_version == "r6-operational-eval-v1",
                OrderOperationalSnapshot.evaluation_ts >= first_bucket_start,
                OrderOperationalSnapshot.evaluation_ts < first_bucket_end,
            )
        )
        assert bucket_count == 1
    else:
        # If the second call crosses an hour boundary, idempotency key changes by design.
        assert second_body["generated_snapshots"] >= 1

    db_session.expire_all()
    order_after = db_session.scalar(select(Order).where(Order.id == uuid.UUID(str(order_id))))
    assert order_after is not None
    assert order_after.status == status_before

    audit_count = db_session.execute(
        text(
            """
            SELECT count(*)
            FROM audit_logs
            WHERE tenant_id = :tenant_id
              AND entity_type = 'tenant'
              AND action = 'operational_snapshot_generated'
              AND metadata_json->>'service_date' = :service_date
            """
        ),
        {"tenant_id": str(tenant.id), "service_date": service_date},
    ).scalar_one()
    assert audit_count == 2


def test_operational_snapshot_run_is_tenant_isolated(client, db_session):
    now = datetime.now(UTC)
    service_date = far_future_service_date(9400)

    tenant_b = Tenant(
        name="Tenant B Snapshots",
        slug="tenant-b-snapshots",
        default_cutoff_time=time(10, 0),
        default_timezone="Europe/Madrid",
        auto_lock_enabled=False,
        created_at=now,
    )
    db_session.add(tenant_b)
    db_session.flush()

    admin_b = User(
        tenant_id=tenant_b.id,
        email="admin@tenantb-snapshots.cortecero.app",
        full_name="Tenant B Admin",
        password_hash=hash_password("adminb123"),
        role=UserRole.admin,
        is_active=True,
        created_at=now,
    )
    office_b = User(
        tenant_id=tenant_b.id,
        email="office@tenantb-snapshots.cortecero.app",
        full_name="Tenant B Office",
        password_hash=hash_password("officeb123"),
        role=UserRole.office,
        is_active=True,
        created_at=now,
    )
    db_session.add(admin_b)
    db_session.add(office_b)
    db_session.flush()

    zone_b = Zone(
        tenant_id=tenant_b.id,
        name="Zona Tenant B Snapshots",
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
        name="Cliente Tenant B Snapshots",
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

    office_b_token = login_as(
        client,
        tenant_slug="tenant-b-snapshots",
        email="office@tenantb-snapshots.cortecero.app",
        password="officeb123",
    )
    _ = create_order(
        client,
        office_b_token,
        customer_id=str(customer_b.id),
        external_ref_prefix="TENANTB-SNAPSHOT",
        service_date=service_date,
        created_at=f"{service_date}T06:00:00Z",
    )

    demo_admin_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="admin@demo.cortecero.app",
        password="admin123",
    )
    demo_run = client.post(
        "/orders/operational-snapshots/run",
        params={"service_date": service_date},
        headers=auth_headers(demo_admin_token),
    )
    assert demo_run.status_code == 200, demo_run.text
    assert demo_run.json()["considered_orders"] == 0
    assert demo_run.json()["generated_snapshots"] == 0

    admin_b_token = login_as(
        client,
        tenant_slug="tenant-b-snapshots",
        email="admin@tenantb-snapshots.cortecero.app",
        password="adminb123",
    )
    tenant_b_run = client.post(
        "/orders/operational-snapshots/run",
        params={"service_date": service_date},
        headers=auth_headers(admin_b_token),
    )
    assert tenant_b_run.status_code == 200, tenant_b_run.text
    assert tenant_b_run.json()["considered_orders"] == 1
    assert tenant_b_run.json()["generated_snapshots"] == 1


def test_operational_snapshot_run_requires_admin_role(client):
    logistics_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )

    res = client.post(
        "/orders/operational-snapshots/run",
        params={"service_date": far_future_service_date(9500)},
        headers=auth_headers(logistics_token),
    )
    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail["code"] == "RBAC_FORBIDDEN"
