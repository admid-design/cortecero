BEGIN;

CREATE TABLE IF NOT EXISTS customer_operational_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL,
    accept_orders BOOLEAN NOT NULL DEFAULT TRUE,
    window_start TIME NULL,
    window_end TIME NULL,
    min_lead_hours INTEGER NOT NULL DEFAULT 0,
    consolidate_by_default BOOLEAN NOT NULL DEFAULT FALSE,
    ops_note TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, customer_id),
    UNIQUE (id, tenant_id),
    CONSTRAINT fk_customer_operational_profiles_customer_tenant
      FOREIGN KEY (customer_id, tenant_id)
      REFERENCES customers(id, tenant_id)
      ON DELETE CASCADE,
    CONSTRAINT ck_customer_operational_profiles_min_lead_hours_non_negative
      CHECK (min_lead_hours >= 0),
    CONSTRAINT ck_customer_operational_profiles_window_pair
      CHECK (
        (window_start IS NULL AND window_end IS NULL)
        OR (window_start IS NOT NULL AND window_end IS NOT NULL)
      )
);

CREATE INDEX IF NOT EXISTS idx_customer_operational_profiles_tenant_customer
    ON customer_operational_profiles (tenant_id, customer_id);

DROP TRIGGER IF EXISTS trg_customer_operational_profiles_updated_at ON customer_operational_profiles;
CREATE TRIGGER trg_customer_operational_profiles_updated_at
BEFORE UPDATE ON customer_operational_profiles
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMIT;
