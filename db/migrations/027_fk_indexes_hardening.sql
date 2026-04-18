-- Migration 027: FK constraints + índices de rendimiento
-- HARDENING-DB-001
--
-- Objetivo:
--   1. Añadir FKs referenciales a stop_proofs y route_messages
--      (migration 020 y 026 las omitieron; los campos existían sin constraint).
--   2. Añadir índices para las queries de hot-path más frecuentes.
--
-- Idempotente: todos los bloques usan IF NOT EXISTS o EXCEPTION WHEN duplicate_object.

-- ============================================================================
-- 1. stop_proofs.route_stop_id → route_stops(id) ON DELETE CASCADE
-- ============================================================================
DO $$ BEGIN
    ALTER TABLE stop_proofs
        ADD CONSTRAINT fk_stop_proofs_route_stop
        FOREIGN KEY (route_stop_id) REFERENCES route_stops(id) ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================================
-- 2. stop_proofs.route_id → routes(id) ON DELETE CASCADE
-- ============================================================================
DO $$ BEGIN
    ALTER TABLE stop_proofs
        ADD CONSTRAINT fk_stop_proofs_route
        FOREIGN KEY (route_id) REFERENCES routes(id) ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================================
-- 3. route_messages.route_id → routes(id) ON DELETE CASCADE
-- ============================================================================
DO $$ BEGIN
    ALTER TABLE route_messages
        ADD CONSTRAINT fk_route_messages_route
        FOREIGN KEY (route_id) REFERENCES routes(id) ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================================
-- 4. Índice orders(tenant_id, status) — hot-path: ready-to-dispatch y colas
--    Complementa al índice compuesto existente (tenant_id, service_date, ...)
--    para queries filtradas solo por status (sin service_date).
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_orders_tenant_status
    ON orders (tenant_id, status);

-- ============================================================================
-- 5. Índice route_stops(route_id, status) — hot-path: detalle de ruta con
--    filtro por estado de parada (arrive/complete/skip/fail).
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_route_stops_route_status
    ON route_stops (route_id, status);
