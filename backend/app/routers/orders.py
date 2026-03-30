import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.audit import write_audit
from app.db import get_db
from app.deps import CurrentUser, require_roles
from app.domain import (
    build_effective_cutoff_at,
    compute_lateness,
    ensure_aware_utc,
    initial_order_status,
    resolve_cutoff,
)
from app.errors import not_found
from app.errors import unprocessable
from app.models import (
    Customer,
    EntityType,
    ExceptionItem,
    ExceptionStatus,
    Order,
    OrderIntakeType,
    OrderLine,
    OrderStatus,
    Plan,
    PlanStatus,
    SourceChannel,
    Tenant,
    UserRole,
    Zone,
)
from app.schemas import (
    OrderIngestionBatchInput,
    OrderIngestionItemResult,
    OrderIngestionResult,
    OrderLineOut,
    OrderOut,
    OrderWeightUpdateRequest,
    OrdersListResponse,
    PendingQueueListResponse,
    PendingQueueReason,
    PendingQueueItemOut,
)


router = APIRouter(tags=["Orders"])

_PENDING_QUEUE_REASON_PRIORITY: dict[str, int] = {
    "LOCKED_PLAN_EXCEPTION_REQUIRED": 0,
    "LATE_PENDING_EXCEPTION": 1,
    "EXCEPTION_REJECTED": 2,
}


def _serialize_order(order: Order, lines: list[OrderLine]) -> OrderOut:
    return OrderOut(
        id=order.id,
        customer_id=order.customer_id,
        zone_id=order.zone_id,
        external_ref=order.external_ref,
        requested_date=order.requested_date,
        service_date=order.service_date,
        created_at=order.created_at,
        status=order.status.value,
        is_late=order.is_late,
        lateness_reason=order.lateness_reason,
        effective_cutoff_at=order.effective_cutoff_at,
        source_channel=order.source_channel.value,
        intake_type=order.intake_type.value,
        total_weight_kg=order.total_weight_kg,
        lines=[
            OrderLineOut(
                id=line.id,
                sku=line.sku,
                qty=line.qty,
                weight_kg=line.weight_kg,
                volume_m3=line.volume_m3,
            )
            for line in lines
        ],
    )


def _resolve_intake_type(db: Session, tenant_id: uuid.UUID, customer_id: uuid.UUID, service_date: date) -> OrderIntakeType:
    has_existing = db.scalar(
        select(Order.id)
        .where(
            Order.tenant_id == tenant_id,
            Order.customer_id == customer_id,
            Order.service_date == service_date,
        )
        .limit(1)
    )
    if has_existing:
        return OrderIntakeType.same_customer_addon
    return OrderIntakeType.new_order


