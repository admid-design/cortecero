from tests.helpers import auth_headers, create_order, login_as, pick_customer_id_for_zone


def test_locked_plan_without_approved_exception_returns_409(client):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )

    plans_res = client.get("/plans", headers=auth_headers(token))
    assert plans_res.status_code == 200, plans_res.text
    locked_plan = next(item for item in plans_res.json()["items"] if item["status"] == "locked")

    customer_id = pick_customer_id_for_zone(client, token, locked_plan["zone_id"])
    order_id = create_order(
        client,
        token,
        customer_id=customer_id,
        external_ref_prefix="LOCKED-409",
        service_date=locked_plan["service_date"],
        created_at="2026-01-01T00:00:00Z",
        sku="SKU-LOCKED-409",
    )

    include_res = client.post(
        f"/plans/{locked_plan['id']}/orders",
        json={"order_id": order_id},
        headers=auth_headers(token),
    )
    assert include_res.status_code == 409
    assert include_res.json()["detail"]["code"] == "EXCEPTION_REQUIRED"
