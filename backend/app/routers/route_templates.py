"""Router — Route Templates XLSX import (XLSX-TEMPLATES-001).

Endpoint:
    POST /route-templates/import-xlsx

Formato de fichero: una fila por parada, agrupadas por vehicle_plate + day_of_week.
Ejemplo de cabeceras aceptadas:
    Matrícula | Día | Orden | Cliente | Dirección | Duración

Reglas de matching:
- Vehículo: exact match en Vehicle.code (case-insensitive) → vehicle_id nullable + warning
- Cliente:  exact CI → partial único → customer_id null + warning
            sin creación automática (a diferencia del import de pedidos)
- Anti-duplicado por grupo:
    si vehicle_id resuelto: tenant+vehicle_id+day_of_week+season → skip + warning
    si vehicle_id null:     tenant+template_name+day_of_week+season → skip + warning
"""

import uuid
from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentUser, require_roles
from app.errors import unprocessable
from app.models import (
    Customer,
    RouteTemplate,
    RouteTemplateStop,
    Tenant,
    Vehicle,
)
from app.schemas import RouteTemplateImportResult
from app.utils.xlsx_parser import (
    TEMPLATE_FIELD_ALIASES,
    auto_map_columns,
    parse_file,
    parse_day_of_week,
    parse_float,
    parse_int,
)

router = APIRouter(tags=["Route Templates"])


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------

def _resolve_vehicle(
    db: Session,
    tenant_id: uuid.UUID,
    plate_raw: str | None,
) -> tuple[uuid.UUID | None, str | None]:
    """Resuelve placa → vehicle_id.

    Returns (vehicle_id, warning_reason).
    """
    if not plate_raw or not plate_raw.strip():
        return None, "matrícula vacía — vehicle_id no resuelto"

    plate = plate_raw.strip()
    vehicle = db.scalar(
        select(Vehicle).where(
            Vehicle.tenant_id == tenant_id,
            func.lower(Vehicle.code) == plate.lower(),
        )
    )
    if vehicle:
        return vehicle.id, None
    return None, f"matrícula '{plate}' no encontrada — vehicle_id no resuelto"


def _resolve_customer_nullable(
    db: Session,
    tenant_id: uuid.UUID,
    customer_name: str | None,
) -> tuple[uuid.UUID | None, str | None]:
    """Resuelve cliente por nombre → customer_id (nullable).

    Regla: exact CI → partial único → null.
    Sin creación automática.

    Returns (customer_id, warning_reason).
    """
    if not customer_name or not customer_name.strip():
        return None, None  # sin nombre → null silencioso

    name = customer_name.strip()

    # 1. Exact match (case-insensitive)
    exact = db.scalars(
        select(Customer).where(
            Customer.tenant_id == tenant_id,
            func.lower(Customer.name) == name.lower(),
        )
    ).all()

    if len(exact) == 1:
        return exact[0].id, None
    if len(exact) > 1:
        return None, f"cliente '{name}' ambiguo: {len(exact)} coincidencias exactas"

    # 2. Partial match — solo si único
    partial = db.scalars(
        select(Customer).where(
            Customer.tenant_id == tenant_id,
            Customer.name.ilike(f"%{name}%"),
        )
    ).all()

    if len(partial) == 1:
        return partial[0].id, f"cliente '{name}' resuelto por coincidencia parcial → '{partial[0].name}'"
    if len(partial) > 1:
        return None, f"cliente '{name}' ambiguo: {len(partial)} coincidencias parciales"

    return None, f"cliente '{name}' no encontrado en el tenant"


