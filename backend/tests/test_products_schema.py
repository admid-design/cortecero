from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


def test_products_schema_definition(db_session):
    product_columns = db_session.execute(
        text(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'products'
            ORDER BY ordinal_position
            """
        )
    ).fetchall()

    assert product_columns
    by_name = {row.column_name: row for row in product_columns}
    assert by_name["id"].data_type == "uuid"
    assert by_name["tenant_id"].data_type == "uuid"
    assert by_name["sku"].data_type == "text"
    assert by_name["name"].data_type == "text"
    assert by_name["barcode"].is_nullable == "YES"
    assert by_name["uom"].data_type == "text"
    assert by_name["active"].data_type == "boolean"
    assert by_name["created_at"].data_type == "timestamp with time zone"
    assert by_name["updated_at"].data_type == "timestamp with time zone"

    indexes = {
        row.indexname
        for row in db_session.execute(
            text(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'products'
                """
            )
        ).fetchall()
    }
    assert "products_pkey" in indexes
    assert "products_tenant_id_sku_key" in indexes
    assert "idx_products_tenant_active" in indexes
    assert "idx_products_tenant_barcode" in indexes


def test_products_unique_sku_by_tenant_and_non_empty_constraints(db_session):
    tenant_id = db_session.execute(text("SELECT id FROM tenants LIMIT 1")).scalar_one()
    now = datetime.now(UTC)

    sku = f"SKU-{uuid4()}"
    db_session.execute(
        text(
            """
            INSERT INTO products (id, tenant_id, sku, name, barcode, uom, active, created_at, updated_at)
            VALUES (:id, :tenant_id, :sku, :name, :barcode, :uom, TRUE, :created_at, :updated_at)
            """
        ),
        {
            "id": str(uuid4()),
            "tenant_id": str(tenant_id),
            "sku": sku,
            "name": "Producto A",
            "barcode": "EAN001",
            "uom": "unit",
            "created_at": now,
            "updated_at": now,
        },
    )
    db_session.commit()

    with pytest.raises(DBAPIError):
        db_session.execute(
            text(
                """
                INSERT INTO products (id, tenant_id, sku, name, barcode, uom, active, created_at, updated_at)
                VALUES (:id, :tenant_id, :sku, :name, :barcode, :uom, TRUE, :created_at, :updated_at)
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": str(tenant_id),
                "sku": sku,
                "name": "Producto Duplicado",
                "barcode": "EAN002",
                "uom": "unit",
                "created_at": now,
                "updated_at": now,
            },
        )
        db_session.commit()
    db_session.rollback()

    other_tenant_id = uuid4()
    db_session.execute(
        text(
            """
            INSERT INTO tenants (id, name, slug, default_cutoff_time, default_timezone, auto_lock_enabled, created_at, updated_at)
            VALUES (:id, :name, :slug, TIME '10:00', 'Europe/Madrid', FALSE, :created_at, :updated_at)
            """
        ),
        {
            "id": str(other_tenant_id),
            "name": "Tenant Productos",
            "slug": f"tenant-products-{uuid4()}",
            "created_at": now,
            "updated_at": now,
        },
    )
    db_session.execute(
        text(
            """
            INSERT INTO products (id, tenant_id, sku, name, barcode, uom, active, created_at, updated_at)
            VALUES (:id, :tenant_id, :sku, :name, :barcode, :uom, TRUE, :created_at, :updated_at)
            """
        ),
        {
            "id": str(uuid4()),
            "tenant_id": str(other_tenant_id),
            "sku": sku,
            "name": "Producto Otro Tenant",
            "barcode": "EAN003",
            "uom": "unit",
            "created_at": now,
            "updated_at": now,
        },
    )
    db_session.commit()

    with pytest.raises(DBAPIError):
        db_session.execute(
            text(
                """
                INSERT INTO products (id, tenant_id, sku, name, barcode, uom, active, created_at, updated_at)
                VALUES (:id, :tenant_id, :sku, :name, :barcode, :uom, TRUE, :created_at, :updated_at)
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": str(tenant_id),
                "sku": "   ",
                "name": "Producto Invalido SKU",
                "barcode": None,
                "uom": "unit",
                "created_at": now,
                "updated_at": now,
            },
        )
        db_session.commit()
    db_session.rollback()

    with pytest.raises(DBAPIError):
        db_session.execute(
            text(
                """
                INSERT INTO products (id, tenant_id, sku, name, barcode, uom, active, created_at, updated_at)
                VALUES (:id, :tenant_id, :sku, :name, :barcode, :uom, TRUE, :created_at, :updated_at)
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": str(tenant_id),
                "sku": f"SKU-{uuid4()}",
                "name": "Producto Invalido UOM",
                "barcode": None,
                "uom": "  ",
                "created_at": now,
                "updated_at": now,
            },
        )
        db_session.commit()
    db_session.rollback()

