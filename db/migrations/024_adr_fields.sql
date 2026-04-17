-- Migration 024: campos ADR (mercancías peligrosas)
-- F5 — ADR-001: vehicles.is_adr_certified y orders.requires_adr
-- Filas existentes: is_adr_certified=false, requires_adr=false (valores seguros por defecto).

DO $$ BEGIN
    ALTER TABLE vehicles ADD COLUMN is_adr_certified BOOLEAN NOT NULL DEFAULT false;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE orders ADD COLUMN requires_adr BOOLEAN NOT NULL DEFAULT false;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_vehicles_adr
    ON vehicles (tenant_id, is_adr_certified)
    WHERE is_adr_certified = true;

CREATE INDEX IF NOT EXISTS idx_orders_adr
    ON orders (tenant_id, requires_adr)
    WHERE requires_adr = true;
