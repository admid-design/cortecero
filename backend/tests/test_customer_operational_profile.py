from datetime import UTC, datetime

from app.models import AuditLog, Customer, CustomerOperationalProfile, EntityType, Tenant, User, UserRole, Zone
from app.security import hash_password
from tests.helpers import auth_headers, login_as


def _first_customer_id(client, token: str) -> str:
    res = client.get("/admin/customers", headers=auth_headers(token))
    assert res.status_code == 200, res.text
    items = res.json()["items"]
    assert items
    return items[0]["id"]


def test_get_customer_operational_profile_defaults_and_read_access(client, db_session):
    admin_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="admin@demo.cortecero.app",
        password="admin123",
    )
    customer_id = _first_customer_id(client, admin_token)

    customer = db_session.query(Customer).filter(Customer.id == customer_id).one()
    zone = db_session.query(Zone).filter(Zone.id == customer.zone_id, Zone.tenant_id == customer.tenant_id).one()

    office_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )
    logistics_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )

    for token in (office_token, logistics_token, admin_token):
        res = client.get(f"/admin/customers/{customer_id}/operational-profile", headers=auth_headers(token))
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["customer_id"] == customer_id
        assert body["accept_orders"] is True
        assert body["window_start"] is None
        assert body["window_end"] is None
        assert body["min_lead_hours"] == 0
        assert body["consolidate_by_default"] is False
        assert body["ops_note"] is None
        assert body["window_mode"] == "none"
        assert body["is_customized"] is False
        assert body["evaluation_timezone"] == zone.timezone


def test_put_customer_operational_profile_upsert_replace_and_idempotent(client, db_session):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="admin@demo.cortecero.app",
        password="admin123",
    )
    customer_id = _first_customer_id(client, token)

    put_first = client.put(
        f"/admin/customers/{customer_id}/operational-profile",
        json={
            "accept_orders": False,
            "window_start": "22:00:00",
            "window_end": "06:00:00",
            "min_lead_hours": 4,
            "consolidate_by_default": True,
            "ops_note": "Entrega nocturna",
        },
        headers=auth_headers(token),
    )
    assert put_first.status_code == 200, put_first.text
    first_body = put_first.json()
    assert first_body["is_customized"] is True
    assert first_body["window_mode"] == "cross_midnight"

    profile = (
        db_session.query(CustomerOperationalProfile)
        .filter(
            CustomerOperationalProfile.customer_id == customer_id,
        )
        .one()
    )
    assert profile.accept_orders is False
    assert profile.window_start.isoformat() == "22:00:00"
    assert profile.window_end.isoformat() == "06:00:00"
    assert profile.min_lead_hours == 4
    assert profile.consolidate_by_default is True
    assert profile.ops_note == "Entrega nocturna"

    tenant = db_session.query(Tenant).filter(Tenant.slug == "demo-cortecero").one()
    first_audits = [
        row
        for row in db_session.query(AuditLog)
        .filter(
            AuditLog.tenant_id == tenant.id,
            AuditLog.entity_type == EntityType.tenant,
            AuditLog.action == "customer.operational_profile_updated",
        )
        .order_by(AuditLog.ts.asc())
        .all()
        if row.metadata_json.get("customer_id") == customer_id
    ]
    assert len(first_audits) == 1

    put_replace = client.put(
        f"/admin/customers/{customer_id}/operational-profile",
        json={
            "accept_orders": True,
            "window_start": None,
            "window_end": None,
            "min_lead_hours": 1,
            "consolidate_by_default": False,
            "ops_note": None,
        },
        headers=auth_headers(token),
    )
    assert put_replace.status_code == 200, put_replace.text
    replace_body = put_replace.json()
    assert replace_body["window_mode"] == "none"
    assert replace_body["window_start"] is None
    assert replace_body["window_end"] is None
    assert replace_body["ops_note"] is None

    db_session.refresh(profile)
    assert profile.accept_orders is True
    assert profile.window_start is None
    assert profile.window_end is None
    assert profile.min_lead_hours == 1
    assert profile.consolidate_by_default is False
    assert profile.ops_note is None

    second_audits = [
        row
        for row in db_session.query(AuditLog)
        .filter(
            AuditLog.tenant_id == tenant.id,
            AuditLog.entity_type == EntityType.tenant,
            AuditLog.action == "customer.operational_profile_updated",
        )
        .order_by(AuditLog.ts.asc())
        .all()
        if row.metadata_json.get("customer_id") == customer_id
    ]
    assert len(second_audits) == 2

    put_no_change = client.put(
        f"/admin/customers/{customer_id}/operational-profile",
        json={
            "accept_orders": True,
            "window_start": None,
            "window_end": None,
            "min_lead_hours": 1,
            "consolidate_by_default": False,
            "ops_note": None,
        },
        headers=auth_headers(token),
    )
    assert put_no_change.status_code == 200, put_no_change.text

    final_audits = [
        row
        for row in db_session.query(AuditLog)
        .filter(
            AuditLog.tenant_id == tenant.id,
            AuditLog.entity_type == EntityType.tenant,
            AuditLog.action == "customer.operational_profile_updated",
        )
        .order_by(AuditLog.ts.asc())
        .all()
        if row.metadata_json.get("customer_id") == customer_id
    ]
    assert len(final_audits) == 2


