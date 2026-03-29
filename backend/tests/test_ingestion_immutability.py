from tests.helpers import auth_headers, create_order, login_as


def test_reingestion_keeps_created_at_and_lateness(client):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )

    orders_res = client.get("/orders", headers=auth_headers(token))
    assert orders_res.status_code == 200, orders_res.text
    customer_id = orders_res.json()["items"][0]["customer_id"]

    service_date = "2099-12-29"
    external_ref_prefix = "IMMUTABLE"
    first_created_at = "2026-01-01T00:00:00Z"
    second_created_at = "2099-12-29T23:59:59Z"

    order_id = create_order(
        client,
        token,
        customer_id=customer_id,
        external_ref_prefix=external_ref_prefix,
        service_date=service_date,
        created_at=first_created_at,
        sku="SKU-IMM-1",
    )

    before_res = client.get(f"/orders/{order_id}", headers=auth_headers(token))
    assert before_res.status_code == 200, before_res.text
    before = before_res.json()

    payload_update = {
        "orders": [
            {
                "customer_id": customer_id,
                "external_ref": before["external_ref"],
                "service_date": service_date,
                "created_at": second_created_at,
                "source_channel": "sales",
                "lines": [{"sku": "SKU-IMM-2", "qty": 2}],
            }
        ]
    }
    update_res = client.post("/ingestion/orders", json=payload_update, headers=auth_headers(token))
    assert update_res.status_code == 200, update_res.text
    assert update_res.json()["updated"] == 1

    after_res = client.get(f"/orders/{order_id}", headers=auth_headers(token))
    assert after_res.status_code == 200, after_res.text
    after = after_res.json()

    assert after["created_at"] == before["created_at"]
    assert after["is_late"] == before["is_late"]
    assert after["effective_cutoff_at"] == before["effective_cutoff_at"]
