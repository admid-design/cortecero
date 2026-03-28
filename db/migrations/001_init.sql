BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =========================
-- ENUMS
-- =========================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
        CREATE TYPE user_role AS ENUM ('office', 'logistics', 'admin');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'plan_status') THEN
        CREATE TYPE plan_status AS ENUM ('open', 'locked', 'dispatched');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'order_status') THEN
        CREATE TYPE order_status AS ENUM (
            'ingested',
            'late_pending_exception',
            'ready_for_planning',
            'planned',
            'exception_rejected'
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'exception_type') THEN
        CREATE TYPE exception_type AS ENUM ('late_order');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'exception_status') THEN
        CREATE TYPE exception_status AS ENUM ('pending', 'approved', 'rejected');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'scope_type') THEN
        CREATE TYPE scope_type AS ENUM ('zone', 'customer');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'inclusion_type') THEN
        CREATE TYPE inclusion_type AS ENUM ('normal', 'exception');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'entity_type') THEN
        CREATE TYPE entity_type AS ENUM ('order', 'exception', 'plan', 'plan_order');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'source_channel') THEN
        CREATE TYPE source_channel AS ENUM (
            'sales',
            'office',
            'direct_customer',
            'hotel_direct',
            'other'
        );
    END IF;
END $$;

-- =========================
-- TENANTS / USERS
-- =========================
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    default_cutoff_time TIME NOT NULL DEFAULT TIME '10:00',
    default_timezone TEXT NOT NULL DEFAULT 'Europe/Madrid',
    auto_lock_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role user_role NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, email),
    UNIQUE (id, tenant_id)
);

-- =========================
-- MASTER DATA
-- =========================
CREATE TABLE IF NOT EXISTS zones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    default_cutoff_time TIME NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'Europe/Madrid',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, name),
    UNIQUE (id, tenant_id)
);

CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    zone_id UUID NOT NULL,
    name TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    cutoff_override_time TIME NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (id, tenant_id),
    CONSTRAINT fk_customers_zone_tenant
      FOREIGN KEY (zone_id, tenant_id)
      REFERENCES zones(id, tenant_id)
      ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_customers_tenant_zone
    ON customers (tenant_id, zone_id);

CREATE TABLE IF NOT EXISTS cutoff_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    scope_type scope_type NOT NULL,
    scope_id UUID NOT NULL,
    cutoff_time TIME NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE INDEX IF NOT EXISTS idx_cutoff_rules_lookup
    ON cutoff_rules (tenant_id, scope_type, scope_id, active, effective_from);

-- =========================
-- ORDERS
-- =========================
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL,
    zone_id UUID NOT NULL,
    external_ref TEXT NOT NULL,
    requested_date DATE NULL,
    service_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    status order_status NOT NULL DEFAULT 'ingested',
    is_late BOOLEAN NOT NULL DEFAULT FALSE,
    lateness_reason TEXT NULL,
    effective_cutoff_at TIMESTAMPTZ NOT NULL,
    source_channel source_channel NOT NULL DEFAULT 'other',
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, external_ref, service_date),
    UNIQUE (id, tenant_id),
    CONSTRAINT fk_orders_customer_tenant
      FOREIGN KEY (customer_id, tenant_id)
      REFERENCES customers(id, tenant_id)
      ON DELETE RESTRICT,
    CONSTRAINT fk_orders_zone_tenant
      FOREIGN KEY (zone_id, tenant_id)
      REFERENCES zones(id, tenant_id)
      ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_orders_tenant_service_date
    ON orders (tenant_id, service_date);

CREATE INDEX IF NOT EXISTS idx_orders_tenant_zone_status
    ON orders (tenant_id, zone_id, status);

CREATE INDEX IF NOT EXISTS idx_orders_tenant_is_late
    ON orders (tenant_id, is_late);

CREATE TABLE IF NOT EXISTS order_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    order_id UUID NOT NULL,
    sku TEXT NOT NULL,
    qty NUMERIC(14,3) NOT NULL,
    weight_kg NUMERIC(14,3) NULL,
    volume_m3 NUMERIC(14,6) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_order_lines_order_tenant
      FOREIGN KEY (order_id, tenant_id)
      REFERENCES orders(id, tenant_id)
      ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_order_lines_order
    ON order_lines (order_id);

