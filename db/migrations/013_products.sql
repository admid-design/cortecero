BEGIN;

CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    sku TEXT NOT NULL,
    name TEXT NOT NULL,
    barcode TEXT NULL,
    uom TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, sku)
);

CREATE INDEX IF NOT EXISTS idx_products_tenant_active
    ON products (tenant_id, active);

CREATE INDEX IF NOT EXISTS idx_products_tenant_barcode
    ON products (tenant_id, barcode)
    WHERE barcode IS NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_products_sku_not_empty'
    ) THEN
        ALTER TABLE products
        ADD CONSTRAINT ck_products_sku_not_empty
        CHECK (btrim(sku) <> '');
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_products_name_not_empty'
    ) THEN
        ALTER TABLE products
        ADD CONSTRAINT ck_products_name_not_empty
        CHECK (btrim(name) <> '');
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_products_uom_not_empty'
    ) THEN
        ALTER TABLE products
        ADD CONSTRAINT ck_products_uom_not_empty
        CHECK (btrim(uom) <> '');
    END IF;
END $$;

DROP TRIGGER IF EXISTS trg_products_updated_at ON products;
CREATE TRIGGER trg_products_updated_at
BEFORE UPDATE ON products
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMIT;
