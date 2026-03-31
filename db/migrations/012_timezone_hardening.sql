BEGIN;

CREATE OR REPLACE FUNCTION is_valid_iana_timezone(value TEXT)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM pg_timezone_names
        WHERE name = value
    );
$$;

-- Normalize existing records before enforcing constraints.
UPDATE tenants
SET default_timezone = 'UTC'
WHERE default_timezone IS NULL
   OR NOT is_valid_iana_timezone(default_timezone);

UPDATE zones AS z
SET timezone = COALESCE(t.default_timezone, 'UTC')
FROM tenants AS t
WHERE z.tenant_id = t.id
  AND (
      z.timezone IS NULL
      OR NOT is_valid_iana_timezone(z.timezone)
  );

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_tenants_default_timezone_iana'
    ) THEN
        ALTER TABLE tenants
        ADD CONSTRAINT ck_tenants_default_timezone_iana
        CHECK (is_valid_iana_timezone(default_timezone));
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_zones_timezone_iana'
    ) THEN
        ALTER TABLE zones
        ADD CONSTRAINT ck_zones_timezone_iana
        CHECK (is_valid_iana_timezone(timezone));
    END IF;
END $$;

COMMIT;
