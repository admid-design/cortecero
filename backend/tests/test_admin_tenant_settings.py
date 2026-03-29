from app.models import AuditLog, EntityType, Tenant
from tests.helpers import auth_headers, login_as


def test_get_tenant_settings_requires_admin(client):
    admin_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="admin@demo.cortecero.app",
        password="admin123",
    )
    res = client.get("/admin/tenant-settings", headers=auth_headers(admin_token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["slug"] == "demo-cortecero"
    assert body["default_timezone"] == "Europe/Madrid"

    office_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )
    denied = client.get("/admin/tenant-settings", headers=auth_headers(office_token))
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "RBAC_FORBIDDEN"


def test_patch_tenant_settings_updates_values_and_writes_audit(client, db_session):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="admin@demo.cortecero.app",
        password="admin123",
    )

    patch = client.patch(
        "/admin/tenant-settings",
        json={
            "default_cutoff_time": "11:30:00",
            "default_timezone": "UTC",
            "auto_lock_enabled": True,
        },
        headers=auth_headers(token),
    )
    assert patch.status_code == 200, patch.text
    body = patch.json()
    assert body["default_cutoff_time"] == "11:30:00"
    assert body["default_timezone"] == "UTC"
    assert body["auto_lock_enabled"] is True

    tenant = db_session.query(Tenant).filter(Tenant.slug == "demo-cortecero").one()
    assert tenant.default_timezone == "UTC"
    assert tenant.auto_lock_enabled is True

    audit = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.tenant_id == tenant.id,
            AuditLog.entity_type == EntityType.tenant,
            AuditLog.entity_id == tenant.id,
            AuditLog.action == "tenant_settings.updated",
        )
        .order_by(AuditLog.ts.desc())
        .first()
    )
    assert audit is not None
    assert set(audit.metadata_json["changed_fields"]) == {"default_cutoff_time", "default_timezone", "auto_lock_enabled"}
    assert audit.metadata_json["before"]["default_timezone"] == "Europe/Madrid"
    assert audit.metadata_json["after"]["default_timezone"] == "UTC"


def test_patch_tenant_settings_validates_empty_and_null_values(client):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="admin@demo.cortecero.app",
        password="admin123",
    )

    empty_patch = client.patch("/admin/tenant-settings", json={}, headers=auth_headers(token))
    assert empty_patch.status_code == 422
    assert empty_patch.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"

    null_timezone = client.patch(
        "/admin/tenant-settings",
        json={"default_timezone": None},
        headers=auth_headers(token),
    )
    assert null_timezone.status_code == 422
    assert null_timezone.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"
