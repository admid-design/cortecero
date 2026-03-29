DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_enum
        WHERE enumtypid = 'entity_type'::regtype
          AND enumlabel = 'tenant'
    ) THEN
        ALTER TYPE entity_type ADD VALUE 'tenant';
    END IF;
END $$;