@router.post("/ingestion/orders", response_model=OrderIngestionResult)
def ingest_orders(
    payload: OrderIngestionBatchInput,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.office, UserRole.logistics, UserRole.admin)),
) -> OrderIngestionResult:
    tenant = db.scalar(select(Tenant).where(Tenant.id == current.tenant_id))
    if not tenant:
        raise not_found("TENANT_NOT_FOUND", "Tenant no encontrado")

    created = 0
    updated = 0
    rejected = 0
    items: list[OrderIngestionItemResult] = []

    for in_order in payload.orders:
        existing = db.scalar(
            select(Order).where(
                Order.tenant_id == current.tenant_id,
                Order.external_ref == in_order.external_ref,
                Order.service_date == in_order.service_date,
            )
        )

        now = datetime.now(UTC)
        if existing:
            if existing.customer_id != in_order.customer_id:
                rejected += 1
                items.append(
                    OrderIngestionItemResult(
                        external_ref=in_order.external_ref,
                        service_date=in_order.service_date,
                        result="rejected",
                        order_id=existing.id,
                        reason="immutable_customer_id_mismatch",
                    )
                )
                continue

            existing.requested_date = in_order.requested_date
            existing.source_channel = SourceChannel(in_order.source_channel)
            existing.updated_at = now

            db.execute(delete(OrderLine).where(OrderLine.order_id == existing.id, OrderLine.tenant_id == current.tenant_id))
            for line in in_order.lines:
                db.add(
                    OrderLine(
                        tenant_id=current.tenant_id,
                        order_id=existing.id,
                        sku=line.sku,
                        qty=line.qty,
                        weight_kg=line.weight_kg,
                        volume_m3=line.volume_m3,
                        created_at=now,
                    )
                )

            write_audit(
                db,
                tenant_id=current.tenant_id,
                entity_type=EntityType.order,
                entity_id=existing.id,
                action="order.ingestion_updated",
                actor_id=current.id,
                metadata={
                    "external_ref": existing.external_ref,
                    "created_at_immutable": True,
                    "lateness_immutable": True,
                    "intake_type_immutable": True,
                    "intake_type": existing.intake_type.value,
                },
            )
            updated += 1
            items.append(
                OrderIngestionItemResult(
                    external_ref=existing.external_ref,
                    service_date=existing.service_date,
                    result="updated",
                    order_id=existing.id,
                )
            )
            continue

        customer = db.scalar(
            select(Customer).where(Customer.id == in_order.customer_id, Customer.tenant_id == current.tenant_id)
        )
        if not customer:
            rejected += 1
            items.append(
                OrderIngestionItemResult(
                    external_ref=in_order.external_ref,
                    service_date=in_order.service_date,
                    result="rejected",
                    reason="customer_not_found",
                )
            )
            continue

        zone = db.scalar(select(Zone).where(Zone.id == customer.zone_id, Zone.tenant_id == current.tenant_id))
        if not zone:
            rejected += 1
            items.append(
                OrderIngestionItemResult(
                    external_ref=in_order.external_ref,
                    service_date=in_order.service_date,
                    result="rejected",
                    reason="zone_not_found",
                )
            )
            continue

        cutoff_time, timezone = resolve_cutoff(customer, zone, tenant)
        effective_cutoff = build_effective_cutoff_at(in_order.service_date, cutoff_time, timezone)
        created_at = ensure_aware_utc(in_order.created_at)
        is_late, late_reason = compute_lateness(created_at, effective_cutoff)
        intake_type = _resolve_intake_type(db, current.tenant_id, customer.id, in_order.service_date)

        order = Order(
            tenant_id=current.tenant_id,
            customer_id=customer.id,
            zone_id=zone.id,
            external_ref=in_order.external_ref,
            requested_date=in_order.requested_date,
            service_date=in_order.service_date,
            created_at=created_at,
            status=initial_order_status(is_late),
            is_late=is_late,
            lateness_reason=late_reason,
            effective_cutoff_at=effective_cutoff,
            source_channel=SourceChannel(in_order.source_channel),
            intake_type=intake_type,
            ingested_at=now,
            updated_at=now,
        )
        db.add(order)
        db.flush()

        for line in in_order.lines:
            db.add(
                OrderLine(
                    tenant_id=current.tenant_id,
                    order_id=order.id,
                    sku=line.sku,
                    qty=line.qty,
                    weight_kg=line.weight_kg,
                    volume_m3=line.volume_m3,
                    created_at=now,
                )
            )

        write_audit(
            db,
            tenant_id=current.tenant_id,
            entity_type=EntityType.order,
            entity_id=order.id,
            action="order.ingestion_created",
            actor_id=current.id,
            metadata={"external_ref": order.external_ref, "intake_type": order.intake_type.value},
        )

        created += 1
        items.append(
            OrderIngestionItemResult(
                external_ref=order.external_ref,
                service_date=order.service_date,
                result="created",
                order_id=order.id,
            )
        )

    db.commit()
    return OrderIngestionResult(created=created, updated=updated, rejected=rejected, items=items)


@router.get("/orders", response_model=OrdersListResponse)
def list_orders(
    service_date: date | None = None,
    zone_id: uuid.UUID | None = None,
    status: str | None = None,
    is_late: bool | None = None,
    external_ref: str | None = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.office, UserRole.logistics, UserRole.admin)),
) -> OrdersListResponse:
    query = select(Order).where(Order.tenant_id == current.tenant_id)

    if service_date:
        query = query.where(Order.service_date == service_date)
    if zone_id:
        query = query.where(Order.zone_id == zone_id)
    if status:
        query = query.where(Order.status == OrderStatus(status))
    if is_late is not None:
        query = query.where(Order.is_late == is_late)
    if external_ref:
        query = query.where(Order.external_ref == external_ref)

    orders = list(db.scalars(query.order_by(Order.created_at.desc())))
    order_ids = [order.id for order in orders]

    lines_by_order: dict[uuid.UUID, list[OrderLine]] = {order_id: [] for order_id in order_ids}
    if order_ids:
        lines = list(
            db.scalars(
                select(OrderLine).where(OrderLine.tenant_id == current.tenant_id, OrderLine.order_id.in_(order_ids))
            )
        )
        for line in lines:
            lines_by_order.setdefault(line.order_id, []).append(line)

    serialized = [_serialize_order(order, lines_by_order.get(order.id, [])) for order in orders]
    return OrdersListResponse(items=serialized, total=len(serialized))