def _template_exists(
    db: Session,
    tenant_id: uuid.UUID,
    vehicle_id: uuid.UUID | None,
    template_name: str,
    day_of_week: int | None,
    season: str | None,
) -> bool:
    """Comprueba si ya existe una plantilla equivalente (anti-duplicado)."""
    if vehicle_id is not None:
        q = select(RouteTemplate).where(
            RouteTemplate.tenant_id == tenant_id,
            RouteTemplate.vehicle_id == vehicle_id,
            RouteTemplate.day_of_week == day_of_week,
            RouteTemplate.season == season,
        )
    else:
        q = select(RouteTemplate).where(
            RouteTemplate.tenant_id == tenant_id,
            RouteTemplate.name == template_name,
            RouteTemplate.day_of_week == day_of_week,
            RouteTemplate.season == season,
        )
    return db.scalar(q) is not None


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/route-templates/import-xlsx",
    response_model=RouteTemplateImportResult,
    summary="Importar plantillas de ruta desde XLSX/CSV",
)
def import_route_templates(
    file: UploadFile = File(...),
    season: str | None = Form(None),
    current: CurrentUser = Depends(require_roles("office", "logistics", "admin")),
    db: Session = Depends(get_db),
) -> RouteTemplateImportResult:
    """Importa plantillas de ruta desde un fichero .xlsx o .csv.

    Una fila por parada. Agrupadas por vehicle_plate + day_of_week.
    Idempotente: grupos con plantilla ya existente se saltan con warning.
    """
    now = datetime.now(UTC)
    tenant_id = current.tenant_id

    # ── Validar extensión y parsear ──────────────────────────────────────────
    filename = file.filename or ""
    if not filename.lower().endswith((".xlsx", ".csv")):
        raise unprocessable(
            code="INVALID_FILE_EXTENSION",
            message=f"Extensión no permitida: '{filename}'. Usa .xlsx o .csv",
        )

    file_bytes = file.file.read()
    try:
        raw_rows = list(parse_file(file_bytes, filename))
    except ValueError as exc:
        raise unprocessable(code="INVALID_FILE", message=str(exc)) from exc

    if not raw_rows:
        return RouteTemplateImportResult(
            templates_created=0, stops_total=0, warnings=["El fichero no tiene filas de datos"]
        )

    # ── Mapear columnas ──────────────────────────────────────────────────────
    headers = list(raw_rows[0].keys())
    col_map = auto_map_columns(headers, TEMPLATE_FIELD_ALIASES)
    # col_map: {campo_canonico → cabecera_original}

    def _get(row: dict, field: str) -> str | None:
        col = col_map.get(field)
        return row.get(col) if col else None

    # ── Agrupar filas por (plate, day_of_week) ───────────────────────────────
    # Preservamos orden de aparición con list de tuplas
    groups: dict[tuple[str, int | None], list[dict]] = defaultdict(list)
    ungroupable_warnings: list[str] = []

    for row_idx, row in enumerate(raw_rows, start=2):  # fila 1 = cabecera
        plate_raw = _get(row, "vehicle_plate")
        day_raw = _get(row, "day_of_week")
        dow = parse_day_of_week(day_raw)

        plate_key = (plate_raw or "").strip()
        groups[(plate_key, dow)].append({"_row": row_idx, **row})

    # ── Procesar cada grupo ──────────────────────────────────────────────────
    templates_created = 0
    stops_total = 0
    errors: list[str] = []
    warnings: list[str] = []

    # Necesitamos un tenant válido para metadatos
    tenant = db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if tenant is None:
        raise unprocessable(code="TENANT_NOT_FOUND", message="Tenant no encontrado")

    for (plate_key, dow), rows in groups.items():
        first_row_num = rows[0]["_row"]

        # -- Resolver vehículo
        vehicle_id, vehicle_warn = _resolve_vehicle(db, tenant_id, plate_key or None)
        if vehicle_warn:
            warnings.append(f"Grupo '{plate_key}' día {dow}: {vehicle_warn}")

        # -- Nombre de plantilla
        template_name_raw = _get(rows[0], "template_name")
        if template_name_raw and template_name_raw.strip():
            template_name = template_name_raw.strip()
        else:
            day_label = str(dow) if dow else "sin-dia"
            template_name = f"{plate_key or 'SIN-MATRICULA'}-{day_label}"

        # -- Anti-duplicado
        if _template_exists(db, tenant_id, vehicle_id, template_name, dow, season):
            dup_key = f"vehicle_id={vehicle_id}" if vehicle_id else f"name='{template_name}'"
            warnings.append(
                f"Grupo '{plate_key}' día {dow}: plantilla ya existe "
                f"({dup_key}, day_of_week={dow}, season={season!r}) — saltado"
            )
            continue

        # -- Crear RouteTemplate
        template = RouteTemplate(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            name=template_name,
            season=season,
            vehicle_id=vehicle_id,
            day_of_week=dow,
            shift_start=None,
            shift_end=None,
            created_at=now,
        )
        db.add(template)
        db.flush()

        # -- Crear paradas del grupo
        stops_added = 0
        for seq_idx, row in enumerate(rows, start=1):
            row_num = row["_row"]
            customer_name_raw = _get(row, "customer_name")
            customer_id, cust_warn = _resolve_customer_nullable(db, tenant_id, customer_name_raw)
            if cust_warn:
                warnings.append(f"Fila {row_num}: {cust_warn}")

            seq_raw = _get(row, "sequence")
            sequence_number = parse_int(seq_raw) if seq_raw else seq_idx

            lat = parse_float(_get(row, "lat"))
            lng = parse_float(_get(row, "lng"))
            duration_raw = _get(row, "duration_min")
            duration_min = parse_int(duration_raw) if duration_raw else 10
            notes = _get(row, "notes")

            stop = RouteTemplateStop(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                template_id=template.id,
                sequence_number=sequence_number or seq_idx,
                customer_id=customer_id,
                lat=lat,
                lng=lng,
                address=_get(row, "address"),
                duration_min=duration_min if duration_min is not None else 10,
                notes=notes,
                created_at=now,
            )
            db.add(stop)
            stops_added += 1

        db.flush()
        templates_created += 1
        stops_total += stops_added

    db.commit()

    return RouteTemplateImportResult(
        templates_created=templates_created,
        stops_total=stops_total,
        errors=errors,
        warnings=warnings,
    )
