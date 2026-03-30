import uuid
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import write_audit
from app.db import get_db
from app.deps import CurrentUser, require_roles
from app.errors import conflict, not_found, unprocessable
from app.models import (
    Customer,
    CustomerOperationalException,
    CustomerOperationalExceptionType,
    CustomerOperationalProfile,
    EntityType,
    Tenant,
    UserRole,
    Zone,
)
from app.schemas import (
    CustomerCreateRequest,
    CustomerOperationalExceptionCreateRequest,
    CustomerOperationalExceptionOut,
    CustomerOperationalExceptionsListResponse,
    CustomerOperationalProfileOut,
    CustomerOperationalProfilePutRequest,
    CustomerOut,
    CustomersListResponse,
    CustomerUpdateRequest,
)


router = APIRouter(prefix="/admin/customers", tags=["Admin Customers"])


def _get_customer_or_404(db: Session, tenant_id: uuid.UUID, customer_id: uuid.UUID) -> Customer:
    row = db.scalar(select(Customer).where(Customer.id == customer_id, Customer.tenant_id == tenant_id))
    if not row:
        raise not_found("ENTITY_NOT_FOUND", "Cliente no encontrado")
    return row


def _get_tenant_or_404(db: Session, tenant_id: uuid.UUID) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise not_found("ENTITY_NOT_FOUND", "Tenant no encontrado")
    return tenant


def _resolve_operational_timezone(db: Session, tenant_id: uuid.UUID, customer: Customer) -> str:
    zone = db.scalar(select(Zone).where(Zone.id == customer.zone_id, Zone.tenant_id == tenant_id))
    if not zone:
        raise not_found("ENTITY_NOT_FOUND", "Zona no encontrada")
    tenant = _get_tenant_or_404(db, tenant_id)
    timezone = zone.timezone or tenant.default_timezone
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise unprocessable("INVALID_TIMEZONE", "timezone de evaluación no es una IANA timezone válida") from exc
    return timezone


def _window_mode(window_start: time | None, window_end: time | None) -> str:
    if window_start is None and window_end is None:
        return "none"
    if window_start is not None and window_end is not None and window_start > window_end:
        return "cross_midnight"
    return "same_day"


def _validate_operational_profile_payload(payload: CustomerOperationalProfilePutRequest) -> str | None:
    if payload.min_lead_hours < 0:
        raise unprocessable("INVALID_OPERATIONAL_PROFILE", "min_lead_hours debe ser mayor o igual a 0")

    only_one_window_side = (payload.window_start is None) != (payload.window_end is None)
    if only_one_window_side:
        raise unprocessable(
            "INVALID_OPERATIONAL_PROFILE",
            "window_start y window_end deben informarse juntos o ambos null",
        )

    if payload.window_start is not None and payload.window_end is not None and payload.window_start == payload.window_end:
        raise unprocessable(
            "INVALID_OPERATIONAL_PROFILE",
            "window_start y window_end no pueden ser iguales",
        )

    if payload.ops_note is None:
        return None
    normalized_note = payload.ops_note.strip()
    if not normalized_note:
        raise unprocessable("INVALID_OPERATIONAL_PROFILE", "ops_note no puede estar vacía; usa null para limpiarla")
    return normalized_note


def _to_operational_profile_out(
    customer_id: uuid.UUID,
    evaluation_timezone: str,
    *,
    profile: CustomerOperationalProfile | None,
) -> CustomerOperationalProfileOut:
    if profile is None:
        window_start = None
        window_end = None
        min_lead_hours = 0
        accept_orders = True
        consolidate_by_default = False
        ops_note = None
        is_customized = False
    else:
        window_start = profile.window_start
        window_end = profile.window_end
        min_lead_hours = profile.min_lead_hours
        accept_orders = profile.accept_orders
        consolidate_by_default = profile.consolidate_by_default
        ops_note = profile.ops_note
        is_customized = True

    return CustomerOperationalProfileOut(
        customer_id=customer_id,
        accept_orders=accept_orders,
        window_start=window_start,
        window_end=window_end,
        min_lead_hours=min_lead_hours,
        consolidate_by_default=consolidate_by_default,
        ops_note=ops_note,
        evaluation_timezone=evaluation_timezone,
        window_mode=_window_mode(window_start, window_end),
        is_customized=is_customized,
    )


