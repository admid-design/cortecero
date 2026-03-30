BEGIN;

CREATE TABLE IF NOT EXISTS vehicles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    capacity_kg NUMERIC(14,3) NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (id, tenant_id),
    UNIQUE (tenant_id, code),
    CONSTRAINT ck_vehicles_capacity_kg_non_negative
      CHECK (capacity_kg IS NULL OR capacity_kg >= 0)
);

CREATE INDEX IF NOT EXISTS idx_vehicles_tenant_active
    ON vehicles (tenant_id, active);

ALTER TABLE plans
    ADD COLUMN IF NOT EXISTS vehicle_id UUID NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_plans_vehicle_tenant'
    ) THEN
        ALTER TABLE plans
            ADD CONSTRAINT fk_plans_vehicle_tenant
            FOREIGN KEY (vehicle_id, tenant_id)
            REFERENCES vehicles(id, tenant_id)
            ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_plans_tenant_vehicle
    ON plans (tenant_id, vehicle_id);

COMMIT;
