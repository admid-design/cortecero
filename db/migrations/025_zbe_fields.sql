-- Migration 025: campos ZBE (zona de bajas emisiones)
-- F6 — ZBE-001: customers.in_zbe_zone y vehicles.is_zbe_allowed
-- Filas existentes: in_zbe_zone=false, is_zbe_allowed=false (valores seguros por defecto).

DO $$ BEGIN
    ALTER TABLE customers ADD COLUMN in_zbe_zone BOOLEAN NOT NULL DEFAULT false;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE vehicles ADD COLUMN is_zbe_allowed BOOLEAN NOT NULL DEFAULT false;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_customers_zbe
    ON customers (tenant_id, in_zbe_zone)
    WHERE in_zbe_zone = true;

CREATE INDEX IF NOT EXISTS idx_vehicles_zbe
    ON vehicles (tenant_id, is_zbe_allowed)
    WHERE is_zbe_allowed = true;