-- =========================
-- PLANS
-- =========================
CREATE TABLE IF NOT EXISTS plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    service_date DATE NOT NULL,
    zone_id UUID NOT NULL,
    status plan_status NOT NULL DEFAULT 'open',
    version INTEGER NOT NULL DEFAULT 1,
    locked_at TIMESTAMPTZ NULL,
    locked_by UUID NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, service_date, zone_id),
    UNIQUE (id, tenant_id),
    CONSTRAINT fk_plans_zone_tenant
      FOREIGN KEY (zone_id, tenant_id)
      REFERENCES zones(id, tenant_id)
      ON DELETE RESTRICT,
    CONSTRAINT fk_plans_locked_by_tenant
      FOREIGN KEY (locked_by, tenant_id)
      REFERENCES users(id, tenant_id)
      ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_plans_tenant_service_date
    ON plans (tenant_id, service_date);

CREATE INDEX IF NOT EXISTS idx_plans_tenant_zone_status
    ON plans (tenant_id, zone_id, status);

CREATE TABLE IF NOT EXISTS plan_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    plan_id UUID NOT NULL,
    order_id UUID NOT NULL,
    inclusion_type inclusion_type NOT NULL,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    added_by UUID NULL,
    UNIQUE (plan_id, order_id),
    UNIQUE (order_id),
    CONSTRAINT fk_plan_orders_plan_tenant
      FOREIGN KEY (plan_id, tenant_id)
      REFERENCES plans(id, tenant_id)
      ON DELETE CASCADE,
    CONSTRAINT fk_plan_orders_order_tenant
      FOREIGN KEY (order_id, tenant_id)
      REFERENCES orders(id, tenant_id)
      ON DELETE CASCADE,
    CONSTRAINT fk_plan_orders_added_by_tenant
      FOREIGN KEY (added_by, tenant_id)
      REFERENCES users(id, tenant_id)
      ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_plan_orders_plan
    ON plan_orders (plan_id);

CREATE INDEX IF NOT EXISTS idx_plan_orders_order
    ON plan_orders (order_id);

-- =========================
-- EXCEPTIONS
-- =========================
CREATE TABLE IF NOT EXISTS exceptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    order_id UUID NOT NULL,
    type exception_type NOT NULL,
    status exception_status NOT NULL DEFAULT 'pending',
    requested_by UUID NOT NULL,
    resolved_by UUID NULL,
    resolved_at TIMESTAMPTZ NULL,
    note TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_exceptions_order_tenant
      FOREIGN KEY (order_id, tenant_id)
      REFERENCES orders(id, tenant_id)
      ON DELETE CASCADE,
    CONSTRAINT fk_exceptions_requested_by_tenant
      FOREIGN KEY (requested_by, tenant_id)
      REFERENCES users(id, tenant_id)
      ON DELETE RESTRICT,
    CONSTRAINT fk_exceptions_resolved_by_tenant
      FOREIGN KEY (resolved_by, tenant_id)
      REFERENCES users(id, tenant_id)
      ON DELETE SET NULL,
    CHECK (
      (status = 'pending' AND resolved_by IS NULL AND resolved_at IS NULL)
      OR (status IN ('approved', 'rejected') AND resolved_by IS NOT NULL AND resolved_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_exceptions_order
    ON exceptions (order_id);

CREATE INDEX IF NOT EXISTS idx_exceptions_status
    ON exceptions (tenant_id, status);

-- Solo una excepción pendiente por pedido
CREATE UNIQUE INDEX IF NOT EXISTS uq_exceptions_one_pending_per_order
    ON exceptions (order_id)
    WHERE status = 'pending';

-- =========================
-- AUDIT
-- =========================
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    entity_type entity_type NOT NULL,
    entity_id UUID NOT NULL,
    action TEXT NOT NULL,
    actor_id UUID NULL,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    request_id TEXT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT fk_audit_actor_tenant
      FOREIGN KEY (actor_id, tenant_id)
      REFERENCES users(id, tenant_id)
      ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_entity
    ON audit_logs (tenant_id, entity_type, entity_id, ts DESC);

CREATE INDEX IF NOT EXISTS idx_audit_logs_action
    ON audit_logs (tenant_id, action, ts DESC);

-- =========================
-- updated_at trigger
-- =========================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_orders_updated_at ON orders;
CREATE TRIGGER trg_orders_updated_at
BEFORE UPDATE ON orders
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_plans_updated_at ON plans;
CREATE TRIGGER trg_plans_updated_at
BEFORE UPDATE ON plans
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMIT;
