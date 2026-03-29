from datetime import UTC, datetime

from app.models import Customer, Tenant, User, UserRole, Zone
from app.security import hash_password
from tests.helpers import auth_headers, login_as


def test_list_customers_is_tenant_scoped_and_readable_by_logistics(client, db_session):
    tenant_b = Tenant(
        name="Tenant B Customers",
        slug="tenant-b-customers",
        default_cutoff_time=datetime.strptime("10:00", "%H:%M").time(),
        default_timezone="Europe/Madrid",
        auto_lock_enabled=False,
        created_at=datetime.now(UTC),
    )
    db_session.add(tenant_b)
    db_session.flush()
    zone_b = Zone(
        tenant_id=tenant_b.id,
        name="Zona B",
        default_cutoff_time=datetime.strptime("08:30", "%H:%M").time(),
        timezone="Europe/Madrid",
        active=True,
        created_at=datetime.now(UTC),
    )
    db_session.add(zone_b)
    db_session.flush()
    db_session.add(
        Customer(
            tenant_id=tenant_b.id,
            zone_id=zone_b.id,
            name="Cliente Externo",
            priority=1,
            cutoff_override_time=None,
            active=True,
            created_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )
    res = client.get("/admin/customers", headers=auth_headers(token))
    assert res.status_code == 200, res.text
    names = {item["name"] for item in res.json()["items"]}
    assert "Cliente 01" in names
    assert "Cliente Externo" not in names


def test_create_customer_requires_admin_role(client):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )
    zones = client.get("/admin/zones", headers=auth_headers(token))
    assert zones.status_code == 200, zones.text
    zone_id = zones.json()["items"][0]["id"]

    res = client.post(
        "/admin/customers",
        json={
            "zone_id": zone_id,
            "name": "Cliente Nuevo Office",
            "priority": 0,
            "cutoff_override_time": "09:30:00",
        },
        headers=auth_headers(token),
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "RBAC_FORBIDDEN"


def test_create_update_customer_and_name_conflict(client):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="admin@demo.cortecero.app",
        password="admin123",
    )

    zones = client.get("/admin/zones", headers=auth_headers(token))
    assert zones.status_code == 200, zones.text
    zone_ids = [item["id"] for item in zones.json()["items"]]
    assert len(zone_ids) >= 2

    create_res = client.post(
        "/admin/customers",
        json={
            "zone_id": zone_ids[0],
            "name": "R2 Cliente",
            "priority": 1,
            "cutoff_override_time": "09:15:00",
        },
        headers=auth_headers(token),
    )
    assert create_res.status_code == 201, create_res.text
    customer_id = create_res.json()["id"]

    update_res = client.patch(
        f"/admin/customers/{customer_id}",
        json={
            "zone_id": zone_ids[1],
            "name": "R2 Cliente Editado",
            "priority": 7,
            "cutoff_override_time": None,
        },
        headers=auth_headers(token),
    )
    assert update_res.status_code == 200, update_res.text
    body = update_res.json()
    assert body["name"] == "R2 Cliente Editado"
    assert body["priority"] == 7
    assert body["zone_id"] == zone_ids[1]
    assert body["cutoff_override_time"] is None

    conflict_res = client.patch(
        f"/admin/customers/{customer_id}",
        json={"name": "Cliente 01"},
        headers=auth_headers(token),
    )
    assert conflict_res.status_code == 409
    assert conflict_res.json()["detail"]["code"] == "RESOURCE_CONFLICT"


def test_deactivate_customer_rules(client):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="admin@demo.cortecero.app",
        password="admin123",
    )
    zones = client.get("/admin/zones", headers=auth_headers(token))
    assert zones.status_code == 200, zones.text
    zone_id = zones.json()["items"][0]["id"]

    create_res = client.post(
        "/admin/customers",
        json={
            "zone_id": zone_id,
            "name": "Cliente Deactivate",
            "priority": 0,
            "cutoff_override_time": None,
        },
        headers=auth_headers(token),
    )
    assert create_res.status_code == 201, create_res.text
    customer_id = create_res.json()["id"]

    deactivate_res = client.post(f"/admin/customers/{customer_id}/deactivate", headers=auth_headers(token))
    assert deactivate_res.status_code == 200, deactivate_res.text
    assert deactivate_res.json()["active"] is False

    deactivate_again = client.post(f"/admin/customers/{customer_id}/deactivate", headers=auth_headers(token))
    assert deactivate_again.status_code == 422
    assert deactivate_again.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"


def test_update_customer_is_tenant_filtered_and_zone_must_match_tenant(client, db_session):
    tenant_b = Tenant(
        name="Tenant B Customer 2",
        slug="tenant-b-customers-2",
        default_cutoff_time=datetime.strptime("10:00", "%H:%M").time(),
        default_timezone="Europe/Madrid",
        auto_lock_enabled=False,
        created_at=datetime.now(UTC),
    )
    db_session.add(tenant_b)
    db_session.flush()

    db_session.add(
        User(
            tenant_id=tenant_b.id,
            email="admin@tenantb-customers.cortecero.app",
            full_name="Tenant B Admin",
            password_hash=hash_password("adminb123"),
            role=UserRole.admin,
            is_active=True,
            created_at=datetime.now(UTC),
        )
    )
    zone_b = Zone(
        tenant_id=tenant_b.id,
        name="Zona Tenant B Customers",
        default_cutoff_time=datetime.strptime("09:00", "%H:%M").time(),
        timezone="Europe/Madrid",
        active=True,
        created_at=datetime.now(UTC),
    )
    db_session.add(zone_b)
    db_session.flush()

    customer_b = Customer(
        tenant_id=tenant_b.id,
        zone_id=zone_b.id,
        name="Cliente Tenant B",
        priority=0,
        cutoff_override_time=None,
        active=True,
        created_at=datetime.now(UTC),
    )
    db_session.add(customer_b)
    db_session.commit()

    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="admin@demo.cortecero.app",
        password="admin123",
    )

    tenant_filtered = client.patch(
        f"/admin/customers/{customer_b.id}",
        json={"name": "No permitido"},
        headers=auth_headers(token),
    )
    assert tenant_filtered.status_code == 404
    assert tenant_filtered.json()["detail"]["code"] == "ENTITY_NOT_FOUND"

    deactivate_tenant_filtered = client.post(
        f"/admin/customers/{customer_b.id}/deactivate",
        headers=auth_headers(token),
    )
    assert deactivate_tenant_filtered.status_code == 404
    assert deactivate_tenant_filtered.json()["detail"]["code"] == "ENTITY_NOT_FOUND"

    create_cross_zone = client.post(
        "/admin/customers",
        json={
            "zone_id": str(zone_b.id),
            "name": "Cliente Cross Tenant",
            "priority": 0,
            "cutoff_override_time": None,
        },
        headers=auth_headers(token),
    )
    assert create_cross_zone.status_code == 404
    assert create_cross_zone.json()["detail"]["code"] == "ENTITY_NOT_FOUND"
