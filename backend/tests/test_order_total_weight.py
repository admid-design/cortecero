import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


def test_orders_total_weight_column_definition(db_session):
    row = db_session.execute(
        text(
            """
            SELECT
                data_type,
                numeric_precision,
                numeric_scale,
                is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'orders'
              AND column_name = 'total_weight_kg'
            """
        )
    ).fetchone()

    assert row is not None
    assert row.data_type == "numeric"
    assert row.numeric_precision == 14
    assert row.numeric_scale == 3
    assert row.is_nullable == "YES"


def test_orders_total_weight_non_negative_constraint(db_session):
    order_row = db_session.execute(text("SELECT id, tenant_id FROM orders LIMIT 1")).fetchone()
    assert order_row is not None

    # NULL should remain allowed for backward compatibility.
    db_session.execute(
        text("UPDATE orders SET total_weight_kg = NULL WHERE id = :id AND tenant_id = :tenant_id"),
        {"id": order_row.id, "tenant_id": order_row.tenant_id},
    )
    db_session.commit()

    with pytest.raises(DBAPIError):
        db_session.execute(
            text("UPDATE orders SET total_weight_kg = -1 WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": order_row.id, "tenant_id": order_row.tenant_id},
        )
        db_session.commit()
    db_session.rollback()
