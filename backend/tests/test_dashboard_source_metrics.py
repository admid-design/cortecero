import uuid
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
from tests.helpers import auth_headers, far_future_service_date, login_as, pick_customer_id_for_zone


def _create_order_with_channel(
    client,
    token: str,
    *,
    customer_id: str,
    service_date: str,
    source_channel: str,
    late: bool,
) -> str:
    created_at = f"{service_date}T23:59:59Z" if late else "2000-01-01T00:00:00Z"
    payload = {
        "orders": [
            {
                "customer_id": customer_id,
                "external_ref": f"SRC-{source_channel}-{uuid.uuid4()}",
                "service_date": service_date,
                "created_at": created_at,
                "source_channel": source_channel,
                "lines": [{"sku": f"SKU-{source_channel}", "qty": 1}],
            }
        ]
    }
    res = client.post("/ingestion/orders", json=payload, headers=auth_headers(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["created"] == 1
    return body["items"][0]["order_id"]


def _items_by_channel(body: dict) -> dict[str, dict]:
    return {item["source_channel"]: item for item in body["items"]}


def test_source_metrics_calculation_and_order(client):
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
    zone_a_id = zones[0]["id"]
    zone_b_id = zones[1]["id"]

    customer_a_id = pick_customer_id_for_zone(client, office_token, zone_a_id)
    customer_b_id = pick_customer_id_for_zone(client, office_token, zone_b_id)

    in_range_date = far_future_service_date(6000)
    out_range_date = far_future_service_date(6010)

    sales_late_order_id = _create_order_with_channel(
        client,
        office_token,
        customer_id=customer_a_id,
        service_date=in_range_date,
        source_channel="sales",
        late=True,
    )
    _create_order_with_channel(
        client,
        office_token,
        customer_id=customer_a_id,
        service_date=in_range_date,
        source_channel="sales",
        late=False,
    )
    _create_order_with_channel(
        client,
        office_token,
        customer_id=customer_a_id,
        service_date=in_range_date,
        source_channel="office",
        late=False,
    )
    direct_late_order_id = _create_order_with_channel(
        client,
        office_token,
        customer_id=customer_b_id,
        service_date=in_range_date,
        source_channel="direct_customer",
        late=True,
    )
    _create_order_with_channel(
        client,
        office_token,
        customer_id=customer_a_id,
        service_date=out_range_date,
        source_channel="hotel_direct",
        late=False,
    )

    create_approved_exc = client.post(
        "/exceptions",
        json={"order_id": sales_late_order_id, "type": "late_order", "note": "approved by source metrics test"},
        headers=auth_headers(office_token),
    )
    assert create_approved_exc.status_code == 201, create_approved_exc.text
    approve_res = client.post(
        f"/exceptions/{create_approved_exc.json()['id']}/approve",
        headers=auth_headers(logistics_token),
    )
    assert approve_res.status_code == 200, approve_res.text

    create_rejected_exc = client.post(
        "/exceptions",
        json={"order_id": direct_late_order_id, "type": "late_order", "note": "rejected by source metrics test"},
        headers=auth_headers(office_token),
    )
    assert create_rejected_exc.status_code == 201, create_rejected_exc.text
    reject_res = client.post(
        f"/exceptions/{create_rejected_exc.json()['id']}/reject",
        json={"note": "not applicable"},
        headers=auth_headers(logistics_token),
    )
    assert reject_res.status_code == 200, reject_res.text

    res = client.get(
        "/dashboard/source-metrics",
        params={"date_from": in_range_date, "date_to": in_range_date},
        headers=auth_headers(office_token),
    )
    assert res.status_code == 200, res.text
    body = res.json()

    assert [item["source_channel"] for item in body["items"]] == [
        "sales",
        "office",
        "direct_customer",
        "hotel_direct",
        "other",
    ]

    by_channel = _items_by_channel(body)
    assert by_channel["sales"]["total_orders"] == 2
    assert by_channel["sales"]["late_orders"] == 1
    assert by_channel["sales"]["late_rate"] == 0.5
    assert by_channel["sales"]["approved_exceptions"] == 1
    assert by_channel["sales"]["rejected_exceptions"] == 0

    assert by_channel["office"]["total_orders"] == 1
    assert by_channel["office"]["late_orders"] == 0
    assert by_channel["office"]["late_rate"] == 0.0
    assert by_channel["office"]["approved_exceptions"] == 0
    assert by_channel["office"]["rejected_exceptions"] == 0

    assert by_channel["direct_customer"]["total_orders"] == 1
    assert by_channel["direct_customer"]["late_orders"] == 1
    assert by_channel["direct_customer"]["late_rate"] == 1.0
    assert by_channel["direct_customer"]["approved_exceptions"] == 0
    assert by_channel["direct_customer"]["rejected_exceptions"] == 1

    assert by_channel["hotel_direct"]["total_orders"] == 0
    assert by_channel["hotel_direct"]["late_orders"] == 0
    assert by_channel["hotel_direct"]["late_rate"] == 0.0
    assert by_channel["hotel_direct"]["approved_exceptions"] == 0
    assert by_channel["hotel_direct"]["rejected_exceptions"] == 0

    assert by_channel["other"]["total_orders"] == 0
    assert by_channel["other"]["late_orders"] == 0
    assert by_channel["other"]["late_rate"] == 0.0
    assert by_channel["other"]["approved_exceptions"] == 0
    assert by_channel["other"]["rejected_exceptions"] == 0

    zone_filtered_res = client.get(
        "/dashboard/source-metrics",
        params={"date_from": in_range_date, "date_to": in_range_date, "zone_id": zone_a_id},
        headers=auth_headers(office_token),
    )
    assert zone_filtered_res.status_code == 200, zone_filtered_res.text
    by_channel_zone = _items_by_channel(zone_filtered_res.json())
    assert by_channel_zone["direct_customer"]["total_orders"] == 0
    assert by_channel_zone["direct_customer"]["late_orders"] == 0
    assert by_channel_zone["direct_customer"]["rejected_exceptions"] == 0
    assert by_channel_zone["sales"]["total_orders"] == 2
    assert by_channel_zone["office"]["total_orders"] == 1


def test_source_metrics_is_tenant_isolated(client, db_session):
    service_date = date(2100, 1, 2)
    now = datetime.now(UTC)

    tenant_b = Tenant(
        name="Tenant B Source Metrics",
        slug="tenant-b-source-metrics",
        default_cutoff_time=datetime.strptime("10:00", "%H:%M").time(),
        default_timezone="Europe/Madrid",
        auto_lock_enabled=False,
        created_at=now,
    )
    db_session.add(tenant_b)
    db_session.flush()

    tenant_b_user = User(
        tenant_id=tenant_b.id,
        email="office@tenantb-source.cortecero.app",
        full_name="Tenant B Office",
        password_hash=hash_password("officeb123"),
        role=UserRole.office,
        is_active=True,
        created_at=now,
    )
    db_session.add(tenant_b_user)
    db_session.flush()

    tenant_b_zone = Zone(
        tenant_id=tenant_b.id,
        name="Zona Tenant B Source",
        default_cutoff_time=datetime.strptime("09:00", "%H:%M").time(),
        timezone="Europe/Madrid",
        active=True,
        created_at=now,
    )
    db_session.add(tenant_b_zone)
    db_session.flush()

    tenant_b_customer = Customer(
        tenant_id=tenant_b.id,
        zone_id=tenant_b_zone.id,
        name="Cliente Tenant B Source",
        priority=0,
        cutoff_override_time=None,
        active=True,
        created_at=now,
    )
    db_session.add(tenant_b_customer)
    db_session.flush()

    db_session.add(
        Order(
            tenant_id=tenant_b.id,
            customer_id=tenant_b_customer.id,
            zone_id=tenant_b_zone.id,
            external_ref="TENANTB-SOURCE-001",
            requested_date=service_date,
            service_date=service_date,
            created_at=now,
            status=OrderStatus.ready_for_planning,
            is_late=False,
            lateness_reason=None,
            effective_cutoff_at=now,
            source_channel=SourceChannel.other,
            intake_type=OrderIntakeType.new_order,
            ingested_at=now,
            updated_at=now,
        )
    )
    db_session.commit()

    demo_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )
    demo_res = client.get(
        "/dashboard/source-metrics",
        params={"date_from": service_date.isoformat(), "date_to": service_date.isoformat()},
        headers=auth_headers(demo_token),
    )
    assert demo_res.status_code == 200, demo_res.text
    by_channel_demo = _items_by_channel(demo_res.json())
    assert by_channel_demo["other"]["total_orders"] == 0

    tenant_b_token = login_as(
        client,
        tenant_slug="tenant-b-source-metrics",
        email="office@tenantb-source.cortecero.app",
        password="officeb123",
    )
    tenant_b_res = client.get(
        "/dashboard/source-metrics",
        params={"date_from": service_date.isoformat(), "date_to": service_date.isoformat()},
        headers=auth_headers(tenant_b_token),
    )
    assert tenant_b_res.status_code == 200, tenant_b_res.text
    by_channel_tenant_b = _items_by_channel(tenant_b_res.json())
    assert by_channel_tenant_b["other"]["total_orders"] == 1
    assert by_channel_tenant_b["other"]["late_orders"] == 0
    assert by_channel_tenant_b["other"]["late_rate"] == 0.0


def test_source_metrics_range_validation_and_empty_range(client):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )

    invalid_res = client.get(
        "/dashboard/source-metrics",
        params={"date_from": "2100-01-10", "date_to": "2100-01-01"},
        headers=auth_headers(token),
    )
    assert invalid_res.status_code == 422
    assert invalid_res.json()["detail"]["code"] == "SOURCE_METRICS_RANGE_INVALID"

    empty_res = client.get(
        "/dashboard/source-metrics",
        params={"date_from": "2100-02-01", "date_to": "2100-02-01"},
        headers=auth_headers(token),
    )
    assert empty_res.status_code == 200, empty_res.text
    items = empty_res.json()["items"]
    assert len(items) == 5
    for item in items:
        assert item["total_orders"] == 0
        assert item["late_orders"] == 0
        assert item["late_rate"] == 0.0
        assert item["approved_exceptions"] == 0
        assert item["rejected_exceptions"] == 0