def _normalize_operational_exception_note(note: str) -> str:
    normalized_note = note.strip()
    if not normalized_note:
        raise unprocessable("INVALID_OPERATIONAL_EXCEPTION", "note es obligatoria y no puede estar vacía")
    return normalized_note


def _to_operational_exception_out(row: CustomerOperationalException) -> CustomerOperationalExceptionOut:
    return CustomerOperationalExceptionOut.model_validate(
        {
            "id": row.id,
            "customer_id": row.customer_id,
            "date": row.date,
            "type": row.type.value,
            "note": row.note,
            "created_at": row.created_at,
        }
    )


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


@router.get("/{customer_id}/operational-profile", response_model=CustomerOperationalProfileOut)
def get_customer_operational_profile(
    customer_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.office, UserRole.logistics, UserRole.admin)),
) -> CustomerOperationalProfileOut:
    customer = _get_customer_or_404(db, current.tenant_id, customer_id)
    evaluation_timezone = _resolve_operational_timezone(db, current.tenant_id, customer)
    profile = db.scalar(
        select(CustomerOperationalProfile).where(
            CustomerOperationalProfile.tenant_id == current.tenant_id,
            CustomerOperationalProfile.customer_id == customer.id,
        )
    )
    return _to_operational_profile_out(customer.id, evaluation_timezone, profile=profile)


@router.put("/{customer_id}/operational-profile", response_model=CustomerOperationalProfileOut)
def put_customer_operational_profile(
    customer_id: uuid.UUID,
    payload: CustomerOperationalProfilePutRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.admin)),
) -> CustomerOperationalProfileOut:
    customer = _get_customer_or_404(db, current.tenant_id, customer_id)
    evaluation_timezone = _resolve_operational_timezone(db, current.tenant_id, customer)
    normalized_note = _validate_operational_profile_payload(payload)

    profile = db.scalar(
        select(CustomerOperationalProfile).where(
            CustomerOperationalProfile.tenant_id == current.tenant_id,
            CustomerOperationalProfile.customer_id == customer.id,
        )
    )

    if profile is None:
        profile = CustomerOperationalProfile(
            tenant_id=current.tenant_id,
            customer_id=customer.id,
            accept_orders=payload.accept_orders,
            window_start=payload.window_start,
            window_end=payload.window_end,
            min_lead_hours=payload.min_lead_hours,
            consolidate_by_default=payload.consolidate_by_default,
            ops_note=normalized_note,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(profile)
        changed_fields = [
            "accept_orders",
            "window_start",
            "window_end",
            "min_lead_hours",
            "consolidate_by_default",
            "ops_note",
        ]
        before = None
    else:
        before = {
            "accept_orders": profile.accept_orders,
            "window_start": profile.window_start.isoformat() if profile.window_start else None,
            "window_end": profile.window_end.isoformat() if profile.window_end else None,
            "min_lead_hours": profile.min_lead_hours,
            "consolidate_by_default": profile.consolidate_by_default,
            "ops_note": profile.ops_note,
        }
        changed_fields: list[str] = []
        if profile.accept_orders != payload.accept_orders:
            profile.accept_orders = payload.accept_orders
            changed_fields.append("accept_orders")
        if profile.window_start != payload.window_start:
            profile.window_start = payload.window_start
            changed_fields.append("window_start")
        if profile.window_end != payload.window_end:
            profile.window_end = payload.window_end
            changed_fields.append("window_end")
        if profile.min_lead_hours != payload.min_lead_hours:
            profile.min_lead_hours = payload.min_lead_hours
            changed_fields.append("min_lead_hours")
        if profile.consolidate_by_default != payload.consolidate_by_default:
            profile.consolidate_by_default = payload.consolidate_by_default
            changed_fields.append("consolidate_by_default")
        if profile.ops_note != normalized_note:
            profile.ops_note = normalized_note
            changed_fields.append("ops_note")

    if changed_fields:
        write_audit(
            db,
            tenant_id=current.tenant_id,
            entity_type=EntityType.tenant,
            entity_id=current.tenant_id,
            action="customer.operational_profile_updated",
            actor_id=current.id,
            metadata={
                "customer_id": str(customer.id),
                "changed_fields": changed_fields,
                "before": before,
                "after": {
                    "accept_orders": payload.accept_orders,
                    "window_start": payload.window_start.isoformat() if payload.window_start else None,
                    "window_end": payload.window_end.isoformat() if payload.window_end else None,
                    "min_lead_hours": payload.min_lead_hours,
                    "consolidate_by_default": payload.consolidate_by_default,
                    "ops_note": normalized_note,
                    "evaluation_timezone": evaluation_timezone,
                    "window_mode": _window_mode(payload.window_start, payload.window_end),
                },
            },
        )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("RESOURCE_CONFLICT", "No se pudo actualizar el perfil operativo") from exc

    db.refresh(profile)
    return _to_operational_profile_out(customer.id, evaluation_timezone, profile=profile)


@router.get("/{customer_id}/operational-exceptions", response_model=CustomerOperationalExceptionsListResponse)
def list_customer_operational_exceptions(
    customer_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.office, UserRole.logistics, UserRole.admin)),
) -> CustomerOperationalExceptionsListResponse:
    customer = _get_customer_or_404(db, current.tenant_id, customer_id)
    rows = list(
        db.scalars(
            select(CustomerOperationalException)
            .where(
                CustomerOperationalException.tenant_id == current.tenant_id,
                CustomerOperationalException.customer_id == customer.id,
            )
            .order_by(
                CustomerOperationalException.date.asc(),
                CustomerOperationalException.type.asc(),
                CustomerOperationalException.created_at.asc(),
            )
        )
    )
    return CustomerOperationalExceptionsListResponse(
        items=[_to_operational_exception_out(row) for row in rows],
        total=len(rows),
    )


