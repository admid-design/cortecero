BEGIN;

-- ============================================================================
-- ROUTING POC: Driver, Route, RouteStop, Incident, RouteEvent entities
-- Ticket: POC-BLK-A-001
-- Extends: Order (post-planned states), Plan (dispatched state), Vehicle
-- ============================================================================

-- ============================================================================
-- 1. ENUMS / VOCABULARIOS CERRADOS
-- ============================================================================

-- route_status: draft -> planned -> dispatched -> in_progress -> completed
-- También permite: draft/planned/dispatched -> cancelled
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'route_status') THEN
        CREATE TYPE route_status AS ENUM (
            'draft',
            'planned',
            'dispatched',
            'in_progress',
            'completed',
            'cancelled'
        );
    END IF;
END $$;

-- route_stop_status: pending -> en_route -> arrived -> completed/failed
-- También permite: pending -> skipped
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'route_stop_status') THEN
        CREATE TYPE route_stop_status AS ENUM (
            'pending',
            'en_route',
            'arrived',
            'completed',
            'failed',
            'skipped'
        );
    END IF;
END $$;

-- incident_type: access_blocked, customer_absent, customer_rejected, etc.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'incident_type') THEN
        CREATE TYPE incident_type AS ENUM (
            'access_blocked',
            'customer_absent',
            'customer_rejected',
            'vehicle_issue',
            'wrong_address',
            'damaged_goods',
            'other'
        );
    END IF;
END $$;

-- incident_severity: low, medium, high, critical
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'incident_severity') THEN
        CREATE TYPE incident_severity AS ENUM (
            'low',
            'medium',
            'high',
            'critical'
        );
    END IF;
END $$;

-- incident_status: open -> reviewed -> resolved
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'incident_status') THEN
        CREATE TYPE incident_status AS ENUM (
            'open',
            'reviewed',
            'resolved'
        );
    END IF;
END $$;

-- route_event_type: eventos operativos
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'route_event_type') THEN
        CREATE TYPE route_event_type AS ENUM (
            'route_created',
            'route_planned',
            'route_dispatched',
            'route_started',
            'route_completed',
            'route_cancelled',
            'stop_en_route',
            'stop_arrived',
            'stop_completed',
            'stop_failed',
            'stop_skipped',
            'incident_reported',
            'incident_reviewed',
            'incident_resolved',
            'order_returned_to_planning'
        );
    END IF;
END $$;

-- actor_type para RouteEvent
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'route_event_actor_type') THEN
        CREATE TYPE route_event_actor_type AS ENUM (
            'dispatcher',
            'driver',
            'system'
        );
    END IF;
END $$;

-- ============================================================================
-- 2. DRIVER TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS drivers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    vehicle_id UUID NULL,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (id, tenant_id),
    UNIQUE (tenant_id, phone),
    CONSTRAINT ck_drivers_name_not_empty
        CHECK (btrim(name) <> ''),
    CONSTRAINT ck_drivers_phone_not_empty
        CHECK (btrim(phone) <> '')
);

-- FK composition: (vehicle_id, tenant_id) -> vehicles
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_drivers_vehicle_tenant'
    ) THEN
        ALTER TABLE drivers
            ADD CONSTRAINT fk_drivers_vehicle_tenant
            FOREIGN KEY (vehicle_id, tenant_id)
            REFERENCES vehicles(id, tenant_id)
            ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_drivers_tenant_active
    ON drivers (tenant_id, is_active);

CREATE INDEX IF NOT EXISTS idx_drivers_tenant_vehicle
    ON drivers (tenant_id, vehicle_id);

