# Reglas — OpenAPI

Aplica cuando trabajas en `openapi/openapi-v1.yaml` o cuando cambias endpoints del backend.

## Principio

`openapi/openapi-v1.yaml` es el **contrato público vivo** del API.
Debe ser fiel al comportamiento real del backend — no aspiracional, no aproximado.

## Regla de tres-vías

Cuando un path o schema cambia, los tres deben actualizarse **en el mismo commit**:

1. `backend/app/routers/<router>.py` — implementación
2. `openapi/openapi-v1.yaml` — contrato
3. `frontend/lib/api.ts` — cliente tipado

Si los tres no están alineados, el contrato está roto.
Lección: `BUG-ROUTING-READY-DISPATCH-001` — runtime, spec y frontend apuntaban a paths distintos.

## CI de validación

El workflow `openapi-check` en `.github/workflows/openapi-check.yml` valida el YAML en cada push.
Si rompes el YAML, CI falla. Valida con `openapi-spec-validator` antes de commitear.

## Estructura del archivo

- Versión actual: `1.0.0` (ver info en el YAML)
- Paths organizados por dominio operativo
- `components/schemas` para tipos reutilizables

## Reglas de edición

- Mantén sangría y estilo consistente con el archivo existente (2 espacios)
- Añade paths nuevos en la sección correspondiente al dominio
- Documenta siempre los códigos de error posibles en `responses`
- Usa `$ref` para schemas repetidos — no dupliques inline

## Validación local

```bash
# Con venv activado
source .venv/bin/activate
openapi-spec-validator openapi/openapi-v1.yaml
```

## Invariante

El YAML no debe describir endpoints que no existan en el backend.
El backend no debe tener endpoints que no estén en el YAML.
Si hay divergencia, documéntala en `docs/as-is.md` como gap conocido.
