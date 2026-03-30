BEGIN;

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS total_weight_kg NUMERIC(14,3) NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_orders_total_weight_kg_non_negative'
    ) THEN
        ALTER TABLE orders
            ADD CONSTRAINT ck_orders_total_weight_kg_non_negative
            CHECK (total_weight_kg IS NULL OR total_weight_kg >= 0);
    END IF;
END $$;

COMMIT;