def test_put_customer_operational_profile_requires_admin_and_tenant_scope(client, db_session):
    office_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )
    customer_id = _first_customer_id(client, office_token)

    forbidden = client.put(
        f"/admin/customers/{customer_id}/operational-profile",
        json={
            "accept_orders": True,
            "window_start": None,
            "window_end": None,
            "min_lead_hours": 0,
            "consolidate_by_default": False,
            "ops_note": None,
        },
        headers=auth_headers(office_token),
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"]["code"] == "RBAC_FORBIDDEN"

    tenant_b = Tenant(
        name="Tenant B Operational",
        slug="tenant-b-operational",
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
            email="admin@tenantb-operational.cortecero.app",
            full_name="Tenant B Admin",
            password_hash=hash_password("adminb123"),
            role=UserRole.admin,
            is_active=True,
            created_at=datetime.now(UTC),
        )
    )
    zone_b = Zone(
        tenant_id=tenant_b.id,
        name="Zona Tenant B Operational",
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
        name="Cliente Tenant B Operational",
        priority=0,
        cutoff_override_time=None,
        active=True,
        created_at=datetime.now(UTC),
    )
    db_session.add(customer_b)
    db_session.commit()

    admin_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="admin@demo.cortecero.app",
        password="admin123",
    )

    cross_get = client.get(
        f"/admin/customers/{customer_b.id}/operational-profile",
        headers=auth_headers(admin_token),
    )
    assert cross_get.status_code == 404
    assert cross_get.json()["detail"]["code"] == "ENTITY_NOT_FOUND"

    cross_put = client.put(
        f"/admin/customers/{customer_b.id}/operational-profile",
        json={
            "accept_orders": True,
            "window_start": None,
            "window_end": None,
            "min_lead_hours": 0,
            "consolidate_by_default": False,
            "ops_note": None,
        },
        headers=auth_headers(admin_token),
    )
    assert cross_put.status_code == 404
    assert cross_put.json()["detail"]["code"] == "ENTITY_NOT_FOUND"


def test_put_customer_operational_profile_validations_and_timezone_contract(client, db_session):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="admin@demo.cortecero.app",
        password="admin123",
    )
    customer_id = _first_customer_id(client, token)

    invalid_pair = client.put(
        f"/admin/customers/{customer_id}/operational-profile",
        json={
            "accept_orders": True,
            "window_start": "08:00:00",
            "window_end": None,
            "min_lead_hours": 0,
            "consolidate_by_default": False,
            "ops_note": None,
        },
        headers=auth_headers(token),
    )
    assert invalid_pair.status_code == 422
    assert invalid_pair.json()["detail"]["code"] == "INVALID_OPERATIONAL_PROFILE"

    invalid_equal = client.put(
        f"/admin/customers/{customer_id}/operational-profile",
        json={
            "accept_orders": True,
            "window_start": "08:00:00",
            "window_end": "08:00:00",
            "min_lead_hours": 0,
            "consolidate_by_default": False,
            "ops_note": None,
        },
        headers=auth_headers(token),
    )
    assert invalid_equal.status_code == 422
    assert invalid_equal.json()["detail"]["code"] == "INVALID_OPERATIONAL_PROFILE"

    invalid_lead = client.put(
        f"/admin/customers/{customer_id}/operational-profile",
        json={
            "accept_orders": True,
            "window_start": None,
            "window_end": None,
            "min_lead_hours": -1,
            "consolidate_by_default": False,
            "ops_note": None,
        },
        headers=auth_headers(token),
    )
    assert invalid_lead.status_code == 422
    assert invalid_lead.json()["detail"]["code"] == "INVALID_OPERATIONAL_PROFILE"

    invalid_note = client.put(
        f"/admin/customers/{customer_id}/operational-profile",
        json={
            "accept_orders": True,
            "window_start": None,
            "window_end": None,
            "min_lead_hours": 0,
            "consolidate_by_default": False,
            "ops_note": "   ",
        },
        headers=auth_headers(token),
    )
    assert invalid_note.status_code == 422
    assert invalid_note.json()["detail"]["code"] == "INVALID_OPERATIONAL_PROFILE"

    customer = db_session.query(Customer).filter(Customer.id == customer_id).one()
    zone = db_session.query(Zone).filter(Zone.id == customer.zone_id, Zone.tenant_id == customer.tenant_id).one()

    invalid_timezone_update = client.patch(
        f"/admin/zones/{zone.id}",
        json={"timezone": "Mars/Phobos"},
        headers=auth_headers(token),
    )
    assert invalid_timezone_update.status_code == 422
    assert invalid_timezone_update.json()["detail"]["code"] == "INVALID_TIMEZONE"

    valid_profile = client.get(
        f"/admin/customers/{customer_id}/operational-profile",
        headers=auth_headers(token),
    )
    assert valid_profile.status_code == 200, valid_profile.text
    assert valid_profile.json()["evaluation_timezone"] == zone.timezone
