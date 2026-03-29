import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import write_audit
from app.db import get_db
from app.deps import CurrentUser, require_roles
from app.errors import conflict, not_found, unprocessable
from app.models import (
    EntityType,
    ExceptionItem,
    ExceptionStatus,
    ExceptionType,
    Order,
    OrderStatus,
    Plan,
    PlanStatus,
    UserRole,
)
from app.schemas import ExceptionCreateRequest, ExceptionOut, ExceptionRejectRequest, ExceptionsListResponse


router = APIRouter(prefix="/exceptions", tags=["Exceptions"])


@router.post("", response_model=ExceptionOut, status_code=201)
def create_exception(
    payload: ExceptionCreateRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.office, UserRole.logistics, UserRole.admin)),
) -> ExceptionOut:
    order = db.scalar(select(Order).where(Order.id == payload.order_id, Order.tenant_id == current.tenant_id))
    if not order:
        raise not_found("ORDER_NOT_FOUND", "Pedido no encontrado")

    if payload.type != "late_order":
        raise unprocessable("INVALID_EXCEPTION_TYPE", "Solo se admite late_order")

    if order.status == OrderStatus.planned:
        raise conflict("ORDER_ALREADY_PLANNED", "El pedido ya está incluido en un plan")

    if order.status == OrderStatus.exception_rejected:
        raise conflict("ORDER_EXCEPTION_REJECTED", "Pedido rechazado para este service_date")

    locked_plan = db.scalar(
        select(Plan).where(
            Plan.tenant_id == current.tenant_id,
            Plan.service_date == order.service_date,
            Plan.zone_id == order.zone_id,
            Plan.status == PlanStatus.locked,
        )
    )
    if not order.is_late and not locked_plan:
        raise unprocessable(
            "INVALID_EXCEPTION_SCOPE",
            "late_order solo aplica a pedidos tardíos o cuando el plan está locked",
        )

    pending = db.scalar(
        select(ExceptionItem).where(
            ExceptionItem.tenant_id == current.tenant_id,
            ExceptionItem.order_id == order.id,
            ExceptionItem.status == ExceptionStatus.pending,
        )
    )
    if pending:
        raise conflict("EXCEPTION_ALREADY_PENDING", "Ya existe una excepción pendiente")

    now = datetime.now(UTC)
    row = ExceptionItem(
        tenant_id=current.tenant_id,
        order_id=order.id,
        type=ExceptionType.late_order,
        status=ExceptionStatus.pending,
        requested_by=current.id,
        resolved_by=None,
        resolved_at=None,
        note=payload.note,
        created_at=now,
    )
    db.add(row)

    if order.status != OrderStatus.planned:
        order.status = OrderStatus.late_pending_exception

    db.flush()

    write_audit(
        db,
        tenant_id=current.tenant_id,
        entity_type=EntityType.exception,
        entity_id=row.id,
        action="exception.created",
        actor_id=current.id,
        metadata={"order_id": str(order.id), "type": row.type.value},
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("EXCEPTION_CREATE_FAILED", "No se pudo crear la excepción") from exc

    db.refresh(row)
    return ExceptionOut.model_validate(row)


@router.get("", response_model=ExceptionsListResponse)
def list_exceptions(
    status: str | None = None,
    order_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.office, UserRole.logistics, UserRole.admin)),
) -> ExceptionsListResponse:
    query = select(ExceptionItem).where(ExceptionItem.tenant_id == current.tenant_id)
    if status:
        query = query.where(ExceptionItem.status == ExceptionStatus(status))
    if order_id:
        query = query.where(ExceptionItem.order_id == order_id)

    rows = list(db.scalars(query.order_by(ExceptionItem.created_at.desc())))
    return ExceptionsListResponse(items=[ExceptionOut.model_validate(row) for row in rows], total=len(rows))


@router.post("/{exception_id}/approve", response_model=ExceptionOut)
def approve_exception(
    exception_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.logistics, UserRole.admin)),
) -> ExceptionOut:
    row = db.scalar(select(ExceptionItem).where(ExceptionItem.id == exception_id, ExceptionItem.tenant_id == current.tenant_id))
    if not row:
        raise not_found("EXCEPTION_NOT_FOUND", "Excepción no encontrada")

    if row.status != ExceptionStatus.pending:
        raise unprocessable("INVALID_STATE_TRANSITION", "Solo se puede aprobar una excepción pending")

    row.status = ExceptionStatus.approved
    row.resolved_by = current.id
    row.resolved_at = datetime.now(UTC)

    write_audit(
        db,
        tenant_id=current.tenant_id,
        entity_type=EntityType.exception,
        entity_id=row.id,
        action="exception.approved",
        actor_id=current.id,
        metadata={"order_id": str(row.order_id)},
    )

    db.commit()
    db.refresh(row)
    return ExceptionOut.model_validate(row)


@router.post("/{exception_id}/reject", response_model=ExceptionOut)
def reject_exception(
    exception_id: uuid.UUID,
    payload: ExceptionRejectRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.logistics, UserRole.admin)),
) -> ExceptionOut:
    row = db.scalar(select(ExceptionItem).where(ExceptionItem.id == exception_id, ExceptionItem.tenant_id == current.tenant_id))
    if not row:
        raise not_found("EXCEPTION_NOT_FOUND", "Excepción no encontrada")

    if row.status != ExceptionStatus.pending:
        raise unprocessable("INVALID_STATE_TRANSITION", "Solo se puede rechazar una excepción pending")

    row.status = ExceptionStatus.rejected
    row.resolved_by = current.id
    row.resolved_at = datetime.now(UTC)
    row.note = f"{row.note}\nREJECT_REASON: {payload.note}"

    order = db.scalar(select(Order).where(Order.id == row.order_id, Order.tenant_id == current.tenant_id))
    if order and order.status != OrderStatus.planned:
        order.status = OrderStatus.exception_rejected

    write_audit(
        db,
        tenant_id=current.tenant_id,
        entity_type=EntityType.exception,
        entity_id=row.id,
        action="exception.rejected",
        actor_id=current.id,
        metadata={"order_id": str(row.order_id), "reason": payload.note},
    )

    if order:
        write_audit(
            db,
            tenant_id=current.tenant_id,
            entity_type=EntityType.order,
            entity_id=order.id,
            action="order.status_changed",
            actor_id=current.id,
            metadata={"new_status": OrderStatus.exception_rejected.value},
        )

    db.commit()
    db.refresh(row)
    return ExceptionOut.model_validate(row)
