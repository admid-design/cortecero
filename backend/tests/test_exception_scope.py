from tests.helpers import auth_headers, create_order, login_as


def test_late_order_out_of_scope_returns_422(client):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )

    orders_res = client.get("/orders", headers=auth_headers(token))
    assert orders_res.status_code == 200, orders_res.text
    customer_id = orders_res.json()["items"][0]["customer_id"]

    order_id = create_order(
        client,
        token,
        customer_id=customer_id,
        external_ref_prefix="SCOPE-422",
        service_date="2099-12-30",
        created_at="2026-01-01T00:00:00Z",
        sku="SKU-SCOPE-422",
    )

    exc_res = client.post(
        "/exceptions",
        json={"order_id": order_id, "type": "late_order", "note": "no debería aplicar"},
        headers=auth_headers(token),
    )
    assert exc_res.status_code == 422
    assert exc_res.json()["detail"]["code"] == "INVALID_EXCEPTION_SCOPE"
