BEGIN;

CREATE TABLE IF NOT EXISTS order_operational_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    order_id UUID NOT NULL,
    service_date DATE NOT NULL,
    operational_state TEXT NOT NULL,
    operational_reason TEXT NULL,
    evaluation_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    timezone_used TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT fk_order_operational_snapshots_order_tenant
      FOREIGN KEY (order_id, tenant_id)
      REFERENCES orders(id, tenant_id)
      ON DELETE CASCADE,
    CONSTRAINT ck_order_operational_snapshots_state_allowed
      CHECK (operational_state IN ('eligible', 'restricted')),
    CONSTRAINT ck_order_operational_snapshots_reason_consistency
      CHECK (
        (operational_state = 'eligible' AND operational_reason IS NULL)
        OR (operational_state = 'restricted' AND operational_reason IS NOT NULL)
      ),
    CONSTRAINT ck_order_operational_snapshots_reason_code_format
      CHECK (operational_reason IS NULL OR operational_reason ~ '^[A-Z0-9_]+$'),
    CONSTRAINT ck_order_operational_snapshots_timezone_not_blank
      CHECK (length(btrim(timezone_used)) > 0),
    CONSTRAINT ck_order_operational_snapshots_rule_version_not_blank
      CHECK (length(btrim(rule_version)) > 0),
    CONSTRAINT ck_order_operational_snapshots_evidence_object
      CHECK (jsonb_typeof(evidence_json) = 'object')
);

CREATE INDEX IF NOT EXISTS idx_order_operational_snapshots_tenant_service_date
    ON order_operational_snapshots (tenant_id, service_date);

CREATE INDEX IF NOT EXISTS idx_order_operational_snapshots_tenant_order_eval_ts
    ON order_operational_snapshots (tenant_id, order_id, evaluation_ts DESC);

CREATE OR REPLACE FUNCTION prevent_order_operational_snapshots_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'order_operational_snapshots is append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_order_operational_snapshots_no_update ON order_operational_snapshots;
CREATE TRIGGER trg_order_operational_snapshots_no_update
BEFORE UPDATE ON order_operational_snapshots
FOR EACH ROW
EXECUTE FUNCTION prevent_order_operational_snapshots_mutation();

DROP TRIGGER IF EXISTS trg_order_operational_snapshots_no_delete ON order_operational_snapshots;
CREATE TRIGGER trg_order_operational_snapshots_no_delete
BEFORE DELETE ON order_operational_snapshots
FOR EACH ROW
EXECUTE FUNCTION prevent_order_operational_snapshots_mutation();

COMMIT;
