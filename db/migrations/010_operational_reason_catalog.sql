BEGIN;

CREATE TABLE IF NOT EXISTS operational_reason_catalog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    description TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_operational_reason_catalog_code UNIQUE (code),
    CONSTRAINT ck_operational_reason_catalog_code_format
      CHECK (code ~ '^[A-Z0-9_]+$'),
    CONSTRAINT ck_operational_reason_catalog_category_not_blank
      CHECK (length(btrim(category)) > 0),
    CONSTRAINT ck_operational_reason_catalog_description_not_blank
      CHECK (length(btrim(description)) > 0),
    CONSTRAINT ck_operational_reason_catalog_severity_allowed
      CHECK (severity IN ('low', 'medium', 'high', 'critical'))
);

CREATE INDEX IF NOT EXISTS idx_operational_reason_catalog_active_severity
    ON operational_reason_catalog (active, severity, code);

INSERT INTO operational_reason_catalog (code, category, severity, active, description)
VALUES
    (
        'CUSTOMER_DATE_BLOCKED',
        'customer_calendar',
        'critical',
        TRUE,
        'Customer has a blocked operational date for the service date.'
    ),
    (
        'CUSTOMER_NOT_ACCEPTING_ORDERS',
        'customer_policy',
        'critical',
        TRUE,
        'Customer profile currently does not accept orders.'
    ),
    (
        'OUTSIDE_CUSTOMER_WINDOW',
        'customer_window',
        'high',
        TRUE,
        'Order creation time falls outside the configured customer operational window.'
    ),
    (
        'INSUFFICIENT_LEAD_TIME',
        'lead_time',
        'medium',
        TRUE,
        'Order does not satisfy minimum lead time required by customer operational profile.'
    )
ON CONFLICT (code) DO UPDATE
SET
    category = EXCLUDED.category,
    severity = EXCLUDED.severity,
    active = EXCLUDED.active,
    description = EXCLUDED.description;

DROP TRIGGER IF EXISTS trg_operational_reason_catalog_updated_at ON operational_reason_catalog;
CREATE TRIGGER trg_operational_reason_catalog_updated_at
BEFORE UPDATE ON operational_reason_catalog
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMIT;
