from tests.helpers import auth_headers, create_order, login_as


def test_order_intake_type_new_then_same_customer_addon(client):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )

    orders_res = client.get("/orders", headers=auth_headers(token))
    assert orders_res.status_code == 200, orders_res.text
    customer_id = orders_res.json()["items"][0]["customer_id"]

    service_date = "2099-12-27"

    first_order_id = create_order(
        client,
        token,
        customer_id=customer_id,
        external_ref_prefix="INTAKE-NEW",
        service_date=service_date,
        created_at="2026-01-01T00:00:00Z",
        sku="SKU-INTAKE-1",
    )
    second_order_id = create_order(
        client,
        token,
        customer_id=customer_id,
        external_ref_prefix="INTAKE-ADDON",
        service_date=service_date,
        created_at="2026-01-01T00:05:00Z",
        sku="SKU-INTAKE-2",
    )

    first_detail_res = client.get(f"/orders/{first_order_id}", headers=auth_headers(token))
    assert first_detail_res.status_code == 200, first_detail_res.text
    assert first_detail_res.json()["intake_type"] == "new_order"

    second_detail_res = client.get(f"/orders/{second_order_id}", headers=auth_headers(token))
    assert second_detail_res.status_code == 200, second_detail_res.text
    assert second_detail_res.json()["intake_type"] == "same_customer_addon"

    list_res = client.get(
        "/orders",
        params={"service_date": service_date},
        headers=auth_headers(token),
    )
    assert list_res.status_code == 200, list_res.text

    by_id = {item["id"]: item for item in list_res.json()["items"]}
    assert by_id[str(first_order_id)]["intake_type"] == "new_order"
    assert by_id[str(second_order_id)]["intake_type"] == "same_customer_addon"
