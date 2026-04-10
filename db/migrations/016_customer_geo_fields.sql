-- 016_customer_geo_fields.sql
-- Bloque G: Añade coordenadas GPS y dirección de entrega a customers.
-- Prerequisito para Bloque E (Google Route Optimization API).
-- Backward-compatible: todas las columnas son nullable.

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'customers' AND column_name = 'lat'
  ) THEN
    ALTER TABLE customers
      ADD COLUMN lat              NUMERIC(9,6) NULL,
      ADD COLUMN lng              NUMERIC(9,6) NULL,
      ADD COLUMN delivery_address TEXT         NULL;

    COMMENT ON COLUMN customers.lat IS 'Latitud WGS-84 del punto de entrega';
    COMMENT ON COLUMN customers.lng IS 'Longitud WGS-84 del punto de entrega';
    COMMENT ON COLUMN customers.delivery_address IS 'Dirección legible para geocodificación';
  END IF;
END $$;
