import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentUser, require_roles
from app.errors import conflict, not_found, unprocessable
from app.models import Customer, UserRole, Zone
from app.schemas import CustomerCreateRequest, CustomerOut, CustomersListResponse, CustomerUpdateRequest


router = APIRouter(prefix="/admin/customers", tags=["Admin Customers"])


@router.get("", response_model=CustomersListResponse)
def list_customers(
    active: bool | None = None,
    zone_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.office, UserRole.logistics, UserRole.admin)),
) -> CustomersListResponse:
    query = select(Customer).where(Customer.tenant_id == current.tenant_id)
    if active is not None:
        query = query.where(Customer.active == active)
    if zone_id is not None:
        query = query.where(Customer.zone_id == zone_id)

    rows = list(db.scalars(query.order_by(Customer.name.asc())))
    return CustomersListResponse(items=[CustomerOut.model_validate(row) for row in rows], total=len(rows))


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(
    payload: CustomerCreateRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.admin)),
) -> CustomerOut:
    zone = db.scalar(select(Zone).where(Zone.id == payload.zone_id, Zone.tenant_id == current.tenant_id))
    if not zone:
        raise not_found("ENTITY_NOT_FOUND", "Zona no encontrada")

    existing = db.scalar(
        select(Customer).where(
            Customer.tenant_id == current.tenant_id,
            Customer.name == payload.name,
        )
    )
    if existing:
        raise conflict("RESOURCE_CONFLICT", "Ya existe un cliente con ese nombre")

    row = Customer(
        tenant_id=current.tenant_id,
        zone_id=payload.zone_id,
        name=payload.name,
        priority=payload.priority,
        cutoff_override_time=payload.cutoff_override_time,
        active=True,
        created_at=datetime.now(UTC),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("RESOURCE_CONFLICT", "No se pudo crear el cliente") from exc

    db.refresh(row)
    return CustomerOut.model_validate(row)


@router.patch("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: uuid.UUID,
    payload: CustomerUpdateRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.admin)),
) -> CustomerOut:
    row = db.scalar(select(Customer).where(Customer.id == customer_id, Customer.tenant_id == current.tenant_id))
    if not row:
        raise not_found("ENTITY_NOT_FOUND", "Cliente no encontrado")

    if not payload.model_fields_set:
        raise unprocessable("INVALID_STATE_TRANSITION", "No hay cambios para aplicar")

    if "zone_id" in payload.model_fields_set and payload.zone_id is not None and payload.zone_id != row.zone_id:
        zone = db.scalar(select(Zone).where(Zone.id == payload.zone_id, Zone.tenant_id == current.tenant_id))
        if not zone:
            raise not_found("ENTITY_NOT_FOUND", "Zona no encontrada")
        row.zone_id = payload.zone_id

    if "name" in payload.model_fields_set and payload.name is not None and payload.name != row.name:
        existing = db.scalar(
            select(Customer).where(
                Customer.tenant_id == current.tenant_id,
                Customer.name == payload.name,
                Customer.id != row.id,
            )
        )
        if existing:
            raise conflict("RESOURCE_CONFLICT", "Ya existe un cliente con ese nombre")
        row.name = payload.name

    if "priority" in payload.model_fields_set and payload.priority is not None:
        row.priority = payload.priority

    if "cutoff_override_time" in payload.model_fields_set:
        row.cutoff_override_time = payload.cutoff_override_time

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("RESOURCE_CONFLICT", "No se pudo actualizar el cliente") from exc

    db.refresh(row)
    return CustomerOut.model_validate(row)


@router.post("/{customer_id}/deactivate", response_model=CustomerOut)
def deactivate_customer(
    customer_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.admin)),
) -> CustomerOut:
    row = db.scalar(select(Customer).where(Customer.id == customer_id, Customer.tenant_id == current.tenant_id))
    if not row:
        raise not_found("ENTITY_NOT_FOUND", "Cliente no encontrado")

    if not row.active:
        raise unprocessable("INVALID_STATE_TRANSITION", "El cliente ya está desactivado")

    row.active = False
    db.commit()
    db.refresh(row)
    return CustomerOut.model_validate(row)
