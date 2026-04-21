-- Migration 029: route_stops.order_id + routes.plan_id nullable
-- Necesario para ROUTE-FROM-TEMPLATE-001: rutas creadas desde plantilla
-- no tienen pedidos asociados a sus paradas, ni plan diario.
--
-- Idempotente: todos los bloques son seguros ante ejecuciones repetidas.

-- 1. Hacer order_id nullable en route_stops
DO $$ BEGIN
  ALTER TABLE route_stops ALTER COLUMN order_id DROP NOT NULL;
EXCEPTION WHEN others THEN NULL;
END $$;

-- 2. Eliminar el unique constraint original (route_id, order_id)
--    No es seguro con NULLs: múltiples NULLs violarían la constraint en algunos motores.
DO $$ BEGIN
  ALTER TABLE route_stops DROP CONSTRAINT uq_route_stops_route_order;
EXCEPTION WHEN undefined_object THEN NULL;
END $$;

-- 3. Crear índice único parcial: unicidad solo cuando order_id IS NOT NULL.
--    Permite múltiples paradas sin pedido en la misma ruta.
CREATE UNIQUE INDEX IF NOT EXISTS uq_route_stops_route_order_nonnull
    ON route_stops (route_id, order_id)
    WHERE order_id IS NOT NULL;

-- 4. Hacer plan_id nullable en routes
--    Rutas creadas desde plantilla no pertenecen a ningún plan diario.
DO $$ BEGIN
  ALTER TABLE routes ALTER COLUMN plan_id DROP NOT NULL;
EXCEPTION WHEN others THEN NULL;
END $$;
