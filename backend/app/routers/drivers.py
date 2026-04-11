import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentUser, require_roles
from app.errors import conflict, not_found, unprocessable
from app.models import Driver, UserRole, Vehicle
from app.schemas import DriverCreateRequest, DriverOut, DriverUpdateRequest, DriversListResponse

router = APIRouter(prefix="/drivers", tags=["Drivers"])


def _serialize_driver(driver: Driver) -> DriverOut:
    return DriverOut.model_validate(driver)


@router.get("", response_model=DriversListResponse)
def list_drivers(
    active: bool | None = None,
    vehicle_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.office, UserRole.logistics, UserRole.admin)),
) -> DriversListResponse:
    query = select(Driver).where(Driver.tenant_id == current.tenant_id)
    if active is not None:
        query = query.where(Driver.is_active == active)
    if vehicle_id is not None:
        query = query.where(Driver.vehicle_id == vehicle_id)
    rows = list(db.scalars(query.order_by(Driver.name)))
    return DriversListResponse(items=[_serialize_driver(r) for r in rows], total=len(rows))


@router.get("/{driver_id}", response_model=DriverOut)
def get_driver(
    driver_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.office, UserRole.logistics, UserRole.admin)),
) -> DriverOut:
    row = db.scalar(select(Driver).where(Driver.id == driver_id, Driver.tenant_id == current.tenant_id))
    if not row:
        raise not_found("ENTITY_NOT_FOUND", "Chofer no encontrado")
    return _serialize_driver(row)


@router.post("", response_model=DriverOut, status_code=201)
def create_driver(
    payload: DriverCreateRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.logistics, UserRole.admin)),
) -> DriverOut:
    name = payload.name.strip()
    phone = payload.phone.strip()

    if not name:
        raise unprocessable("INVALID_DRIVER", "name no puede estar vacío")
    if not phone:
        raise unprocessable("INVALID_DRIVER", "phone no puede estar vacío")

    # Verificar que el vehículo pertenece al tenant si se proporciona
    if payload.vehicle_id is not None:
        vehicle = db.scalar(
            select(Vehicle).where(
                Vehicle.id == payload.vehicle_id,
                Vehicle.tenant_id == current.tenant_id,
                Vehicle.active.is_(True),
            )
        )
        if not vehicle:
            raise not_found("ENTITY_NOT_FOUND", "Vehículo no encontrado o inactivo")

    # Verificar unicidad de teléfono por tenant
    existing = db.scalar(
        select(Driver).where(Driver.tenant_id == current.tenant_id, Driver.phone == phone)
    )
    if existing:
        raise conflict("RESOURCE_CONFLICT", "Ya existe un chofer con ese teléfono")

    now = datetime.now(UTC)
    row = Driver(
        id=uuid.uuid4(),
        tenant_id=current.tenant_id,
        vehicle_id=payload.vehicle_id,
        name=name,
        phone=phone,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("RESOURCE_CONFLICT", "No se pudo crear el chofer") from exc

    db.refresh(row)
    return _serialize_driver(row)


@router.patch("/{driver_id}", response_model=DriverOut)
def update_driver(
    driver_id: uuid.UUID,
    payload: DriverUpdateRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.logistics, UserRole.admin)),
) -> DriverOut:
    row = db.scalar(select(Driver).where(Driver.id == driver_id, Driver.tenant_id == current.tenant_id))
    if not row:
        raise not_found("ENTITY_NOT_FOUND", "Chofer no encontrado")

    if not payload.model_fields_set:
        raise unprocessable("INVALID_STATE_TRANSITION", "No hay cambios para aplicar")

    if "name" in payload.model_fields_set and payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise unprocessable("INVALID_DRIVER", "name no puede estar vacío")
        row.name = name

    if "phone" in payload.model_fields_set and payload.phone is not None:
        phone = payload.phone.strip()
        if not phone:
            raise unprocessable("INVALID_DRIVER", "phone no puede estar vacío")
        if phone != row.phone:
            existing = db.scalar(
                select(Driver).where(
                    Driver.tenant_id == current.tenant_id,
                    Driver.phone == phone,
                    Driver.id != driver_id,
                )
            )
            if existing:
                raise conflict("RESOURCE_CONFLICT", "Ya existe un chofer con ese teléfono")
        row.phone = phone

    if "vehicle_id" in payload.model_fields_set:
        if payload.vehicle_id is not None:
            vehicle = db.scalar(
                select(Vehicle).where(
                    Vehicle.id == payload.vehicle_id,
                    Vehicle.tenant_id == current.tenant_id,
                    Vehicle.active.is_(True),
                )
            )
            if not vehicle:
                raise not_found("ENTITY_NOT_FOUND", "Vehículo no encontrado o inactivo")
        row.vehicle_id = payload.vehicle_id

    if "is_active" in payload.model_fields_set and payload.is_active is not None:
        row.is_active = payload.is_active

    row.updated_at = datetime.now(UTC)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("RESOURCE_CONFLICT", "No se pudo actualizar el chofer") from exc

    db.refresh(row)
    return _serialize_driver(row)
