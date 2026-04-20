-- Migration 028: Plantillas de ruta para importación XLSX de rutas estacionales
-- ROUTE-TEMPLATE-MODEL-001
--
-- Crea dos tablas:
--   route_templates       — una plantilla por (vehicle, day_of_week, season)
--   route_template_stops  — paradas ordenadas de cada plantilla
--
-- Idempotente: CREATE TABLE IF NOT EXISTS + DO $$ EXCEPTION WHEN duplicate_object

-- ============================================================================
-- 1. route_templates
-- ============================================================================
CREATE TABLE IF NOT EXISTS route_templates (
    id          UUID PRIMARY KEY,
    tenant_id   UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name        TEXT        NOT NULL,
    season      TEXT,                    -- 'verano' | 'invierno' | NULL
    vehicle_id  UUID        REFERENCES vehicles(id) ON DELETE SET NULL,
    day_of_week SMALLINT,               -- 1=Lun … 7=Dom (ISO 8601); NULL = sin día fijo
    shift_start TIME,
    shift_end   TIME,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_route_templates_tenant
    ON route_templates (tenant_id);

CREATE INDEX IF NOT EXISTS idx_route_templates_tenant_season
    ON route_templates (tenant_id, season);

-- ============================================================================
-- 2. route_template_stops
-- ============================================================================
CREATE TABLE IF NOT EXISTS route_template_stops (
    id              UUID    PRIMARY KEY,
    tenant_id       UUID    NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    template_id     UUID    NOT NULL REFERENCES route_templates(id) ON DELETE CASCADE,
    sequence_number INTEGER NOT NULL,
    customer_id     UUID    REFERENCES customers(id) ON DELETE SET NULL,
    lat             NUMERIC(9,6),
    lng             NUMERIC(9,6),
    address         TEXT,
    duration_min    INTEGER NOT NULL DEFAULT 10,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_route_template_stops_seq UNIQUE (template_id, sequence_number)
);

CREATE INDEX IF NOT EXISTS idx_route_template_stops_template
    ON route_template_stops (template_id);

CREATE INDEX IF NOT EXISTS idx_route_template_stops_tenant
    ON route_template_stops (tenant_id);
