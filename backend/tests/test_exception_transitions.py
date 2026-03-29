from tests.helpers import auth_headers, create_order, login_as, pick_customer_id_for_zone


def _create_pending_exception_for_late_order(client, token: str) -> str:
    plans_res = client.get("/plans", headers=auth_headers(token))
    assert plans_res.status_code == 200, plans_res.text
    locked_plan = next(item for item in plans_res.json()["items"] if item["status"] == "locked")

    customer_id = pick_customer_id_for_zone(client, token, locked_plan["zone_id"])
    order_id = create_order(
        client,
        token,
        customer_id=customer_id,
        external_ref_prefix="EXC-LATE",
        service_date=locked_plan["service_date"],
        created_at=f"{locked_plan['service_date']}T23:59:59Z",
        sku="SKU-EXC-LATE",
    )

    create_res = client.post(
        "/exceptions",
        json={"order_id": order_id, "type": "late_order", "note": "late order test"},
        headers=auth_headers(token),
    )
    assert create_res.status_code == 201, create_res.text
    return create_res.json()["id"]


def test_approve_valid_then_invalid_transition(client):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )
    exception_id = _create_pending_exception_for_late_order(client, token)

    approve_res = client.post(f"/exceptions/{exception_id}/approve", headers=auth_headers(token))
    assert approve_res.status_code == 200, approve_res.text
    assert approve_res.json()["status"] == "approved"

    approve_again_res = client.post(f"/exceptions/{exception_id}/approve", headers=auth_headers(token))
    assert approve_again_res.status_code == 422
    assert approve_again_res.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"


def test_reject_valid_then_invalid_transition(client):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )
    exception_id = _create_pending_exception_for_late_order(client, token)

    reject_res = client.post(
        f"/exceptions/{exception_id}/reject",
        json={"note": "no aplica"},
        headers=auth_headers(token),
    )
    assert reject_res.status_code == 200, reject_res.text
    assert reject_res.json()["status"] == "rejected"

    reject_again_res = client.post(
        f"/exceptions/{exception_id}/reject",
        json={"note": "second reject"},
        headers=auth_headers(token),
    )
    assert reject_again_res.status_code == 422
    assert reject_again_res.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"
