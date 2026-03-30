from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from app.models import (
    AuditLog,
    Customer,
    CustomerOperationalException,
    CustomerOperationalExceptionType,
    EntityType,
    Tenant,
    User,
    UserRole,
    Zone,
)
from app.security import hash_password
from tests.helpers import auth_headers, login_as


def _first_customer_id(client, token: str) -> str:
    res = client.get("/admin/customers", headers=auth_headers(token))
    assert res.status_code == 200, res.text
    items = res.json()["items"]
    assert items
    return items[0]["id"]


def test_operational_exceptions_list_create_delete_and_audit(client, db_session):
    admin_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="admin@demo.cortecero.app",
        password="admin123",
    )
    customer_id = _first_customer_id(client, admin_token)

    base_date = date.today() + timedelta(days=10)

    create_a = client.post(
        f"/admin/customers/{customer_id}/operational-exceptions",
        json={"date": base_date.isoformat(), "type": "blocked", "note": "Feriado local"},
        headers=auth_headers(admin_token),
    )
    assert create_a.status_code == 201, create_a.text

    create_b = client.post(
        f"/admin/customers/{customer_id}/operational-exceptions",
        json={"date": (base_date + timedelta(days=1)).isoformat(), "type": "restricted", "note": "Solo mañana"},
        headers=auth_headers(admin_token),
    )
    assert create_b.status_code == 201, create_b.text

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

    for token in (admin_token, office_token, logistics_token):
        list_res = client.get(
            f"/admin/customers/{customer_id}/operational-exceptions",
            headers=auth_headers(token),
        )
        assert list_res.status_code == 200, list_res.text
        body = list_res.json()
        assert body["total"] == 2
        assert [item["type"] for item in body["items"]] == ["blocked", "restricted"]

    exception_to_delete = create_a.json()["id"]
    delete_res = client.delete(
        f"/admin/customers/{customer_id}/operational-exceptions/{exception_to_delete}",
        headers=auth_headers(admin_token),
    )
    assert delete_res.status_code == 200, delete_res.text
    assert delete_res.json()["id"] == exception_to_delete

    list_after = client.get(
        f"/admin/customers/{customer_id}/operational-exceptions",
        headers=auth_headers(admin_token),
    )
    assert list_after.status_code == 200, list_after.text
    assert list_after.json()["total"] == 1

    tenant = db_session.query(Tenant).filter(Tenant.slug == "demo-cortecero").one()
    audit_rows = [
        row
        for row in db_session.query(AuditLog)
        .filter(
            AuditLog.tenant_id == tenant.id,
            AuditLog.entity_type == EntityType.tenant,
            AuditLog.action.in_([
                "customer.operational_exception_created",
                "customer.operational_exception_deleted",
            ]),
        )
        .all()
        if row.metadata_json.get("customer_id") == customer_id
    ]
    assert len([row for row in audit_rows if row.action == "customer.operational_exception_created"]) == 2
    assert len([row for row in audit_rows if row.action == "customer.operational_exception_deleted"]) == 1


def test_operational_exception_duplicate_note_contract_and_write_rbac(client):
    admin_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="admin@demo.cortecero.app",
        password="admin123",
    )
    office_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )
    customer_id = _first_customer_id(client, admin_token)
    target_date = date.today() + timedelta(days=20)

    forbidden_create = client.post(
        f"/admin/customers/{customer_id}/operational-exceptions",
        json={"date": target_date.isoformat(), "type": "blocked", "note": "No debería"},
        headers=auth_headers(office_token),
    )
    assert forbidden_create.status_code == 403
    assert forbidden_create.json()["detail"]["code"] == "RBAC_FORBIDDEN"

    invalid_note = client.post(
        f"/admin/customers/{customer_id}/operational-exceptions",
        json={"date": target_date.isoformat(), "type": "blocked", "note": "   "},
        headers=auth_headers(admin_token),
    )
    assert invalid_note.status_code == 422
    assert invalid_note.json()["detail"]["code"] == "INVALID_OPERATIONAL_EXCEPTION"

    created = client.post(
        f"/admin/customers/{customer_id}/operational-exceptions",
        json={"date": target_date.isoformat(), "type": "blocked", "note": "Cerrado"},
        headers=auth_headers(admin_token),
    )
    assert created.status_code == 201, created.text

    duplicated = client.post(
        f"/admin/customers/{customer_id}/operational-exceptions",
        json={"date": target_date.isoformat(), "type": "blocked", "note": "Duplicado"},
        headers=auth_headers(admin_token),
    )
    assert duplicated.status_code == 409
    assert duplicated.json()["detail"]["code"] == "OPERATIONAL_EXCEPTION_CONFLICT"


def test_operational_exception_delete_not_found_and_tenant_isolation(client, db_session):
    admin_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="admin@demo.cortecero.app",
        password="admin123",
    )
    customer_id = _first_customer_id(client, admin_token)

    delete_missing = client.delete(
        f"/admin/customers/{customer_id}/operational-exceptions/{uuid4()}",
        headers=auth_headers(admin_token),
    )
    assert delete_missing.status_code == 404
    assert delete_missing.json()["detail"]["code"] == "ENTITY_NOT_FOUND"

    tenant_b = Tenant(
        name="Tenant B Operational Exceptions",
        slug="tenant-b-operational-exceptions",
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
            email="admin@tenantb-opex.cortecero.app",
            full_name="Tenant B Admin",
            password_hash=hash_password("adminb123"),
            role=UserRole.admin,
            is_active=True,
            created_at=datetime.now(UTC),
        )
    )
    zone_b = Zone(
        tenant_id=tenant_b.id,
        name="Zona Tenant B Operational Exceptions",
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
        name="Cliente Tenant B Operational Exceptions",
        priority=0,
        cutoff_override_time=None,
        active=True,
        created_at=datetime.now(UTC),
    )
    db_session.add(customer_b)
    db_session.flush()

    exception_b = CustomerOperationalException(
        tenant_id=tenant_b.id,
        customer_id=customer_b.id,
        date=date.today() + timedelta(days=30),
        type=CustomerOperationalExceptionType.blocked,
        note="Bloqueado tenant B",
        created_at=datetime.now(UTC),
    )
    db_session.add(exception_b)
    db_session.commit()

    cross_list = client.get(
        f"/admin/customers/{customer_b.id}/operational-exceptions",
        headers=auth_headers(admin_token),
    )
    assert cross_list.status_code == 404
    assert cross_list.json()["detail"]["code"] == "ENTITY_NOT_FOUND"

    cross_post = client.post(
        f"/admin/customers/{customer_b.id}/operational-exceptions",
        json={"date": (date.today() + timedelta(days=31)).isoformat(), "type": "restricted", "note": "No permitido"},
        headers=auth_headers(admin_token),
    )
    assert cross_post.status_code == 404
    assert cross_post.json()["detail"]["code"] == "ENTITY_NOT_FOUND"

    cross_delete = client.delete(
        f"/admin/customers/{customer_id}/operational-exceptions/{exception_b.id}",
        headers=auth_headers(admin_token),
    )
    assert cross_delete.status_code == 404
    assert cross_delete.json()["detail"]["code"] == "ENTITY_NOT_FOUND"
