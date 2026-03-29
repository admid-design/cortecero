from datetime import UTC, datetime

from app.models import Tenant, User, UserRole, Zone
from app.security import hash_password
from tests.helpers import auth_headers, login_as


def test_list_zones_is_tenant_scoped_and_readable_by_office(client, db_session):
    tenant_b = Tenant(
        name="Tenant B",
        slug="tenant-b-zones",
        default_cutoff_time=datetime.strptime("10:00", "%H:%M").time(),
        default_timezone="Europe/Madrid",
        auto_lock_enabled=False,
        created_at=datetime.now(UTC),
    )
    db_session.add(tenant_b)
    db_session.flush()
    db_session.add(
        Zone(
            tenant_id=tenant_b.id,
            name="Zona Externa",
            default_cutoff_time=datetime.strptime("08:30", "%H:%M").time(),
            timezone="Europe/Madrid",
            active=True,
            created_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )
    res = client.get("/admin/zones", headers=auth_headers(token))
    assert res.status_code == 200, res.text
    names = {item["name"] for item in res.json()["items"]}
    assert "Centro" in names
    assert "Costa" in names
    assert "Zona Externa" not in names


def test_create_zone_requires_admin_role(client):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )
    res = client.post(
        "/admin/zones",
        json={"name": "Nueva Zona", "default_cutoff_time": "10:30:00", "timezone": "Europe/Madrid"},
        headers=auth_headers(token),
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "RBAC_FORBIDDEN"


def test_create_update_zone_and_name_conflict(client):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="admin@demo.cortecero.app",
        password="admin123",
    )

    create_res = client.post(
        "/admin/zones",
        json={"name": "R2 Zona", "default_cutoff_time": "11:00:00", "timezone": "Europe/Madrid"},
        headers=auth_headers(token),
    )
    assert create_res.status_code == 201, create_res.text
    zone_id = create_res.json()["id"]

    update_res = client.patch(
        f"/admin/zones/{zone_id}",
        json={"name": "R2 Zona Editada", "default_cutoff_time": "12:00:00"},
        headers=auth_headers(token),
    )
    assert update_res.status_code == 200, update_res.text
    assert update_res.json()["name"] == "R2 Zona Editada"
    assert update_res.json()["default_cutoff_time"] == "12:00:00"

    duplicate_res = client.patch(
        f"/admin/zones/{zone_id}",
        json={"name": "Centro"},
        headers=auth_headers(token),
    )
    assert duplicate_res.status_code == 409
    assert duplicate_res.json()["detail"]["code"] == "RESOURCE_CONFLICT"


def test_deactivate_zone_rules(client):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="admin@demo.cortecero.app",
        password="admin123",
    )

    zones_res = client.get("/admin/zones", headers=auth_headers(token))
    assert zones_res.status_code == 200, zones_res.text
    centro_id = next(item["id"] for item in zones_res.json()["items"] if item["name"] == "Centro")

    has_customers_res = client.post(f"/admin/zones/{centro_id}/deactivate", headers=auth_headers(token))
    assert has_customers_res.status_code == 422
    assert has_customers_res.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"

    create_res = client.post(
        "/admin/zones",
        json={"name": "Zona Temporal", "default_cutoff_time": "07:45:00", "timezone": "Europe/Madrid"},
        headers=auth_headers(token),
    )
    assert create_res.status_code == 201, create_res.text
    new_zone_id = create_res.json()["id"]

    deactivate_ok = client.post(f"/admin/zones/{new_zone_id}/deactivate", headers=auth_headers(token))
    assert deactivate_ok.status_code == 200, deactivate_ok.text
    assert deactivate_ok.json()["active"] is False

    deactivate_again = client.post(f"/admin/zones/{new_zone_id}/deactivate", headers=auth_headers(token))
    assert deactivate_again.status_code == 422
    assert deactivate_again.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"


def test_update_zone_is_tenant_filtered(client, db_session):
    tenant_b = Tenant(
        name="Tenant B 2",
        slug="tenant-b-zones-2",
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
            email="admin@tenantb.cortecero.app",
            full_name="Tenant B Admin",
            password_hash=hash_password("adminb123"),
            role=UserRole.admin,
            is_active=True,
            created_at=datetime.now(UTC),
        )
    )
    zone_b = Zone(
        tenant_id=tenant_b.id,
        name="Zona Tenant B",
        default_cutoff_time=datetime.strptime("09:00", "%H:%M").time(),
        timezone="Europe/Madrid",
        active=True,
        created_at=datetime.now(UTC),
    )
    db_session.add(zone_b)
    db_session.commit()

    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="admin@demo.cortecero.app",
        password="admin123",
    )
    res = client.patch(
        f"/admin/zones/{zone_b.id}",
        json={"name": "No permitido"},
        headers=auth_headers(token),
    )
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "ENTITY_NOT_FOUND"
