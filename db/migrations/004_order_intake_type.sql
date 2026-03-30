BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'order_intake_type') THEN
        CREATE TYPE order_intake_type AS ENUM ('new_order', 'same_customer_addon');
    END IF;
END $$;

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS intake_type order_intake_type;

ALTER TABLE orders
    ALTER COLUMN intake_type SET DEFAULT 'new_order';

UPDATE orders
SET intake_type = 'new_order'
WHERE intake_type IS NULL;

ALTER TABLE orders
    ALTER COLUMN intake_type SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_orders_tenant_customer_service_created
    ON orders (tenant_id, customer_id, service_date, created_at);

COMMIT;
