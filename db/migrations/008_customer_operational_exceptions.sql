BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_type
        WHERE typname = 'customer_operational_exception_type'
    ) THEN
        CREATE TYPE customer_operational_exception_type AS ENUM ('blocked', 'restricted');
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS customer_operational_exceptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL,
    date DATE NOT NULL,
    type customer_operational_exception_type NOT NULL,
    note TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, customer_id, date, type),
    UNIQUE (id, tenant_id),
    CONSTRAINT fk_customer_operational_exceptions_customer_tenant
      FOREIGN KEY (customer_id, tenant_id)
      REFERENCES customers(id, tenant_id)
      ON DELETE CASCADE,
    CONSTRAINT ck_customer_operational_exceptions_note_not_blank
      CHECK (length(btrim(note)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_customer_operational_exceptions_tenant_customer_date
    ON customer_operational_exceptions (tenant_id, customer_id, date);

COMMIT;
