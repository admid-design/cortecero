import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentUser, require_roles
from app.errors import conflict, not_found, unprocessable
from app.models import Customer, UserRole, Zone
from app.schemas import ZoneCreateRequest, ZoneOut, ZoneUpdateRequest, ZonesListResponse


router = APIRouter(prefix="/admin/zones", tags=["Admin Zones"])


def _ensure_valid_iana_timezone(value: str) -> None:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise unprocessable("INVALID_TIMEZONE", "timezone no es una IANA timezone válida") from exc


@router.get("", response_model=ZonesListResponse)
def list_zones(
    active: bool | None = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.office, UserRole.logistics, UserRole.admin)),
) -> ZonesListResponse:
    query = select(Zone).where(Zone.tenant_id == current.tenant_id)
    if active is not None:
        query = query.where(Zone.active == active)

    rows = list(db.scalars(query.order_by(Zone.name.asc())))
    return ZonesListResponse(items=[ZoneOut.model_validate(row) for row in rows], total=len(rows))


@router.post("", response_model=ZoneOut, status_code=201)
def create_zone(
    payload: ZoneCreateRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.admin)),
) -> ZoneOut:
    _ensure_valid_iana_timezone(payload.timezone)

    existing = db.scalar(
        select(Zone).where(
            Zone.tenant_id == current.tenant_id,
            Zone.name == payload.name,
        )
    )
    if existing:
        raise conflict("RESOURCE_CONFLICT", "Ya existe una zona con ese nombre")

    row = Zone(
        tenant_id=current.tenant_id,
        name=payload.name,
        default_cutoff_time=payload.default_cutoff_time,
        timezone=payload.timezone,
        active=True,
        created_at=datetime.now(UTC),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("RESOURCE_CONFLICT", "No se pudo crear la zona") from exc

    db.refresh(row)
    return ZoneOut.model_validate(row)


@router.patch("/{zone_id}", response_model=ZoneOut)
def update_zone(
    zone_id: uuid.UUID,
    payload: ZoneUpdateRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.admin)),
) -> ZoneOut:
    row = db.scalar(select(Zone).where(Zone.id == zone_id, Zone.tenant_id == current.tenant_id))
    if not row:
        raise not_found("ENTITY_NOT_FOUND", "Zona no encontrada")

    if payload.name is None and payload.default_cutoff_time is None and payload.timezone is None:
        raise unprocessable("INVALID_STATE_TRANSITION", "No hay cambios para aplicar")

    if payload.name is not None and payload.name != row.name:
        existing = db.scalar(
            select(Zone).where(
                Zone.tenant_id == current.tenant_id,
                Zone.name == payload.name,
                Zone.id != row.id,
            )
        )
        if existing:
            raise conflict("RESOURCE_CONFLICT", "Ya existe una zona con ese nombre")
        row.name = payload.name

    if payload.default_cutoff_time is not None:
        row.default_cutoff_time = payload.default_cutoff_time

    if payload.timezone is not None:
        _ensure_valid_iana_timezone(payload.timezone)
        row.timezone = payload.timezone

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("RESOURCE_CONFLICT", "No se pudo actualizar la zona") from exc

    db.refresh(row)
    return ZoneOut.model_validate(row)


@router.post("/{zone_id}/deactivate", response_model=ZoneOut)
def deactivate_zone(
    zone_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.admin)),
) -> ZoneOut:
    row = db.scalar(select(Zone).where(Zone.id == zone_id, Zone.tenant_id == current.tenant_id))
    if not row:
        raise not_found("ENTITY_NOT_FOUND", "Zona no encontrada")

    if not row.active:
        raise unprocessable("INVALID_STATE_TRANSITION", "La zona ya está desactivada")

    has_active_customers = db.scalar(
        select(Customer.id).where(
            Customer.tenant_id == current.tenant_id,
            Customer.zone_id == row.id,
            Customer.active.is_(True),
        )
    )
    if has_active_customers:
        raise unprocessable("INVALID_STATE_TRANSITION", "No se puede desactivar una zona con clientes activos")

    row.active = False
    db.commit()
    db.refresh(row)
    return ZoneOut.model_validate(row)
