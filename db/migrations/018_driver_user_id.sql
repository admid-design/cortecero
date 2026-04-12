-- 018_driver_user_id.sql
-- PILOT-HARDEN-001: Vínculo explícito Driver → User
--
-- Problema previo: la relación Driver ↔ User se resolvía por convención de UUID
-- compartido (drivers.id == users.id). Sin FK, sin trazabilidad, sin enforcement.
-- El seed y POST /drivers crean Driver con UUID propio sin User ligado.
--
-- Corrección mínima backward-compatible:
--   * Añade columna user_id UUID NULL en drivers.
--   * FK → users(id) con ON DELETE SET NULL: si se borra el User, el Driver
--     queda desvinculado (no se borra el historial operativo).
--   * DEFERRABLE INITIALLY DEFERRED: permite crear User y Driver en la misma
--     transacción en cualquier orden.
--   * Unique: un User no puede estar vinculado a más de un Driver activo.
--   * Drivers existentes (seed, demo) quedan con user_id = NULL: válido.
--     Solo necesitan user_id cuando el conductor necesita autenticarse en PWA.
--
-- Impacto en auth (routing.py/_resolve_current_driver):
--   SELECT ... WHERE drivers.user_id = current_user.id  (antes: drivers.id)
--
-- Rollback seguro: DROP CONSTRAINT + DROP COLUMN — sin pérdida de datos.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'drivers' AND column_name = 'user_id'
    ) THEN
        ALTER TABLE drivers
            ADD COLUMN user_id UUID NULL;

        ALTER TABLE drivers
            ADD CONSTRAINT uq_drivers_user_id
            UNIQUE (user_id);

        ALTER TABLE drivers
            ADD CONSTRAINT fk_drivers_user_id
            FOREIGN KEY (user_id)
            REFERENCES users(id)
            ON DELETE SET NULL
            DEFERRABLE INITIALLY DEFERRED;

        CREATE INDEX IF NOT EXISTS idx_drivers_user_id
            ON drivers (user_id);
    END IF;
END $$;
