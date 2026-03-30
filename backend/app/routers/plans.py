import uuid
from datetime import UTC, date, datetime
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
    EntityType,
    ExceptionItem,
    ExceptionStatus,
    InclusionType,
    Order,
    OrderStatus,
    Plan,
    PlanOrder,
    PlanStatus,
    Tenant,
    UserRole,
)
from app.schemas import AutoLockRunResponse, PlanCreateRequest, PlanOrderCreateRequest, PlanOrderOut, PlanOut, PlansListResponse


router = APIRouter(prefix="/plans", tags=["Plans"])


def _serialize_plan(db: Session, tenant_id: uuid.UUID, plan: Plan) -> PlanOut:
    plan_orders = list(
        db.scalars(
            select(PlanOrder).where(PlanOrder.tenant_id == tenant_id, PlanOrder.plan_id == plan.id).order_by(PlanOrder.added_at)
        )
    )
    return PlanOut(
        id=plan.id,
        service_date=plan.service_date,
        zone_id=plan.zone_id,
        status=plan.status.value,
        version=plan.version,
        locked_at=plan.locked_at,
        locked_by=plan.locked_by,
        orders=[
            PlanOrderOut(
                id=po.id,
                plan_id=po.plan_id,
                order_id=po.order_id,
                inclusion_type=po.inclusion_type.value,
                added_at=po.added_at,
                added_by=po.added_by,
            )
            for po in plan_orders
        ],
    )


@router.get("", response_model=PlansListResponse)
def list_plans(
    service_date: date | None = None,
    zone_id: uuid.UUID | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.office, UserRole.logistics, UserRole.admin)),
) -> PlansListResponse:
    query = select(Plan).where(Plan.tenant_id == current.tenant_id)
    if service_date:
        query = query.where(Plan.service_date == service_date)
    if zone_id:
        query = query.where(Plan.zone_id == zone_id)
    if status:
        query = query.where(Plan.status == PlanStatus(status))

    plans = list(db.scalars(query.order_by(Plan.service_date.desc())))
    items = [_serialize_plan(db, current.tenant_id, plan) for plan in plans]
    return PlansListResponse(items=items, total=len(items))


@router.post("", response_model=PlanOut, status_code=201)
def create_plan(
    payload: PlanCreateRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.logistics, UserRole.admin)),
) -> PlanOut:
    existing = db.scalar(
        select(Plan).where(
            Plan.tenant_id == current.tenant_id,
            Plan.service_date == payload.service_date,
            Plan.zone_id == payload.zone_id,
        )
    )
    if existing:
        raise conflict("PLAN_ALREADY_EXISTS", "Ya existe un plan para esa fecha y zona")

    now = datetime.now(UTC)
    plan = Plan(
        tenant_id=current.tenant_id,
        service_date=payload.service_date,
        zone_id=payload.zone_id,
        status=PlanStatus.open,
        version=1,
        locked_at=None,
        locked_by=None,
        created_at=now,
        updated_at=now,
    )
    db.add(plan)
    db.flush()

    write_audit(
        db,
        tenant_id=current.tenant_id,
        entity_type=EntityType.plan,
        entity_id=plan.id,
        action="plan.created",
        actor_id=current.id,
        metadata={"service_date": str(plan.service_date), "zone_id": str(plan.zone_id)},
    )

    db.commit()
    db.refresh(plan)
    return _serialize_plan(db, current.tenant_id, plan)


@router.post("/auto-lock/run", response_model=AutoLockRunResponse)
def run_auto_lock(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.logistics, UserRole.admin)),
) -> AutoLockRunResponse:
    tenant = db.scalar(select(Tenant).where(Tenant.id == current.tenant_id))
    if not tenant:
        raise not_found("TENANT_NOT_FOUND", "Tenant no encontrado")

    try:
        tenant_now = datetime.now(ZoneInfo(tenant.default_timezone))
    except ZoneInfoNotFoundError as exc:
        raise unprocessable("INVALID_TIMEZONE", "Timezone del tenant no válida") from exc

    target_service_date = tenant_now.date() + date.resolution
    run_window_at = tenant_now.replace(
        hour=tenant.default_cutoff_time.hour,
        minute=tenant.default_cutoff_time.minute,
        second=tenant.default_cutoff_time.second,
        microsecond=0,
    )
    window_reached = tenant_now >= run_window_at
    if not tenant.auto_lock_enabled or not window_reached:
        return AutoLockRunResponse(
            tenant_id=current.tenant_id,
            service_date=target_service_date,
            auto_lock_enabled=tenant.auto_lock_enabled,
            window_reached=window_reached,
            considered_open_plans=0,
            locked_count=0,
            locked_plan_ids=[],
        )

    open_plans = list(
        db.scalars(
            select(Plan).where(
                Plan.tenant_id == current.tenant_id,
                Plan.service_date == target_service_date,
                Plan.status == PlanStatus.open,
            )
        )
    )

    now_utc = datetime.now(UTC)
    locked_ids: list[uuid.UUID] = []
    for plan in open_plans:
        plan.status = PlanStatus.locked
        plan.locked_at = now_utc
        plan.locked_by = current.id
        plan.version += 1
        locked_ids.append(plan.id)

        write_audit(
            db,
            tenant_id=current.tenant_id,
            entity_type=EntityType.plan,
            entity_id=plan.id,
            action="auto_lock_plan",
            actor_id=current.id,
            metadata={
                "service_date": str(plan.service_date),
                "zone_id": str(plan.zone_id),
                "previous_status": PlanStatus.open.value,
                "new_status": PlanStatus.locked.value,
            },
        )

    db.commit()
    return AutoLockRunResponse(
        tenant_id=current.tenant_id,
        service_date=target_service_date,
        auto_lock_enabled=tenant.auto_lock_enabled,
        window_reached=window_reached,
        considered_open_plans=len(open_plans),
        locked_count=len(locked_ids),
        locked_plan_ids=locked_ids,
    )


