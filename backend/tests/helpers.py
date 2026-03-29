from __future__ import annotations

import uuid
from datetime import date

from fastapi.testclient import TestClient


def login_as(
    client: TestClient,
    *,
    tenant_slug: str,
    email: str,
    password: str,
) -> str:
    res = client.post(
        "/auth/login",
        json={"tenant_slug": tenant_slug, "email": email, "password": password},
    )
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    assert token
    return token


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def pick_customer_id_for_zone(client: TestClient, token: str, zone_id: str) -> str:
    res = client.get("/orders", params={"zone_id": zone_id}, headers=auth_headers(token))
    assert res.status_code == 200, res.text
    items = res.json()["items"]
    assert items, "No orders found for zone in seed data"
    return items[0]["customer_id"]


def create_order(
    client: TestClient,
    token: str,
    *,
    customer_id: str,
    external_ref_prefix: str,
    service_date: str,
    created_at: str,
    sku: str = "SKU-TEST",
) -> str:
    external_ref = f"{external_ref_prefix}-{uuid.uuid4()}"
    payload = {
        "orders": [
            {
                "customer_id": customer_id,
                "external_ref": external_ref,
                "service_date": service_date,
                "created_at": created_at,
                "source_channel": "office",
                "lines": [{"sku": sku, "qty": 1}],
            }
        ]
    }
    res = client.post("/ingestion/orders", json=payload, headers=auth_headers(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["items"][0]["result"] in {"created", "updated"}
    order_id = body["items"][0]["order_id"]
    assert order_id
    return order_id


def far_future_service_date(days: int = 3650) -> str:
    return (date.today().fromordinal(date.today().toordinal() + days)).isoformat()
