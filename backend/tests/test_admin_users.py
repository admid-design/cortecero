from datetime import UTC, datetime

from app.models import Tenant, User, UserRole
from app.security import hash_password, verify_password
from tests.helpers import auth_headers, login_as


def test_admin_users_list_is_tenant_scoped_and_requires_admin(client, db_session):
    tenant_b = Tenant(
        name="Tenant B Users",
        slug="tenant-b-users",
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
            email="user-b@tenantb.cortecero.app",
            full_name="User B",
            password_hash=hash_password("tenantb123"),
            role=UserRole.office,
            is_active=True,
            created_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    admin_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="admin@demo.cortecero.app",
        password="admin123",
    )
    res = client.get("/admin/users", headers=auth_headers(admin_token))
    assert res.status_code == 200, res.text
    emails = {item["email"] for item in res.json()["items"]}
    assert "admin@demo.cortecero.app" in emails
    assert "user-b@tenantb.cortecero.app" not in emails

    office_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )
    denied = client.get("/admin/users", headers=auth_headers(office_token))
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "RBAC_FORBIDDEN"


def test_create_user_hashes_password_and_enforces_unique_per_tenant(client, db_session):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="admin@demo.cortecero.app",
        password="admin123",
    )

    create_res = client.post(
        "/admin/users",
        json={
            "email": "new-office@demo.cortecero.app",
            "full_name": "New Office",
            "role": "office",
            "password": "newoffice123",
            "is_active": True,
        },
        headers=auth_headers(token),
    )
    assert create_res.status_code == 201, create_res.text
    body = create_res.json()
    assert body["email"] == "new-office@demo.cortecero.app"
    assert body["role"] == "office"
    assert "password_hash" not in body

    stored = db_session.query(User).filter(User.email == "new-office@demo.cortecero.app").one()
    assert stored.is_active is True
    assert stored.password_hash != "newoffice123"
    assert verify_password("newoffice123", stored.password_hash)

    duplicate = client.post(
        "/admin/users",
        json={
            "email": "NEW-OFFICE@DEMO.CORTECERO.APP",
            "full_name": "Duplicate",
            "role": "logistics",
            "password": "dup-pass-123",
            "is_active": True,
        },
        headers=auth_headers(token),
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "RESOURCE_CONFLICT"

    tenant_b = Tenant(
        name="Tenant B Create",
        slug="tenant-b-create-users",
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
            email="admin@tenantb-create.cortecero.app",
            full_name="Tenant B Admin",
            password_hash=hash_password("tenantb123"),
            role=UserRole.admin,
            is_active=True,
            created_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    token_b = login_as(
        client,
        tenant_slug="tenant-b-create-users",
        email="admin@tenantb-create.cortecero.app",
        password="tenantb123",
    )
    cross_tenant_ok = client.post(
        "/admin/users",
        json={
            "email": "new-office@demo.cortecero.app",
            "full_name": "Same Email Other Tenant",
            "role": "office",
            "password": "tenantb-office-123",
            "is_active": True,
        },
        headers=auth_headers(token_b),
    )
    assert cross_tenant_ok.status_code == 201, cross_tenant_ok.text


def test_update_user_changes_password_and_role_and_validates_role_value(client, db_session):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="admin@demo.cortecero.app",
        password="admin123",
    )
    create_res = client.post(
        "/admin/users",
        json={
            "email": "update-me@demo.cortecero.app",
            "full_name": "Update Me",
            "role": "office",
            "password": "office-pass-123",
            "is_active": True,
        },
        headers=auth_headers(token),
    )
    assert create_res.status_code == 201, create_res.text
    user_id = create_res.json()["id"]

    update_res = client.patch(
        f"/admin/users/{user_id}",
        json={
            "full_name": "Updated User",
            "role": "logistics",
            "password": "new-pass-456",
            "is_active": True,
        },
        headers=auth_headers(token),
    )
    assert update_res.status_code == 200, update_res.text
    body = update_res.json()
    assert body["full_name"] == "Updated User"
    assert body["role"] == "logistics"
    assert body["is_active"] is True

    stored = db_session.query(User).filter(User.id == user_id).one()
    assert stored.role == UserRole.logistics
    assert verify_password("new-pass-456", stored.password_hash)

    invalid_role = client.patch(
        f"/admin/users/{user_id}",
        json={"role": "superadmin"},
        headers=auth_headers(token),
    )
    assert invalid_role.status_code == 422


def test_cannot_deactivate_or_demote_last_active_admin(client):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="admin@demo.cortecero.app",
        password="admin123",
    )

    users = client.get("/admin/users", headers=auth_headers(token))
    assert users.status_code == 200, users.text
    admin_id = next(item["id"] for item in users.json()["items"] if item["email"] == "admin@demo.cortecero.app")

    deactivate = client.patch(
        f"/admin/users/{admin_id}",
        json={"is_active": False},
        headers=auth_headers(token),
    )
    assert deactivate.status_code == 422
    assert deactivate.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"

    demote = client.patch(
        f"/admin/users/{admin_id}",
        json={"role": "office"},
        headers=auth_headers(token),
    )
    assert demote.status_code == 422
    assert demote.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"


def test_update_user_is_tenant_filtered(client, db_session):
    tenant_b = Tenant(
        name="Tenant B Patch",
        slug="tenant-b-patch-users",
        default_cutoff_time=datetime.strptime("10:00", "%H:%M").time(),
        default_timezone="Europe/Madrid",
        auto_lock_enabled=False,
        created_at=datetime.now(UTC),
    )
    db_session.add(tenant_b)
    db_session.flush()
    user_b = User(
        tenant_id=tenant_b.id,
        email="office@tenantb-patch.cortecero.app",
        full_name="Tenant B Office",
        password_hash=hash_password("tenantb123"),
        role=UserRole.office,
        is_active=True,
        created_at=datetime.now(UTC),
    )
    db_session.add(user_b)
    db_session.commit()

    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="admin@demo.cortecero.app",
        password="admin123",
    )
    res = client.patch(
        f"/admin/users/{user_b.id}",
        json={"full_name": "No permitido"},
        headers=auth_headers(token),
    )
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "ENTITY_NOT_FOUND"
