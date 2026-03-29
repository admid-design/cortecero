BEGIN;

-- =========================
-- updated_at columns for admin master data
-- =========================
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;
ALTER TABLE tenants ALTER COLUMN updated_at SET DEFAULT NOW();
UPDATE tenants SET updated_at = NOW() WHERE updated_at IS NULL;
ALTER TABLE tenants ALTER COLUMN updated_at SET NOT NULL;

ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;
ALTER TABLE users ALTER COLUMN updated_at SET DEFAULT NOW();
UPDATE users SET updated_at = NOW() WHERE updated_at IS NULL;
ALTER TABLE users ALTER COLUMN updated_at SET NOT NULL;

ALTER TABLE zones ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;
ALTER TABLE zones ALTER COLUMN updated_at SET DEFAULT NOW();
UPDATE zones SET updated_at = NOW() WHERE updated_at IS NULL;
ALTER TABLE zones ALTER COLUMN updated_at SET NOT NULL;

ALTER TABLE customers ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;
ALTER TABLE customers ALTER COLUMN updated_at SET DEFAULT NOW();
UPDATE customers SET updated_at = NOW() WHERE updated_at IS NULL;
ALTER TABLE customers ALTER COLUMN updated_at SET NOT NULL;

-- =========================
-- indexes for admin queries
-- =========================
CREATE INDEX IF NOT EXISTS idx_zones_tenant_active
    ON zones (tenant_id, active);

CREATE INDEX IF NOT EXISTS idx_customers_tenant_active_zone
    ON customers (tenant_id, active, zone_id);

CREATE INDEX IF NOT EXISTS idx_users_tenant_active_role
    ON users (tenant_id, is_active, role);

-- =========================
-- updated_at triggers
-- =========================
DROP TRIGGER IF EXISTS trg_tenants_updated_at ON tenants;
CREATE TRIGGER trg_tenants_updated_at
BEFORE UPDATE ON tenants
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_zones_updated_at ON zones;
CREATE TRIGGER trg_zones_updated_at
BEFORE UPDATE ON zones
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_customers_updated_at ON customers;
CREATE TRIGGER trg_customers_updated_at
BEFORE UPDATE ON customers
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMIT;