@router.get("/orders/pending-queue", response_model=PendingQueueListResponse)
def list_pending_queue(
    service_date: date,
    zone_id: uuid.UUID | None = None,
    reason: PendingQueueReason | None = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.office, UserRole.logistics, UserRole.admin)),
) -> PendingQueueListResponse:
    candidate_statuses = (
        OrderStatus.late_pending_exception,
        OrderStatus.ready_for_planning,
        OrderStatus.exception_rejected,
    )

    query = select(Order).where(
        Order.tenant_id == current.tenant_id,
        Order.service_date == service_date,
        Order.status.in_(candidate_statuses),
    )
    if zone_id:
        query = query.where(Order.zone_id == zone_id)

    candidates = list(db.scalars(query))
    if not candidates:
        return PendingQueueListResponse(items=[], total=0)

    candidate_ids = [order.id for order in candidates]
    locked_plans_query = select(Plan.zone_id).where(
        Plan.tenant_id == current.tenant_id,
        Plan.service_date == service_date,
        Plan.status == PlanStatus.locked,
    )
    if zone_id:
        locked_plans_query = locked_plans_query.where(Plan.zone_id == zone_id)
    locked_zone_ids = set(db.scalars(locked_plans_query))

    approved_exception_order_ids = set(
        db.scalars(
            select(ExceptionItem.order_id).where(
                ExceptionItem.tenant_id == current.tenant_id,
                ExceptionItem.status == ExceptionStatus.approved,
                ExceptionItem.order_id.in_(candidate_ids),
            )
        )
    )
    pending_exception_order_ids = set(
        db.scalars(
            select(ExceptionItem.order_id).where(
                ExceptionItem.tenant_id == current.tenant_id,
                ExceptionItem.status == ExceptionStatus.pending,
                ExceptionItem.order_id.in_(candidate_ids),
            )
        )
    )

    items: list[PendingQueueItemOut] = []
    for order in candidates:
        queue_reason: PendingQueueReason | None = None
        if (
            order.status == OrderStatus.late_pending_exception
            and (order.id in pending_exception_order_ids or order.id not in approved_exception_order_ids)
        ):
            queue_reason = "LATE_PENDING_EXCEPTION"
        elif order.status == OrderStatus.exception_rejected:
            queue_reason = "EXCEPTION_REJECTED"
        elif (
            order.status == OrderStatus.ready_for_planning
            and order.zone_id in locked_zone_ids
            and order.id not in approved_exception_order_ids
        ):
            queue_reason = "LOCKED_PLAN_EXCEPTION_REQUIRED"

        if queue_reason is None:
            continue
        if reason and queue_reason != reason:
            continue

        items.append(
            PendingQueueItemOut(
                order_id=order.id,
                external_ref=order.external_ref,
                status=order.status.value,
                reason=queue_reason,
                service_date=order.service_date,
                zone_id=order.zone_id,
                created_at=order.created_at,
            )
        )

    items.sort(
        key=lambda item: (
            _PENDING_QUEUE_REASON_PRIORITY[item.reason],
            item.created_at,
            str(item.order_id),
        )
    )
    return PendingQueueListResponse(items=items, total=len(items))


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.office, UserRole.logistics, UserRole.admin)),
) -> OrderOut:
    order = db.scalar(select(Order).where(Order.id == order_id, Order.tenant_id == current.tenant_id))
    if not order:
        raise not_found("ORDER_NOT_FOUND", "Pedido no encontrado")

    lines = list(db.scalars(select(OrderLine).where(OrderLine.order_id == order.id, OrderLine.tenant_id == current.tenant_id)))
    return _serialize_order(order, lines)


@router.patch("/orders/{order_id}/weight", response_model=OrderOut)
def update_order_weight(
    order_id: uuid.UUID,
    payload: OrderWeightUpdateRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.logistics, UserRole.admin)),
) -> OrderOut:
    order = db.scalar(select(Order).where(Order.id == order_id, Order.tenant_id == current.tenant_id))
    if not order:
        raise not_found("ORDER_NOT_FOUND", "Pedido no encontrado")

    if payload.total_weight_kg is not None and payload.total_weight_kg < 0:
        raise unprocessable("INVALID_WEIGHT_VALUE", "total_weight_kg debe ser mayor o igual a 0")

    previous_weight = order.total_weight_kg
    order.total_weight_kg = payload.total_weight_kg
    order.updated_at = datetime.now(UTC)

    write_audit(
        db,
        tenant_id=current.tenant_id,
        entity_type=EntityType.order,
        entity_id=order.id,
        action="order.weight_updated",
        actor_id=current.id,
        metadata={
            "previous_total_weight_kg": str(previous_weight) if previous_weight is not None else None,
            "new_total_weight_kg": str(order.total_weight_kg) if order.total_weight_kg is not None else None,
        },
    )

    db.commit()
    db.refresh(order)
    lines = list(db.scalars(select(OrderLine).where(OrderLine.order_id == order.id, OrderLine.tenant_id == current.tenant_id)))
    return _serialize_order(order, lines)
