# R6-QA-001 Temporal & DST Deterministic Matrix

Objetivo: fijar resultados deterministas para evaluación operativa en bordes temporales, sin alterar semántica de R1-R5.

## Scope cubierto
- `same_day` window
- `cross_midnight` window
- DST forward
- DST backward
- timezone inválida (fallback explícito)

## Casos y expectativa contractual

1. `same_day` (`08:00` - `10:00`, timezone `UTC`)
- `08:00` => `eligible` (`operational_reason = null`)
- `10:00` => `eligible` (`operational_reason = null`)
- `10:00:01` => `restricted` (`OUTSIDE_CUSTOMER_WINDOW`)

2. `cross_midnight` (`22:00` - `02:00`, timezone `UTC`)
- `22:00` => `eligible`
- `02:00` => `eligible`
- `14:00` => `restricted` (`OUTSIDE_CUSTOMER_WINDOW`)

3. DST forward (`Europe/Madrid`, 2027-03-28, window `01:00` - `03:00`)
- `00:30Z` (`01:30` local) => `eligible`
- `01:30Z` (`03:30` local) => `restricted` (`OUTSIDE_CUSTOMER_WINDOW`)

4. DST backward (`Europe/Madrid`, 2027-10-31, window `02:00` - `02:45`)
- `00:30Z` (`02:30` local, primera ocurrencia) => `eligible`
- `01:30Z` (`02:30` local, segunda ocurrencia) => `eligible`
- `01:50Z` (`02:50` local) => `restricted` (`OUTSIDE_CUSTOMER_WINDOW`)

5. Timezone inválida
- `zone.timezone` inválida + `tenant.default_timezone` inválida
- Evaluación mantiene resultado funcional (`reason`) y expone:
  - `timezone_used = UTC`
  - `timezone_source = utc_fallback`

## Implementación de pruebas
- `backend/tests/test_operational_temporal_dst.py`