-- Trigger para updated_at
DROP TRIGGER IF EXISTS trg_drivers_updated_at ON drivers;
CREATE TRIGGER trg_drivers_updated_at
BEFORE UPDATE ON drivers
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- 3. ROUTE TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS routes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    plan_id UUID NOT NULL,
    vehicle_id UUID NOT NULL,
    driver_id UUID NULL,
    service_date DATE NOT NULL,
    status route_status NOT NULL DEFAULT 'draft',
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    optimization_request_id TEXT NULL,
    optimization_response_json JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    dispatched_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    UNIQUE (id, tenant_id),
    CONSTRAINT ck_routes_optimization_response_is_object
        CHECK (
            optimization_response_json IS NULL
            OR jsonb_typeof(optimization_response_json) IN ('object', 'null')
        )
);

-- FKs composition
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_routes_plan_tenant'
    ) THEN
        ALTER TABLE routes
            ADD CONSTRAINT fk_routes_plan_tenant
            FOREIGN KEY (plan_id, tenant_id)
            REFERENCES plans(id, tenant_id)
            ON DELETE CASCADE;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_routes_vehicle_tenant'
    ) THEN
        ALTER TABLE routes
            ADD CONSTRAINT fk_routes_vehicle_tenant
            FOREIGN KEY (vehicle_id, tenant_id)
            REFERENCES vehicles(id, tenant_id)
            ON DELETE RESTRICT;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_routes_driver_tenant'
    ) THEN
        ALTER TABLE routes
            ADD CONSTRAINT fk_routes_driver_tenant
            FOREIGN KEY (driver_id, tenant_id)
            REFERENCES drivers(id, tenant_id)
            ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_routes_tenant_plan
    ON routes (tenant_id, plan_id);

CREATE INDEX IF NOT EXISTS idx_routes_tenant_vehicle_status
    ON routes (tenant_id, vehicle_id, status);

CREATE INDEX IF NOT EXISTS idx_routes_tenant_driver_service_date
    ON routes (tenant_id, driver_id, service_date);

CREATE INDEX IF NOT EXISTS idx_routes_service_date_status
    ON routes (service_date, status);

DROP TRIGGER IF EXISTS trg_routes_updated_at ON routes;
CREATE TRIGGER trg_routes_updated_at
BEFORE UPDATE ON routes
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- 4. ROUTE_STOP TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS route_stops (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    route_id UUID NOT NULL,
    order_id UUID NOT NULL,
    sequence_number INTEGER NOT NULL CHECK (sequence_number >= 1),
    estimated_arrival_at TIMESTAMPTZ NULL,
    estimated_service_minutes INTEGER NOT NULL DEFAULT 10 CHECK (estimated_service_minutes > 0),
    status route_stop_status NOT NULL DEFAULT 'pending',
    arrived_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    failed_at TIMESTAMPTZ NULL,
    failure_reason TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (id, tenant_id),
    CONSTRAINT ck_route_stops_failure_reason_consistency
        CHECK (
            (status = 'failed' AND failure_reason IS NOT NULL)
            OR (status != 'failed' AND failure_reason IS NULL)
        ),
    CONSTRAINT ck_route_stops_completion_consistency
        CHECK (
            (status = 'completed' AND completed_at IS NOT NULL)
            OR (status != 'completed' AND completed_at IS NULL)
        ),
    CONSTRAINT ck_route_stops_failure_consistency
        CHECK (
            (status = 'failed' AND failed_at IS NOT NULL)
            OR (status != 'failed' AND failed_at IS NULL)
        ),
    CONSTRAINT ck_route_stops_arrived_consistency
        CHECK (
            (status IN ('arrived', 'completed', 'failed') AND arrived_at IS NOT NULL)
            OR (status NOT IN ('arrived', 'completed', 'failed') AND arrived_at IS NULL)
        )
);

-- FKs composition
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_route_stops_route_tenant'
    ) THEN
        ALTER TABLE route_stops
            ADD CONSTRAINT fk_route_stops_route_tenant
            FOREIGN KEY (route_id, tenant_id)
            REFERENCES routes(id, tenant_id)
            ON DELETE CASCADE;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_route_stops_order_tenant'
    ) THEN
        ALTER TABLE route_stops
            ADD CONSTRAINT fk_route_stops_order_tenant
            FOREIGN KEY (order_id, tenant_id)
            REFERENCES orders(id, tenant_id)
            ON DELETE RESTRICT;
    END IF;
