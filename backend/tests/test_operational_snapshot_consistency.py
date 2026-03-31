from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.models import (
    Order,
    OrderOperationalSnapshot,
    Tenant,
    Zone,
)
from app.routers import orders as orders_router
from tests.helpers import auth_headers, create_order, far_future_service_date, login_as


def _zone_and_customers(client, token: str) -> tuple[str, list[str]]:
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
    response = client.put(
        f"/admin/customers/{customer_id}/operational-profile",
        json={
            "accept_orders": accept_orders,
            "window_start": window_start,
            "window_end": window_end,
            "min_lead_hours": min_lead_hours,
            "consolidate_by_default": False,
            "ops_note": "R6-QA-002 profile",
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text


def test_operational_snapshot_matches_current_evaluation(client, db_session):
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
    restricted_customer_id, eligible_customer_id = customer_ids[:2]

    zone = db_session.scalar(select(Zone).where(Zone.id == UUID(zone_id)))
    assert zone is not None
    zone.timezone = "UTC"
    db_session.commit()

    _put_profile(
        client,
        admin_token,
        restricted_customer_id,
        accept_orders=False,
        window_start=None,
        window_end=None,
        min_lead_hours=0,
    )
    _put_profile(
        client,
        admin_token,
        eligible_customer_id,
        accept_orders=True,
        window_start=None,
        window_end=None,
        min_lead_hours=0,
    )

    service_date = far_future_service_date(9900)
    restricted_order_id = create_order(
        client,
        office_token,
        customer_id=restricted_customer_id,
        external_ref_prefix="SNAP-CONS-REST",
        service_date=service_date,
        created_at=f"{service_date}T08:00:00Z",
    )
    eligible_order_id = create_order(
        client,
        office_token,
        customer_id=eligible_customer_id,
        external_ref_prefix="SNAP-CONS-ELIG",
        service_date=service_date,
        created_at=f"{service_date}T08:10:00Z",
    )

    tracked_ids = [UUID(restricted_order_id), UUID(eligible_order_id)]
    status_before = {
        row.id: row.status
        for row in db_session.scalars(select(Order).where(Order.id.in_(tracked_ids))).all()
    }

    orders_res = client.get(
        "/orders",
        params={"service_date": service_date, "zone_id": zone_id},
        headers=auth_headers(office_token),
    )
    assert orders_res.status_code == 200, orders_res.text
    listed = {row["id"]: row for row in orders_res.json()["items"] if row["id"] in {restricted_order_id, eligible_order_id}}
    assert len(listed) == 2

    run_res = client.post(
        "/orders/operational-snapshots/run",
        params={"service_date": service_date},
        headers=auth_headers(admin_token),
    )
    assert run_res.status_code == 200, run_res.text
    assert run_res.json()["considered_orders"] >= 2

    for order_id in [restricted_order_id, eligible_order_id]:
        timeline_res = client.get(
            f"/orders/{order_id}/operational-snapshots",
            headers=auth_headers(office_token),
        )
        assert timeline_res.status_code == 200, timeline_res.text
        timeline_body = timeline_res.json()
        assert timeline_body["total"] >= 1
        latest_snapshot = timeline_body["items"][-1]
        current = listed[order_id]

        assert latest_snapshot["operational_state"] == current["operational_state"]
        assert latest_snapshot["operational_reason"] == current["operational_reason"]
        assert latest_snapshot["timezone_used"] == current["operational_explanation"]["timezone_used"]
        assert latest_snapshot["rule_version"] == current["operational_explanation"]["rule_version"]
        assert latest_snapshot["evidence_json"]["timezone_source"] == current["operational_explanation"]["timezone_source"]

    db_session.expire_all()
    status_after = {
        row.id: row.status
        for row in db_session.scalars(select(Order).where(Order.id.in_(tracked_ids))).all()
    }
    assert status_after == status_before


def test_operational_snapshot_batch_run_is_idempotent_in_same_bucket(client, db_session, monkeypatch):
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
    customer_id = customer_ids[0]

    zone = db_session.scalar(select(Zone).where(Zone.id == UUID(zone_id)))
    assert zone is not None
    zone.timezone = "UTC"
    db_session.commit()

    _put_profile(
        client,
        admin_token,
        customer_id,
        accept_orders=False,
        window_start=None,
        window_end=None,
        min_lead_hours=0,
    )

    service_date = far_future_service_date(9910)
    created_ids = [
        create_order(
            client,
            office_token,
            customer_id=customer_id,
            external_ref_prefix=f"SNAP-BATCH-{idx}",
            service_date=service_date,
            created_at=f"{service_date}T08:{idx:02d}:00Z",
        )
        for idx in (1, 2, 3)
    ]

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            fixed = datetime(2026, 5, 1, 10, 30, tzinfo=UTC)
            return fixed if tz else fixed.replace(tzinfo=None)

    monkeypatch.setattr(orders_router, "datetime", _FrozenDatetime)

    first_run = client.post(
        "/orders/operational-snapshots/run",
        params={"service_date": service_date},
        headers=auth_headers(admin_token),
    )
    assert first_run.status_code == 200, first_run.text
    first_body = first_run.json()

    second_run = client.post(
        "/orders/operational-snapshots/run",
        params={"service_date": service_date},
        headers=auth_headers(admin_token),
    )
    assert second_run.status_code == 200, second_run.text
    second_body = second_run.json()

    assert first_body["evaluation_ts_bucket"] == second_body["evaluation_ts_bucket"]
    assert first_body["considered_orders"] == 3
    assert first_body["generated_snapshots"] == 3
    assert first_body["skipped_existing"] == 0
    assert second_body["considered_orders"] == 3
    assert second_body["generated_snapshots"] == 0
    assert second_body["skipped_existing"] == 3
    assert second_body["generated_snapshot_ids"] == []

    tenant = db_session.scalar(select(Tenant).where(Tenant.slug == "demo-cortecero"))
    assert tenant is not None
    snapshot_rows = list(
        db_session.scalars(
            select(OrderOperationalSnapshot).where(
                OrderOperationalSnapshot.tenant_id == tenant.id,
                OrderOperationalSnapshot.order_id.in_([UUID(item) for item in created_ids]),
                OrderOperationalSnapshot.service_date == datetime.fromisoformat(service_date).date(),
                OrderOperationalSnapshot.rule_version == "r6-operational-eval-v1",
            )
        )
    )
    assert len(snapshot_rows) == 3
    assert {str(row.order_id) for row in snapshot_rows} == set(created_ids)
