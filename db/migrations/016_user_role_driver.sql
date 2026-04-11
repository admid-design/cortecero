-- D.2 — habilitar rol driver para autenticación/ejecución conductor

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
        ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'driver';
    END IF;
END
$$;