@router.get("/{plan_id}", response_model=PlanOut)
def get_plan(
    plan_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.office, UserRole.logistics, UserRole.admin)),
) -> PlanOut:
    plan = db.scalar(select(Plan).where(Plan.id == plan_id, Plan.tenant_id == current.tenant_id))
    if not plan:
        raise not_found("PLAN_NOT_FOUND", "Plan no encontrado")
    return _serialize_plan(db, current.tenant_id, plan)


@router.post("/{plan_id}/lock", response_model=PlanOut)
def lock_plan(
    plan_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.logistics, UserRole.admin)),
) -> PlanOut:
    plan = db.scalar(select(Plan).where(Plan.id == plan_id, Plan.tenant_id == current.tenant_id))
    if not plan:
        raise not_found("PLAN_NOT_FOUND", "Plan no encontrado")

    if plan.status != PlanStatus.open:
        raise unprocessable("INVALID_STATE_TRANSITION", "Solo se puede bloquear un plan open")

    plan.status = PlanStatus.locked
    plan.locked_at = datetime.now(UTC)
    plan.locked_by = current.id
    plan.version += 1

    write_audit(
        db,
        tenant_id=current.tenant_id,
        entity_type=EntityType.plan,
        entity_id=plan.id,
        action="plan.locked",
        actor_id=current.id,
        metadata={"previous_status": "open", "new_status": "locked"},
    )

    db.commit()
    db.refresh(plan)
    return _serialize_plan(db, current.tenant_id, plan)


@router.post("/{plan_id}/orders", response_model=PlanOrderOut)
def include_order(
    plan_id: uuid.UUID,
    payload: PlanOrderCreateRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.logistics, UserRole.admin)),
) -> PlanOrderOut:
    plan = db.scalar(select(Plan).where(Plan.id == plan_id, Plan.tenant_id == current.tenant_id))
    if not plan:
        raise not_found("PLAN_NOT_FOUND", "Plan no encontrado")

    order = db.scalar(select(Order).where(Order.id == payload.order_id, Order.tenant_id == current.tenant_id))
    if not order:
        raise not_found("ORDER_NOT_FOUND", "Pedido no encontrado")

    if order.service_date != plan.service_date or order.zone_id != plan.zone_id:
        raise conflict("PLAN_ORDER_SCOPE_MISMATCH", "El pedido no pertenece a la fecha/zona del plan")

    if plan.status == PlanStatus.dispatched:
        raise conflict("PLAN_DISPATCHED", "El plan ya está despachado")

    if order.status == OrderStatus.exception_rejected:
        raise conflict("ORDER_EXCEPTION_REJECTED", "Pedido rechazado para este service_date")

    approved_exception = db.scalar(
        select(ExceptionItem).where(
            ExceptionItem.tenant_id == current.tenant_id,
            ExceptionItem.order_id == order.id,
            ExceptionItem.status == ExceptionStatus.approved,
        )
    )

    if plan.status == PlanStatus.locked and not approved_exception:
        raise conflict("EXCEPTION_REQUIRED", "Plan locked requiere excepción aprobada")

    if plan.status == PlanStatus.open:
        if order.status == OrderStatus.ready_for_planning:
            inclusion = InclusionType.normal
        elif approved_exception:
            inclusion = InclusionType.exception
        else:
            raise conflict("EXCEPTION_REQUIRED", "El pedido requiere excepción aprobada")
    else:
        inclusion = InclusionType.exception

    now = datetime.now(UTC)
    row = PlanOrder(
        tenant_id=current.tenant_id,
        plan_id=plan.id,
        order_id=order.id,
        inclusion_type=inclusion,
        added_at=now,
        added_by=current.id,
    )
    db.add(row)

    order.status = OrderStatus.planned
    db.flush()

    write_audit(
        db,
        tenant_id=current.tenant_id,
        entity_type=EntityType.plan_order,
        entity_id=row.id,
        action="plan_order.included",
        actor_id=current.id,
        metadata={"plan_id": str(plan.id), "order_id": str(order.id), "inclusion_type": inclusion.value},
    )
    write_audit(
        db,
        tenant_id=current.tenant_id,
        entity_type=EntityType.order,
        entity_id=order.id,
        action="order.status_changed",
        actor_id=current.id,
        metadata={"new_status": OrderStatus.planned.value},
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("ORDER_ALREADY_PLANNED", "El pedido ya está incluido en un plan") from exc

    db.refresh(row)
    return PlanOrderOut(
        id=row.id,
        plan_id=row.plan_id,
        order_id=row.order_id,
        inclusion_type=row.inclusion_type.value,
        added_at=row.added_at,
        added_by=row.added_by,
    )
