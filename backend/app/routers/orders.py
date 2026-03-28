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
from app.models import (
    Customer,
    EntityType,
    Order,
    OrderLine,
    OrderStatus,
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
    OrdersListResponse,
)


router = APIRouter(tags=["Orders"])


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
            metadata={"external_ref": order.external_ref},
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
