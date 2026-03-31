import uuid
from datetime import date

from sqlalchemy import select

from app.models import Zone
from app.routers.orders import _resolve_timezone
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
            "ops_note": "R6-QA-001 temporal matrix",
        },
        headers=auth_headers(token),
    )
    assert res.status_code == 200, res.text


def _set_zone_timezone(db_session, zone_id: str, timezone: str) -> None:
    zone = db_session.scalar(select(Zone).where(Zone.id == uuid.UUID(zone_id)))
    assert zone is not None
    zone.timezone = timezone
    db_session.commit()


def _create_and_fetch_operational(
    client,
    office_token: str,
    *,
    customer_id: str,
    external_ref_prefix: str,
    service_date: str,
    created_at: str,
) -> tuple[str | None, dict]:
    order_id = create_order(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix=external_ref_prefix,
        service_date=service_date,
        created_at=created_at,
    )
    detail = client.get(f"/orders/{order_id}", headers=auth_headers(office_token))
    assert detail.status_code == 200, detail.text
    body = detail.json()
    return body["operational_reason"], body["operational_explanation"]


def test_operational_same_day_window_edges_are_deterministic(client, db_session):
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
    _set_zone_timezone(db_session, zone_id, "UTC")
    _put_profile(
        client,
        admin_token,
        customer_id,
        accept_orders=True,
        window_start="08:00:00",
        window_end="10:00:00",
        min_lead_hours=0,
    )

    in_start_reason, _ = _create_and_fetch_operational(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="R6-QA-SAME-IN-START",
        service_date="2100-07-01",
        created_at="2100-07-01T08:00:00Z",
    )
    in_end_reason, _ = _create_and_fetch_operational(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="R6-QA-SAME-IN-END",
        service_date="2100-07-01",
        created_at="2100-07-01T10:00:00Z",
    )
    out_reason, _ = _create_and_fetch_operational(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="R6-QA-SAME-OUT",
        service_date="2100-07-01",
        created_at="2100-07-01T10:00:01Z",
    )

    assert in_start_reason is None
    assert in_end_reason is None
    assert out_reason == "OUTSIDE_CUSTOMER_WINDOW"


def test_operational_cross_midnight_window_edges_are_deterministic(client, db_session):
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
    _set_zone_timezone(db_session, zone_id, "UTC")
    _put_profile(
        client,
        admin_token,
        customer_id,
        accept_orders=True,
        window_start="22:00:00",
        window_end="02:00:00",
        min_lead_hours=0,
    )

    in_night_reason, _ = _create_and_fetch_operational(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="R6-QA-CROSS-IN-NIGHT",
        service_date="2100-07-02",
        created_at="2100-07-02T22:00:00Z",
    )
    in_early_reason, _ = _create_and_fetch_operational(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="R6-QA-CROSS-IN-EARLY",
        service_date="2100-07-02",
        created_at="2100-07-02T02:00:00Z",
    )
    out_reason, _ = _create_and_fetch_operational(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="R6-QA-CROSS-OUT",
        service_date="2100-07-02",
        created_at="2100-07-02T14:00:00Z",
    )

    assert in_night_reason is None
    assert in_early_reason is None
    assert out_reason == "OUTSIDE_CUSTOMER_WINDOW"


def test_operational_dst_forward_edges_are_deterministic(client, db_session):
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
    _set_zone_timezone(db_session, zone_id, "Europe/Madrid")
    _put_profile(
        client,
        admin_token,
        customer_id,
        accept_orders=True,
        window_start="01:00:00",
        window_end="03:00:00",
        min_lead_hours=0,
    )

    # Europe/Madrid DST forward (2027-03-28):
    # 00:30Z -> 01:30 local (inside), 01:30Z -> 03:30 local (outside)
    in_reason, in_explanation = _create_and_fetch_operational(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="R6-QA-DST-FWD-IN",
        service_date="2027-03-28",
        created_at="2027-03-28T00:30:00Z",
    )
    out_reason, out_explanation = _create_and_fetch_operational(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="R6-QA-DST-FWD-OUT",
        service_date="2027-03-28",
        created_at="2027-03-28T01:30:00Z",
    )

    assert in_reason is None
    assert out_reason == "OUTSIDE_CUSTOMER_WINDOW"
    assert in_explanation["timezone_used"] == "Europe/Madrid"
    assert in_explanation["timezone_source"] == "zone"
    assert out_explanation["timezone_used"] == "Europe/Madrid"
    assert out_explanation["timezone_source"] == "zone"


def test_operational_dst_backward_edges_are_deterministic(client, db_session):
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
    _set_zone_timezone(db_session, zone_id, "Europe/Madrid")
    _put_profile(
        client,
        admin_token,
        customer_id,
        accept_orders=True,
        window_start="02:00:00",
        window_end="02:45:00",
        min_lead_hours=0,
    )

    # Europe/Madrid DST backward (2027-10-31):
    # 00:30Z -> 02:30 local (first 02:30), 01:30Z -> 02:30 local (second 02:30), both inside.
    first_230_reason, first_230_explanation = _create_and_fetch_operational(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="R6-QA-DST-BWD-FIRST",
        service_date="2027-10-31",
        created_at="2027-10-31T00:30:00Z",
    )
    second_230_reason, second_230_explanation = _create_and_fetch_operational(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="R6-QA-DST-BWD-SECOND",
        service_date="2027-10-31",
        created_at="2027-10-31T01:30:00Z",
    )
    out_reason, out_explanation = _create_and_fetch_operational(
        client,
        office_token,
        customer_id=customer_id,
        external_ref_prefix="R6-QA-DST-BWD-OUT",
        service_date="2027-10-31",
        created_at="2027-10-31T01:50:00Z",
    )

    assert first_230_reason is None
    assert second_230_reason is None
    assert out_reason == "OUTSIDE_CUSTOMER_WINDOW"
    assert first_230_explanation["timezone_used"] == "Europe/Madrid"
    assert first_230_explanation["timezone_source"] == "zone"
    assert second_230_explanation["timezone_used"] == "Europe/Madrid"
    assert second_230_explanation["timezone_source"] == "zone"
    assert out_explanation["timezone_used"] == "Europe/Madrid"
    assert out_explanation["timezone_source"] == "zone"


def test_operational_timezone_resolver_fallback_is_deterministic():
    tenant_fallback = _resolve_timezone("Europe/Madrid", "Invalid/Zone")
    assert tenant_fallback.timezone_used == "Europe/Madrid"
    assert tenant_fallback.timezone_source == "tenant_default"

    utc_fallback = _resolve_timezone("Invalid/Tenant", "Invalid/Zone")
    assert utc_fallback.timezone_used == "UTC"
    assert utc_fallback.timezone_source == "utc_fallback"
