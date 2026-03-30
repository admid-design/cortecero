from datetime import UTC, date, datetime

from app.models import (
    Customer,
    Order,
    OrderIntakeType,
    OrderStatus,
    SourceChannel,
    Tenant,
    User,
    UserRole,
    Zone,
)
from app.security import hash_password
from tests.helpers import auth_headers, create_order, far_future_service_date, login_as, pick_customer_id_for_zone


def test_pending_queue_inclusion_and_deterministic_order(client):
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

    zones_res = client.get("/admin/zones", headers=auth_headers(office_token))
    assert zones_res.status_code == 200, zones_res.text
    zones = zones_res.json()["items"]
    assert len(zones) >= 2
    open_zone_id = zones[0]["id"]
    locked_zone_id = zones[1]["id"]

    open_customer_id = pick_customer_id_for_zone(client, office_token, open_zone_id)
    locked_customer_id = pick_customer_id_for_zone(client, office_token, locked_zone_id)

    service_date = far_future_service_date(5000)

    open_plan_res = client.post(
        "/plans",
        json={"service_date": service_date, "zone_id": open_zone_id},
        headers=auth_headers(logistics_token),
    )
    assert open_plan_res.status_code == 201, open_plan_res.text

    locked_plan_res = client.post(
        "/plans",
        json={"service_date": service_date, "zone_id": locked_zone_id},
        headers=auth_headers(logistics_token),
    )
    assert locked_plan_res.status_code == 201, locked_plan_res.text
    locked_plan_id = locked_plan_res.json()["id"]

    lock_res = client.post(f"/plans/{locked_plan_id}/lock", headers=auth_headers(logistics_token))
    assert lock_res.status_code == 200, lock_res.text

    late_order_id = create_order(
        client,
        office_token,
        customer_id=open_customer_id,
        external_ref_prefix="PQ-LATE",
        service_date=service_date,
        created_at=f"{service_date}T23:59:59Z",
        sku="SKU-PQ-LATE",
    )

    locked_exception_required_id = create_order(
        client,
        office_token,
        customer_id=locked_customer_id,
        external_ref_prefix="PQ-LOCKED",
        service_date=service_date,
        created_at="2000-01-01T00:00:00Z",
        sku="SKU-PQ-LOCKED",
    )

    rejected_order_id = create_order(
        client,
        office_token,
        customer_id=open_customer_id,
        external_ref_prefix="PQ-REJECT",
        service_date=service_date,
        created_at=f"{service_date}T22:00:00Z",
        sku="SKU-PQ-REJECT",
    )

    approved_order_id = create_order(
        client,
        office_token,
        customer_id=open_customer_id,
        external_ref_prefix="PQ-APPROVED",
        service_date=service_date,
        created_at=f"{service_date}T21:00:00Z",
        sku="SKU-PQ-APPROVED",
    )

    eligible_open_order_id = create_order(
        client,
        office_token,
        customer_id=open_customer_id,
        external_ref_prefix="PQ-ELIGIBLE",
        service_date=service_date,
        created_at="2000-01-01T00:00:00Z",
        sku="SKU-PQ-ELIGIBLE",
    )

    create_exc_res = client.post(
        "/exceptions",
        json={"order_id": rejected_order_id, "type": "late_order", "note": "pending queue reject test"},
        headers=auth_headers(office_token),
    )
    assert create_exc_res.status_code == 201, create_exc_res.text
    exc_id = create_exc_res.json()["id"]

    reject_res = client.post(
        f"/exceptions/{exc_id}/reject",
        json={"note": "no aplica"},
        headers=auth_headers(logistics_token),
    )
    assert reject_res.status_code == 200, reject_res.text

    create_approved_exc_res = client.post(
        "/exceptions",
        json={"order_id": approved_order_id, "type": "late_order", "note": "pending queue approve test"},
        headers=auth_headers(office_token),
    )
    assert create_approved_exc_res.status_code == 201, create_approved_exc_res.text
    approved_exc_id = create_approved_exc_res.json()["id"]

    approve_res = client.post(
        f"/exceptions/{approved_exc_id}/approve",
        headers=auth_headers(logistics_token),
    )
    assert approve_res.status_code == 200, approve_res.text

    queue_res = client.get(
        "/orders/pending-queue",
        params={"service_date": service_date},
        headers=auth_headers(office_token),
    )
    assert queue_res.status_code == 200, queue_res.text
    queue_items = queue_res.json()["items"]
    queue_ids = [item["order_id"] for item in queue_items]

    assert str(eligible_open_order_id) not in queue_ids
    assert str(approved_order_id) not in queue_ids
    assert set(queue_ids) == {str(late_order_id), str(locked_exception_required_id), str(rejected_order_id)}

    by_id = {item["order_id"]: item for item in queue_items}
    assert by_id[str(late_order_id)]["reason"] == "LATE_PENDING_EXCEPTION"
    assert by_id[str(locked_exception_required_id)]["reason"] == "LOCKED_PLAN_EXCEPTION_REQUIRED"
    assert by_id[str(rejected_order_id)]["reason"] == "EXCEPTION_REJECTED"

    reason_order = [item["reason"] for item in queue_items]
    assert reason_order == [
        "LOCKED_PLAN_EXCEPTION_REQUIRED",
        "LATE_PENDING_EXCEPTION",
        "EXCEPTION_REJECTED",
    ]

    reason_filter_res = client.get(
        "/orders/pending-queue",
        params={"service_date": service_date, "reason": "EXCEPTION_REJECTED"},
        headers=auth_headers(office_token),
    )
    assert reason_filter_res.status_code == 200, reason_filter_res.text
    filtered_items = reason_filter_res.json()["items"]
    assert len(filtered_items) == 1
    assert filtered_items[0]["order_id"] == str(rejected_order_id)
    assert filtered_items[0]["reason"] == "EXCEPTION_REJECTED"