END $$;

-- Unicidad: (route_id, order_id) y (route_id, sequence_number)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_route_stops_route_order'
    ) THEN
        ALTER TABLE route_stops
            ADD CONSTRAINT uq_route_stops_route_order
            UNIQUE (route_id, order_id);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_route_stops_route_sequence'
    ) THEN
        ALTER TABLE route_stops
            ADD CONSTRAINT uq_route_stops_route_sequence
            UNIQUE (route_id, sequence_number);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_route_stops_tenant_route
    ON route_stops (tenant_id, route_id);

CREATE INDEX IF NOT EXISTS idx_route_stops_tenant_order_status
    ON route_stops (tenant_id, order_id, status);

CREATE INDEX IF NOT EXISTS idx_route_stops_status
    ON route_stops (status);

DROP TRIGGER IF EXISTS trg_route_stops_updated_at ON route_stops;
CREATE TRIGGER trg_route_stops_updated_at
BEFORE UPDATE ON route_stops
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- 5. INCIDENT TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    route_id UUID NOT NULL,
    route_stop_id UUID NULL,
    driver_id UUID NOT NULL,
    type incident_type NOT NULL,
    severity incident_severity NOT NULL,
    description TEXT NOT NULL,
    status incident_status NOT NULL DEFAULT 'open',
    reported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ NULL,
    resolved_at TIMESTAMPTZ NULL,
    resolution_note TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_incidents_description_not_empty
        CHECK (btrim(description) <> ''),
    CONSTRAINT ck_incidents_resolution_consistency
        CHECK (
            (status = 'resolved' AND resolution_note IS NOT NULL AND resolved_at IS NOT NULL)
            OR (status != 'resolved' AND resolution_note IS NULL AND resolved_at IS NULL)
        ),
    CONSTRAINT ck_incidents_reviewed_consistency
        CHECK (
            (status IN ('reviewed', 'resolved') AND reviewed_at IS NOT NULL)
            OR (status NOT IN ('reviewed', 'resolved') AND reviewed_at IS NULL)
        )
);

-- FKs composition
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_incidents_route_tenant'
    ) THEN
        ALTER TABLE incidents
            ADD CONSTRAINT fk_incidents_route_tenant
            FOREIGN KEY (route_id, tenant_id)
            REFERENCES routes(id, tenant_id)
            ON DELETE CASCADE;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_incidents_route_stop_tenant'
    ) THEN
        ALTER TABLE incidents
            ADD CONSTRAINT fk_incidents_route_stop_tenant
            FOREIGN KEY (route_stop_id, tenant_id)
            REFERENCES route_stops(id, tenant_id)
            ON DELETE SET NULL;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_incidents_driver_tenant'
    ) THEN
        ALTER TABLE incidents
            ADD CONSTRAINT fk_incidents_driver_tenant
            FOREIGN KEY (driver_id, tenant_id)
            REFERENCES drivers(id, tenant_id)
            ON DELETE RESTRICT;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_incidents_tenant_route
    ON incidents (tenant_id, route_id);

CREATE INDEX IF NOT EXISTS idx_incidents_tenant_status_severity
    ON incidents (tenant_id, status, severity);

CREATE INDEX IF NOT EXISTS idx_incidents_tenant_reported_at
    ON incidents (tenant_id, reported_at DESC);

DROP TRIGGER IF EXISTS trg_incidents_updated_at ON incidents;
CREATE TRIGGER trg_incidents_updated_at
BEFORE UPDATE ON incidents
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- 6. ROUTE_EVENT TABLE (append-only)
-- ============================================================================

