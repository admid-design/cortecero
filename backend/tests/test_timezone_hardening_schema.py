from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


def test_timezone_hardening_function_and_constraints_exist(db_session):
    function_exists = db_session.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_proc
                WHERE proname = 'is_valid_iana_timezone'
            )
            """
        )
    ).scalar_one()
    assert function_exists is True

    constraints = {
        row.conname
        for row in db_session.execute(
            text(
                """
                SELECT conname
                FROM pg_constraint
                WHERE conname IN ('ck_tenants_default_timezone_iana', 'ck_zones_timezone_iana')
                """
            )
        ).fetchall()
    }
    assert "ck_tenants_default_timezone_iana" in constraints
    assert "ck_zones_timezone_iana" in constraints


def test_timezone_hardening_rejects_invalid_tenant_and_zone_timezone(db_session):
    with pytest.raises(DBAPIError):
        db_session.execute(
            text(
                """
                INSERT INTO tenants (id, name, slug, default_cutoff_time, default_timezone, auto_lock_enabled, created_at, updated_at)
                VALUES (:id, :name, :slug, TIME '10:00', :timezone, FALSE, :now, :now)
                """
            ),
            {
                "id": str(uuid4()),
                "name": "Tenant Invalid TZ",
                "slug": f"tenant-invalid-tz-{uuid4()}",
                "timezone": "Invalid/Timezone",
                "now": datetime.now(UTC),
            },
        )
        db_session.commit()
    db_session.rollback()

    tenant_id = uuid4()
    now = datetime.now(UTC)
    db_session.execute(
        text(
            """
            INSERT INTO tenants (id, name, slug, default_cutoff_time, default_timezone, auto_lock_enabled, created_at, updated_at)
            VALUES (:id, :name, :slug, TIME '10:00', :timezone, FALSE, :now, :now)
            """
        ),
        {
            "id": str(tenant_id),
            "name": "Tenant Valid TZ",
            "slug": f"tenant-valid-tz-{uuid4()}",
            "timezone": "Europe/Madrid",
            "now": now,
        },
    )
    db_session.commit()

    with pytest.raises(DBAPIError):
        db_session.execute(
            text(
                """
                INSERT INTO zones (id, tenant_id, name, default_cutoff_time, timezone, active, created_at, updated_at)
                VALUES (:id, :tenant_id, :name, TIME '09:00', :timezone, TRUE, :now, :now)
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": str(tenant_id),
                "name": "Zona Invalid TZ",
                "timezone": "No/SuchTimezone",
                "now": datetime.now(UTC),
            },
        )
        db_session.commit()
    db_session.rollback()

