import csv
import io
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

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
from tests.helpers import auth_headers, create_order, far_future_service_date, login_as


def _first_zone_and_customer(client, token: str) -> tuple[str, str]:
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
    assert customers
    return zone_id, customers[0]["id"]


def test_operational_dataset_export_pagination_plan_metrics_and_no_status_mutation(client, db_session):
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

    zone = db_session.scalar(select(Zone).where(Zone.id == uuid.UUID(zone_id)))
    assert zone is not None
    zone.timezone = "UTC"
    db_session.commit()

    service_date = date.fromisoformat(far_future_service_date(7600))
    previous_day = service_date - timedelta(days=1)

    order_a = create_order(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="EXP-A",
        service_date=service_date.isoformat(),
        created_at=f"{previous_day.isoformat()}T06:00:00Z",
    )
    order_b = create_order(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="EXP-B",
        service_date=service_date.isoformat(),
        created_at=f"{previous_day.isoformat()}T06:10:00Z",
    )
    order_c = create_order(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="EXP-C",
        service_date=service_date.isoformat(),
        created_at=f"{previous_day.isoformat()}T06:20:00Z",
    )

    set_weight_res = client.patch(
        f"/orders/{order_a}/weight",
        json={"total_weight_kg": 50},
        headers=auth_headers(admin_token),
    )
    assert set_weight_res.status_code == 200, set_weight_res.text

    plan_res = client.post(
        "/plans",
        json={"service_date": service_date.isoformat(), "zone_id": zone_id},
        headers=auth_headers(admin_token),
    )
    assert plan_res.status_code == 201, plan_res.text
    plan_id = plan_res.json()["id"]

    for order_id in [order_a, order_b]:
        include_res = client.post(
            f"/plans/{plan_id}/orders",
            json={"order_id": order_id},
            headers=auth_headers(admin_token),
        )
        assert include_res.status_code == 200, include_res.text

    tracked = [uuid.UUID(order_a), uuid.UUID(order_b), uuid.UUID(order_c)]
    status_before = {
        row.id: row.status
        for row in db_session.scalars(select(Order).where(Order.id.in_(tracked))).all()
    }

    page1_res = client.get(
        "/exports/operational-dataset",
        params={
            "date_from": service_date.isoformat(),
            "date_to": service_date.isoformat(),
            "page": 1,
            "page_size": 2,
        },
        headers=auth_headers(admin_token),
    )
    assert page1_res.status_code == 200, page1_res.text
    page1 = page1_res.json()
    assert page1["total"] == 3
    assert page1["total_pages"] == 2
    assert page1["page"] == 1
    assert page1["page_size"] == 2
    assert page1["anonymized"] is False
    assert len(page1["items"]) == 2
    assert page1["items"][0]["created_at"] <= page1["items"][1]["created_at"]

    page2_res = client.get(
        "/exports/operational-dataset",
        params={
            "date_from": service_date.isoformat(),
            "date_to": service_date.isoformat(),
            "page": 2,
            "page_size": 2,
        },
        headers=auth_headers(admin_token),
    )
    assert page2_res.status_code == 200, page2_res.text
    page2 = page2_res.json()
    assert page2["total"] == 3
    assert page2["total_pages"] == 2
    assert len(page2["items"]) == 1

    merged_items = page1["items"] + page2["items"]
    merged_ids = {item["order_id"] for item in merged_items}
    assert merged_ids == {order_a, order_b, order_c}

    planned_item = next(item for item in merged_items if item["order_id"] == order_a)
    assert planned_item["planned"] is True
    assert planned_item["plan_id"] == plan_id
    assert planned_item["plan_inclusion_type"] == "normal"
    assert planned_item["plan_status"] == "open"
    assert planned_item["plan_orders_total"] == 2
    assert planned_item["plan_orders_with_weight"] == 1
    assert planned_item["plan_orders_missing_weight"] == 1
    assert float(planned_item["plan_total_weight_kg"]) == 50.0

    db_session.expire_all()
    status_after = {
        row.id: row.status
        for row in db_session.scalars(select(Order).where(Order.id.in_(tracked))).all()
    }
    assert status_after == status_before


