BEGIN;

CREATE INDEX IF NOT EXISTS idx_orders_tenant_service_customer_zone
    ON orders (tenant_id, service_date, customer_id, zone_id);

CREATE INDEX IF NOT EXISTS idx_customer_operational_profiles_tenant_customer
    ON customer_operational_profiles (tenant_id, customer_id);

CREATE INDEX IF NOT EXISTS idx_customer_operational_exceptions_tenant_customer_date
    ON customer_operational_exceptions (tenant_id, customer_id, date);

COMMIT;
