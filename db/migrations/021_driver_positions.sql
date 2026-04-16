-- Migration 021: driver_positions
-- Posición GPS del conductor. Se envía periódicamente desde la PWA.
-- Solo la posición más reciente es relevante para el mapa en tiempo real.
-- Retención: job de limpieza recomendado cada 7 días.
-- Bloque A3 (GPS-001)

CREATE TABLE IF NOT EXISTS driver_positions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  driver_id UUID NOT NULL,
  route_id UUID NOT NULL,
  lat NUMERIC(9,6) NOT NULL,
  lng NUMERIC(9,6) NOT NULL,
  accuracy_m NUMERIC(8,2),
  speed_kmh NUMERIC(6,2),
  heading NUMERIC(5,2),
  recorded_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Consulta dominante: última posición de un driver en una ruta activa
CREATE INDEX IF NOT EXISTS idx_driver_positions_driver_recent
  ON driver_positions(driver_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_driver_positions_route
  ON driver_positions(route_id);

CREATE INDEX IF NOT EXISTS idx_driver_positions_tenant
  ON driver_positions(tenant_id);
