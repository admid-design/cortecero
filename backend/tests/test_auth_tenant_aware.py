from datetime import UTC, datetime

from app.models import Tenant, User, UserRole
from app.security import hash_password
from tests.helpers import login_as


def test_login_is_tenant_aware(client, db_session):
    same_email = "logistics@demo.cortecero.app"

    tenant_b = Tenant(
        name="Tenant B",
        slug="tenant-b",
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
            email=same_email,
            full_name="Tenant B Logistics",
            password_hash=hash_password("tenantb123"),
            role=UserRole.logistics,
            is_active=True,
            created_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    token_a = login_as(
        client,
        tenant_slug="demo-cortecero",
        email=same_email,
        password="logistics123",
    )
    assert token_a

    token_b = login_as(
        client,
        tenant_slug="tenant-b",
        email=same_email,
        password="tenantb123",
    )
    assert token_b

    wrong_scope = client.post(
        "/auth/login",
        json={
            "tenant_slug": "demo-cortecero",
            "email": same_email,
            "password": "tenantb123",
        },
    )
    assert wrong_scope.status_code == 401
    assert wrong_scope.json()["detail"]["code"] == "INVALID_CREDENTIALS"
