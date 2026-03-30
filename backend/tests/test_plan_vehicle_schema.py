from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


def test_plan_vehicle_schema_definition(db_session):
    plan_vehicle_column = db_session.execute(
        text(
            """
            SELECT data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'plans'
              AND column_name = 'vehicle_id'
            """
        )
    ).fetchone()
    assert plan_vehicle_column is not None
    assert plan_vehicle_column.data_type == "uuid"
    assert plan_vehicle_column.is_nullable == "YES"

    vehicle_capacity_column = db_session.execute(
        text(
            """
            SELECT data_type, numeric_precision, numeric_scale, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'vehicles'
              AND column_name = 'capacity_kg'
            """
        )
    ).fetchone()
    assert vehicle_capacity_column is not None
    assert vehicle_capacity_column.data_type == "numeric"
    assert vehicle_capacity_column.numeric_precision == 14
    assert vehicle_capacity_column.numeric_scale == 3
    assert vehicle_capacity_column.is_nullable == "YES"


def test_vehicles_capacity_non_negative_constraint(db_session):
    tenant_id = db_session.execute(text("SELECT id FROM tenants LIMIT 1")).scalar_one()
    with pytest.raises(DBAPIError):
        db_session.execute(
            text(
                """
                INSERT INTO vehicles (id, tenant_id, code, name, capacity_kg, active, created_at)
                VALUES (:id, :tenant_id, :code, :name, :capacity_kg, TRUE, :created_at)
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": str(tenant_id),
                "code": f"NEG-{uuid4()}",
                "name": "Vehiculo Negativo",
                "capacity_kg": -0.001,
                "created_at": datetime.now(UTC),
            },
        )
        db_session.commit()
    db_session.rollback()


def test_plans_vehicle_fk_enforces_tenant_scope(db_session):
    plan_row = db_session.execute(text("SELECT id, tenant_id FROM plans LIMIT 1")).fetchone()
    assert plan_row is not None

    tenant_b_id = uuid4()
    db_session.execute(
        text(
            """
            INSERT INTO tenants (id, name, slug, default_cutoff_time, default_timezone, auto_lock_enabled, created_at)
            VALUES (:id, :name, :slug, TIME '10:00', 'Europe/Madrid', FALSE, NOW())
            """
        ),
        {"id": str(tenant_b_id), "name": "Tenant B Plan Vehicle FK", "slug": f"tenant-b-plan-vehicle-fk-{uuid4()}"},
    )
    vehicle_b_id = uuid4()
    db_session.execute(
        text(
            """
            INSERT INTO vehicles (id, tenant_id, code, name, capacity_kg, active, created_at)
            VALUES (:id, :tenant_id, :code, :name, :capacity_kg, TRUE, NOW())
            """
        ),
        {
            "id": str(vehicle_b_id),
            "tenant_id": str(tenant_b_id),
            "code": f"FK-{uuid4()}",
            "name": "Vehiculo Tenant B",
            "capacity_kg": 1000,
        },
    )
    db_session.commit()

    with pytest.raises(DBAPIError):
        db_session.execute(
            text("UPDATE plans SET vehicle_id = :vehicle_id WHERE id = :plan_id AND tenant_id = :tenant_id"),
            {
                "vehicle_id": str(vehicle_b_id),
                "plan_id": str(plan_row.id),
                "tenant_id": str(plan_row.tenant_id),
            },
        )
        db_session.commit()
    db_session.rollback()
