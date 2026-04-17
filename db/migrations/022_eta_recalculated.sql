-- Migration 022: ETA recalculada en route_stops + tipo delay_alert en RouteEventType
-- Bloque B2 — ETA-001

-- 1. Añadir recalculated_eta_at a route_stops
DO $$ BEGIN
  ALTER TABLE route_stops ADD COLUMN recalculated_eta_at TIMESTAMPTZ;
EXCEPTION WHEN duplicate_column THEN NULL; END $$;

-- 2. Añadir delay_alert al enum route_event_type
-- ADD VALUE IF NOT EXISTS no puede estar dentro de un bloque DO en PostgreSQL < 12;
-- y con psycopg3 autocommit el EXCEPTION WHEN others puede silenciar el error.
-- Se ejecuta directamente fuera de DO block (PostgreSQL 9.5+ soporta IF NOT EXISTS).
ALTER TYPE route_event_type ADD VALUE IF NOT EXISTS 'delay_alert';
