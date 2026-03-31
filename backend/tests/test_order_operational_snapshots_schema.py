from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


def test_order_operational_snapshots_schema_definition(db_session):
    snapshot_columns = db_session.execute(
        text(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'order_operational_snapshots'
            ORDER BY ordinal_position
            """
        )
    ).fetchall()

    assert snapshot_columns
    by_name = {row.column_name: row for row in snapshot_columns}
    assert by_name["id"].data_type == "uuid"
    assert by_name["tenant_id"].data_type == "uuid"
    assert by_name["order_id"].data_type == "uuid"
    assert by_name["service_date"].data_type == "date"
    assert by_name["operational_state"].data_type == "text"
    assert by_name["operational_reason"].is_nullable == "YES"
    assert by_name["evaluation_ts"].data_type == "timestamp with time zone"
    assert by_name["timezone_used"].data_type == "text"
    assert by_name["rule_version"].data_type == "text"
    assert by_name["evidence_json"].data_type == "jsonb"

    indexes = {
        row.indexname
        for row in db_session.execute(
            text(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'order_operational_snapshots'
                """
            )
        ).fetchall()
    }
    assert "idx_order_operational_snapshots_tenant_service_date" in indexes
    assert "idx_order_operational_snapshots_tenant_order_eval_ts" in indexes


def test_order_operational_snapshots_constraints_and_append_only(db_session):
    order_row = db_session.execute(
        text("SELECT id, tenant_id, service_date FROM orders ORDER BY created_at ASC LIMIT 1")
    ).fetchone()
    assert order_row is not None

    # Eligible rows allow NULL reason.
    snapshot_id_eligible = uuid4()
    db_session.execute(
        text(
            """
            INSERT INTO order_operational_snapshots (
                id, tenant_id, order_id, service_date, operational_state,
                operational_reason, evaluation_ts, timezone_used, rule_version, evidence_json
            ) VALUES (
                :id, :tenant_id, :order_id, :service_date, 'eligible',
                NULL, :evaluation_ts, 'Europe/Madrid', 'r6-operational-eval-v1', '{"window_type":"none"}'::jsonb
            )
            """
        ),
        {
            "id": str(snapshot_id_eligible),
            "tenant_id": str(order_row.tenant_id),
            "order_id": str(order_row.id),
            "service_date": order_row.service_date,
            "evaluation_ts": datetime.now(UTC),
        },
    )

    # Restricted rows require reason.
    snapshot_id_restricted = uuid4()
    db_session.execute(
        text(
            """
            INSERT INTO order_operational_snapshots (
                id, tenant_id, order_id, service_date, operational_state,
                operational_reason, evaluation_ts, timezone_used, rule_version, evidence_json
            ) VALUES (
                :id, :tenant_id, :order_id, :service_date, 'restricted',
                'CUSTOMER_DATE_BLOCKED', :evaluation_ts, 'Europe/Madrid', 'r6-operational-eval-v1', '{"window_type":"none"}'::jsonb
            )
            """
        ),
        {
            "id": str(snapshot_id_restricted),
            "tenant_id": str(order_row.tenant_id),
            "order_id": str(order_row.id),
            "service_date": order_row.service_date,
            "evaluation_ts": datetime.now(UTC),
        },
    )
    db_session.commit()

    with pytest.raises(DBAPIError):
        db_session.execute(
            text(
                """
                INSERT INTO order_operational_snapshots (
                    id, tenant_id, order_id, service_date, operational_state,
                    operational_reason, evaluation_ts, timezone_used, rule_version, evidence_json
                ) VALUES (
                    :id, :tenant_id, :order_id, :service_date, 'restricted',
                    NULL, :evaluation_ts, 'Europe/Madrid', 'r6-operational-eval-v1', '{}'::jsonb
                )
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": str(order_row.tenant_id),
                "order_id": str(order_row.id),
                "service_date": order_row.service_date,
                "evaluation_ts": datetime.now(UTC),
            },
        )
        db_session.commit()
    db_session.rollback()

    with pytest.raises(DBAPIError):
        db_session.execute(
            text(
                """
                INSERT INTO order_operational_snapshots (
                    id, tenant_id, order_id, service_date, operational_state,
                    operational_reason, evaluation_ts, timezone_used, rule_version, evidence_json
                ) VALUES (
                    :id, :tenant_id, :order_id, :service_date, 'eligible',
                    'CUSTOMER_DATE_BLOCKED', :evaluation_ts, 'Europe/Madrid', 'r6-operational-eval-v1', '{}'::jsonb
                )
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": str(order_row.tenant_id),
                "order_id": str(order_row.id),
                "service_date": order_row.service_date,
                "evaluation_ts": datetime.now(UTC),
            },
        )
        db_session.commit()
    db_session.rollback()

    # Tenant scope must match order tenant.
    other_tenant_id = uuid4()
    db_session.execute(
        text(
            """
            INSERT INTO tenants (id, name, slug, default_cutoff_time, default_timezone, auto_lock_enabled, created_at, updated_at)
            VALUES (:id, :name, :slug, TIME '10:00', 'Europe/Madrid', FALSE, NOW(), NOW())
            """
        ),
        {
            "id": str(other_tenant_id),
            "name": "Tenant FK Snapshots",
            "slug": f"tenant-fk-snapshots-{uuid4()}",
        },
    )
    db_session.commit()

    with pytest.raises(DBAPIError):
        db_session.execute(
            text(
                """
                INSERT INTO order_operational_snapshots (
                    id, tenant_id, order_id, service_date, operational_state,
                    operational_reason, evaluation_ts, timezone_used, rule_version, evidence_json
                ) VALUES (
                    :id, :tenant_id, :order_id, :service_date, 'restricted',
                    'CUSTOMER_DATE_BLOCKED', :evaluation_ts, 'Europe/Madrid', 'r6-operational-eval-v1', '{}'::jsonb
                )
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": str(other_tenant_id),
                "order_id": str(order_row.id),
                "service_date": order_row.service_date,
                "evaluation_ts": datetime.now(UTC),
            },
        )
        db_session.commit()
    db_session.rollback()

    with pytest.raises(DBAPIError) as update_exc:
        db_session.execute(
            text("UPDATE order_operational_snapshots SET rule_version = 'changed' WHERE id = :id"),
            {"id": str(snapshot_id_restricted)},
        )
        db_session.commit()
    db_session.rollback()
    assert "append-only" in str(update_exc.value).lower()

    with pytest.raises(DBAPIError) as delete_exc:
        db_session.execute(
            text("DELETE FROM order_operational_snapshots WHERE id = :id"),
            {"id": str(snapshot_id_restricted)},
        )
        db_session.commit()
    db_session.rollback()
    assert "append-only" in str(delete_exc.value).lower()