def test_pending_queue_is_tenant_isolated(client, db_session):
    service_date = date(2100, 1, 1)
    now = datetime.now(UTC)

    tenant_b = Tenant(
        name="Tenant B Pending Queue",
        slug="tenant-b-pending-queue",
        default_cutoff_time=datetime.strptime("10:00", "%H:%M").time(),
        default_timezone="Europe/Madrid",
        auto_lock_enabled=False,
        created_at=now,
    )
    db_session.add(tenant_b)
    db_session.flush()

    user_b = User(
        tenant_id=tenant_b.id,
        email="office@tenantb-pending.cortecero.app",
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
        name="Zona Tenant B Pending",
        default_cutoff_time=datetime.strptime("09:00", "%H:%M").time(),
        timezone="Europe/Madrid",
        active=True,
        created_at=now,
    )
    db_session.add(zone_b)
    db_session.flush()

    customer_b = Customer(
        tenant_id=tenant_b.id,
        zone_id=zone_b.id,
        name="Cliente Tenant B Pending",
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
        external_ref="TENANTB-PQ-001",
        requested_date=service_date,
        service_date=service_date,
        created_at=now,
        status=OrderStatus.late_pending_exception,
        is_late=True,
        lateness_reason="created_after_cutoff",
        effective_cutoff_at=now,
        source_channel=SourceChannel.office,
        intake_type=OrderIntakeType.new_order,
        ingested_at=now,
        updated_at=now,
    )
    db_session.add(tenant_b_order)
    db_session.commit()

    demo_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )
    demo_queue_res = client.get(
        "/orders/pending-queue",
        params={"service_date": service_date.isoformat()},
        headers=auth_headers(demo_token),
    )
    assert demo_queue_res.status_code == 200, demo_queue_res.text
    demo_refs = {item["external_ref"] for item in demo_queue_res.json()["items"]}
    assert "TENANTB-PQ-001" not in demo_refs

    tenant_b_token = login_as(
        client,
        tenant_slug="tenant-b-pending-queue",
        email="office@tenantb-pending.cortecero.app",
        password="officeb123",
    )
    tenant_b_queue_res = client.get(
        "/orders/pending-queue",
        params={"service_date": service_date.isoformat()},
        headers=auth_headers(tenant_b_token),
    )
    assert tenant_b_queue_res.status_code == 200, tenant_b_queue_res.text
    tenant_b_refs = {item["external_ref"] for item in tenant_b_queue_res.json()["items"]}
    assert "TENANTB-PQ-001" in tenant_b_refs