CREATE TABLE IF NOT EXISTS route_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    route_id UUID NOT NULL,
    route_stop_id UUID NULL,
    event_type route_event_type NOT NULL,
    actor_type route_event_actor_type NOT NULL,
    actor_id UUID NULL,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT ck_route_events_metadata_is_object
        CHECK (jsonb_typeof(metadata_json) = 'object'),
    CONSTRAINT fk_route_events_route_tenant
        FOREIGN KEY (route_id, tenant_id)
        REFERENCES routes(id, tenant_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_route_events_route_stop_tenant
        FOREIGN KEY (route_stop_id, tenant_id)
        REFERENCES route_stops(id, tenant_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_route_events_tenant_route
    ON route_events (tenant_id, route_id);

CREATE INDEX IF NOT EXISTS idx_route_events_tenant_ts
    ON route_events (tenant_id, ts DESC);

CREATE INDEX IF NOT EXISTS idx_route_events_event_type
    ON route_events (event_type);

-- Append-only protection
CREATE OR REPLACE FUNCTION prevent_route_events_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'route_events is append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_route_events_no_update ON route_events;
CREATE TRIGGER trg_route_events_no_update
BEFORE UPDATE ON route_events
FOR EACH ROW
EXECUTE FUNCTION prevent_route_events_mutation();

DROP TRIGGER IF EXISTS trg_route_events_no_delete ON route_events;
CREATE TRIGGER trg_route_events_no_delete
BEFORE DELETE ON route_events
FOR EACH ROW
EXECUTE FUNCTION prevent_route_events_mutation();

-- ============================================================================
-- 7. ORDER_STATUS EXTENSION: post-planned states
-- ============================================================================
-- Extensión sin cambiar orden_status enum existente.
-- Documentación: routing-poc-states.md
-- Estados nuevos: assigned, dispatched, delivered, failed_delivery
-- Únicamente falla_delivery -> ready_for_planning es el único retroceso permitido.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'order_status') THEN
        -- Si el tipo no existe aún (muy improbable), crearlo
        CREATE TYPE order_status AS ENUM (
            'ingested',
            'late_pending_exception',
            'ready_for_planning',
            'planned',
            'exception_rejected',
            'assigned',
            'dispatched',
            'delivered',
            'failed_delivery'
        );
    ELSE
        -- Si existe, intentar añadir los nuevos valores
        -- Nota: PostgreSQL 12+ permite ALTER TYPE ... ADD VALUE
        BEGIN
            ALTER TYPE order_status ADD VALUE 'assigned';
        EXCEPTION WHEN OTHERS THEN
            NULL; -- Ya existe, continuar
        END;
        BEGIN
            ALTER TYPE order_status ADD VALUE 'dispatched';
        EXCEPTION WHEN OTHERS THEN
            NULL;
        END;
        BEGIN
            ALTER TYPE order_status ADD VALUE 'delivered';
        EXCEPTION WHEN OTHERS THEN
            NULL;
        END;
        BEGIN
            ALTER TYPE order_status ADD VALUE 'failed_delivery';
        EXCEPTION WHEN OTHERS THEN
            NULL;
        END;
    END IF;
END $$;

-- ============================================================================
-- 8. PLAN_STATUS EXTENSION: dispatched state se activa al despachar ruta
-- ============================================================================
-- Documentación: routing-poc-states.md
-- El estado 'dispatched' ahora tiene significado operativo.

-- plan_status enum likely exists already, no modification needed in this migration
-- pero documentamos su uso aquí.

-- ============================================================================
-- 9. ÍNDICES ADICIONALES PARA PERFORMANCE
-- ============================================================================

-- Para consultas de rutas por tenant y estado
CREATE INDEX IF NOT EXISTS idx_routes_tenant_status_created_at
    ON routes (tenant_id, status, created_at DESC);

-- Para consultas de paradas pendientes en ruta
CREATE INDEX IF NOT EXISTS idx_route_stops_tenant_status_sequence
    ON route_stops (tenant_id, status, sequence_number);

-- Para consultas de incidencias sin resolver
CREATE INDEX IF NOT EXISTS idx_incidents_tenant_open_status
    ON incidents (tenant_id, status) WHERE status IN ('open', 'reviewed');

COMMIT;
