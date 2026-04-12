# Reglas — Base de datos

Aplica cuando trabajas en `db/` o cuando cambias modelos en `backend/app/models.py`.

## Stack

- PostgreSQL 16
- Migraciones SQL en `db/migrations/`
- Runner: `backend/scripts/apply_migration.py` — aplica por orden lexicográfico, idempotente
- Se ejecuta en `backend/scripts/start.sh` al arrancar el backend

## Nomenclatura de migraciones

```
NNN_descripcion_corta.sql
```

- `NNN` es número de 3 dígitos, siguiente al último existente
- Descripción en snake_case, sin abreviaturas crípticas
- Ejemplo: `020_route_geo_index.sql`

## Reglas de idempotencia

Toda migración debe poder correr múltiples veces sin error.

Patrones obligatorios:
```sql
CREATE TABLE IF NOT EXISTS ...
CREATE INDEX IF NOT EXISTS ...

-- Para añadir columna:
DO $$ BEGIN
  ALTER TABLE t ADD COLUMN col type;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- Para añadir constraint:
DO $$ BEGIN
  ALTER TABLE t ADD CONSTRAINT name ...;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
```

## Reglas de modificación

- **No borres ni modifiques migrations anteriores** — son historia inmutable
- Si una migración anterior tiene un error que necesitas corregir, crea una nueva migración que lo corrija
- No renombres tablas/columnas sin bloque explícito que actualice también `models.py`

## Alineación con models.py

Cuando añades una columna o tabla en SQL, actualiza `backend/app/models.py` en el mismo commit.
No dejes `models.py` desincronizado con el schema de DB.

## Migraciones recientes críticas

| Número | Nombre | Contenido |
|--------|--------|-----------|
| 017 | `user_role_driver` | Rol `driver` en tabla `users` |
| 018 | `driver_user_id` | FK explícita `drivers.user_id → users.id` |
| 019 | `warehouse_locations` | Campos de ubicación de almacén |

## Nunca

- No metas datos reales de cliente en migraciones ni seeds
- No hagas migraciones destructivas (DROP TABLE, DROP COLUMN) sin gate explícito del usuario
- No dejes constraints sin nombre — ponles nombres descriptivos
