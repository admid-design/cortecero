BEGIN;

CREATE TABLE IF NOT EXISTS warehouse_locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, code)
);

CREATE INDEX IF NOT EXISTS idx_warehouse_locations_tenant_active
    ON warehouse_locations (tenant_id, active);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_warehouse_locations_code_not_empty'
    ) THEN
        ALTER TABLE warehouse_locations
        ADD CONSTRAINT ck_warehouse_locations_code_not_empty
        CHECK (btrim(code) <> '');
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_warehouse_locations_name_not_empty'
    ) THEN
        ALTER TABLE warehouse_locations
        ADD CONSTRAINT ck_warehouse_locations_name_not_empty
        CHECK (btrim(name) <> '');
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_warehouse_locations_type_not_empty'
    ) THEN
        ALTER TABLE warehouse_locations
        ADD CONSTRAINT ck_warehouse_locations_type_not_empty
        CHECK (btrim(type) <> '');
    END IF;
END $$;

DROP TRIGGER IF EXISTS trg_warehouse_locations_updated_at ON warehouse_locations;
CREATE TRIGGER trg_warehouse_locations_updated_at
BEFORE UPDATE ON warehouse_locations
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMIT;