def test_operational_dataset_export_tenant_isolation_and_rbac(client, db_session):
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

    service_date = date(2100, 7, 1)
    now = datetime.now(UTC)

    tenant_b = Tenant(
        name="Tenant B Export",
        slug="tenant-b-export",
        default_cutoff_time=datetime.strptime("10:00", "%H:%M").time(),
        default_timezone="UTC",
        auto_lock_enabled=False,
        created_at=now,
    )
    db_session.add(tenant_b)
    db_session.flush()

    zone_b = Zone(
        tenant_id=tenant_b.id,
        name="Zona Tenant B Export",
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
        name="Cliente Tenant B Export",
        priority=0,
        cutoff_override_time=None,
        active=True,
        created_at=now,
    )
    db_session.add(customer_b)
    db_session.flush()

    order_b = Order(
        tenant_id=tenant_b.id,
        customer_id=customer_b.id,
        zone_id=zone_b.id,
        external_ref="TENANT-B-EXPORT-001",
        requested_date=service_date,
        service_date=service_date,
        created_at=datetime(2100, 6, 30, 8, 0, tzinfo=UTC),
        status=OrderStatus.ready_for_planning,
        is_late=False,
        lateness_reason=None,
        effective_cutoff_at=datetime(2100, 6, 30, 10, 0, tzinfo=UTC),
        source_channel=SourceChannel.office,
        intake_type=OrderIntakeType.new_order,
        total_weight_kg=None,
        ingested_at=now,
        updated_at=now,
    )
    db_session.add(order_b)

    user_b = User(
        tenant_id=tenant_b.id,
        email="admin@tenantb-export.cortecero.app",
        full_name="Tenant B Admin",
        password_hash=hash_password("adminb123"),
        role=UserRole.admin,
        is_active=True,
        created_at=now,
    )
    db_session.add(user_b)
    db_session.commit()

    export_res = client.get(
        "/exports/operational-dataset",
        params={"date_from": service_date.isoformat(), "date_to": service_date.isoformat()},
        headers=auth_headers(admin_token),
    )
    assert export_res.status_code == 200, export_res.text
    exported_ids = {item["order_id"] for item in export_res.json()["items"]}
    assert str(order_b.id) not in exported_ids

    forbidden_res = client.get(
        "/exports/operational-dataset",
        params={"date_from": service_date.isoformat(), "date_to": service_date.isoformat()},
        headers=auth_headers(office_token),
    )
    assert forbidden_res.status_code == 403
    assert forbidden_res.json()["detail"]["code"] == "RBAC_FORBIDDEN"


def test_operational_dataset_export_invalid_filters_and_csv_anonymized(client):
    admin_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="admin@demo.cortecero.app",
        password="admin123",
    )

    invalid_date = client.get(
        "/exports/operational-dataset",
        params={"date_from": "2100-01-02", "date_to": "2100-01-01"},
        headers=auth_headers(admin_token),
    )
    assert invalid_date.status_code == 422
    assert invalid_date.json()["detail"]["code"] == "INVALID_EXPORT_FILTER"

    invalid_format = client.get(
        "/exports/operational-dataset",
        params={"date_from": "2100-01-01", "date_to": "2100-01-02", "format": "xml"},
        headers=auth_headers(admin_token),
    )
    assert invalid_format.status_code == 422
    assert invalid_format.json()["detail"]["code"] == "INVALID_EXPORT_FILTER"

    csv_res = client.get(
        "/exports/operational-dataset",
        params={
            "date_from": "2100-01-01",
            "date_to": "2100-01-02",
            "format": "csv",
            "anonymize": True,
            "page": 1,
            "page_size": 50,
        },
        headers=auth_headers(admin_token),
    )
    assert csv_res.status_code == 200, csv_res.text
    assert csv_res.headers["content-type"].startswith("text/csv")
    assert "X-Total-Count" in csv_res.headers

    reader = csv.DictReader(io.StringIO(csv_res.text))
    row = next(reader, None)
    if row is not None:
        assert row["external_ref"].startswith("order-")
        assert row["customer_name"].startswith("customer-")
        assert row["zone_name"].startswith("zone-")
