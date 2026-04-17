-- Migration 023: trip_number en routes
-- F4 — DOUBLE-TRIP-001: permite que un vehículo haga dos viajes en el mismo día.
-- trip_number=1 (primer viaje), trip_number=2 (segundo viaje).
-- Filas existentes reciben trip_number=1 por el DEFAULT.

DO $$ BEGIN
    ALTER TABLE routes ADD COLUMN trip_number SMALLINT NOT NULL DEFAULT 1;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE routes
        ADD CONSTRAINT ck_routes_trip_number CHECK (trip_number IN (1, 2));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_routes_vehicle_service_trip
    ON routes (tenant_id, vehicle_id, service_date, trip_number);