@router.post("/{customer_id}/operational-exceptions", response_model=CustomerOperationalExceptionOut, status_code=201)
def create_customer_operational_exception(
    customer_id: uuid.UUID,
    payload: CustomerOperationalExceptionCreateRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.admin)),
) -> CustomerOperationalExceptionOut:
    customer = _get_customer_or_404(db, current.tenant_id, customer_id)
    normalized_note = _normalize_operational_exception_note(payload.note)

    existing = db.scalar(
        select(CustomerOperationalException).where(
            CustomerOperationalException.tenant_id == current.tenant_id,
            CustomerOperationalException.customer_id == customer.id,
            CustomerOperationalException.date == payload.date,
            CustomerOperationalException.type == CustomerOperationalExceptionType(payload.type),
        )
    )
    if existing:
        raise conflict("OPERATIONAL_EXCEPTION_CONFLICT", "Ya existe una excepción para esa fecha y tipo")

    row = CustomerOperationalException(
        tenant_id=current.tenant_id,
        customer_id=customer.id,
        date=payload.date,
        type=CustomerOperationalExceptionType(payload.type),
        note=normalized_note,
        created_at=datetime.now(UTC),
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("OPERATIONAL_EXCEPTION_CONFLICT", "Ya existe una excepción para esa fecha y tipo") from exc

    write_audit(
        db,
        tenant_id=current.tenant_id,
        entity_type=EntityType.tenant,
        entity_id=current.tenant_id,
        action="customer.operational_exception_created",
        actor_id=current.id,
        metadata={
            "customer_id": str(customer.id),
            "exception_id": str(row.id),
            "date": str(row.date),
            "type": row.type.value,
            "note": row.note,
        },
    )
    db.commit()
    db.refresh(row)
    return _to_operational_exception_out(row)


@router.delete("/{customer_id}/operational-exceptions/{exception_id}", response_model=CustomerOperationalExceptionOut)
def delete_customer_operational_exception(
    customer_id: uuid.UUID,
    exception_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.admin)),
) -> CustomerOperationalExceptionOut:
    customer = _get_customer_or_404(db, current.tenant_id, customer_id)
    row = db.scalar(
        select(CustomerOperationalException).where(
            CustomerOperationalException.id == exception_id,
            CustomerOperationalException.tenant_id == current.tenant_id,
            CustomerOperationalException.customer_id == customer.id,
        )
    )
    if not row:
        raise not_found("ENTITY_NOT_FOUND", "Excepción operativa no encontrada")

    out = _to_operational_exception_out(row)
    write_audit(
        db,
        tenant_id=current.tenant_id,
        entity_type=EntityType.tenant,
        entity_id=current.tenant_id,
        action="customer.operational_exception_deleted",
        actor_id=current.id,
        metadata={
            "customer_id": str(customer.id),
            "exception_id": str(row.id),
            "date": str(row.date),
            "type": row.type.value,
            "note": row.note,
        },
    )
    db.delete(row)
    db.commit()
    return out


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
