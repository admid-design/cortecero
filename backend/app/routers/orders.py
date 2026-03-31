import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
    CustomerOperationalException,
    CustomerOperationalExceptionType,
    CustomerOperationalProfile,
    EntityType,
    ExceptionItem,
    ExceptionStatus,
    Order,
    OrderIntakeType,
    OrderLine,
    OperationalReasonCatalog,
    OrderOperationalSnapshot,
    OrderStatus,
    Plan,
    PlanStatus,
    SourceChannel,
    Tenant,
    UserRole,
    Zone,
)
from app.schemas import (
    OperationalQueueItemOut,
    OperationalQueueListResponse,
    OperationalExplanationOut,
    OperationalSnapshotRunResponse,
    OrderIngestionBatchInput,
    OrderIngestionItemResult,
    OrderIngestionResult,
    OrderLineOut,
    OrderOut,
    OrderWeightUpdateRequest,
    OrdersListResponse,
    PendingQueueListResponse,
    PendingQueueItemOut,
    PendingQueueReason,
)


router = APIRouter(tags=["Orders"])

_PENDING_QUEUE_REASON_PRIORITY: dict[str, int] = {
    "LOCKED_PLAN_EXCEPTION_REQUIRED": 0,
    "LATE_PENDING_EXCEPTION": 1,
    "EXCEPTION_REJECTED": 2,
}


_OPERATIONAL_REASON_PRECEDENCE: tuple[str, ...] = (
    "CUSTOMER_DATE_BLOCKED",
    "CUSTOMER_NOT_ACCEPTING_ORDERS",
    "OUTSIDE_CUSTOMER_WINDOW",
    "INSUFFICIENT_LEAD_TIME",
)
_OPERATIONAL_REASON_PRIORITY: dict[str, int] = {
    reason: idx for idx, reason in enumerate(_OPERATIONAL_REASON_PRECEDENCE)
}
_OPERATIONAL_RULE_VERSION = "r6-operational-eval-v1"
_OPERATIONAL_REASON_FALLBACK_CATEGORY = "catalog_mismatch"
_OPERATIONAL_REASON_FALLBACK_SEVERITY = "critical"
_OPERATIONAL_SNAPSHOT_BUCKET_HOURS = 1


@dataclass(frozen=True)
class _ResolvedTimezone:
    tzinfo: ZoneInfo
    timezone_used: str
    timezone_source: Literal["zone", "tenant_default", "utc_fallback"]


@dataclass(frozen=True)
class _OperationalEvaluation:
    reason_code: str | None
    reason_category: str | None
    severity: Literal["low", "medium", "high", "critical"] | None
    timezone_used: str
    timezone_source: Literal["zone", "tenant_default", "utc_fallback"]
    rule_version: str
    catalog_status: Literal["active", "inactive", "missing", "not_applicable"]


@dataclass(frozen=True)
class _OperationalContext:
    profiles_by_customer: dict[uuid.UUID, CustomerOperationalProfile]
    date_restriction_keys: set[tuple[uuid.UUID, date]]
    zones_by_id: dict[uuid.UUID, Zone]
    reason_catalog_by_code: dict[str, OperationalReasonCatalog]


def _resolve_timezone(tenant_default_timezone: str, zone_timezone: str | None) -> _ResolvedTimezone:
    if zone_timezone:
        try:
            return _ResolvedTimezone(
                tzinfo=ZoneInfo(zone_timezone),
                timezone_used=zone_timezone,
                timezone_source="zone",
            )
        except ZoneInfoNotFoundError:
            pass
    if tenant_default_timezone:
        try:
            return _ResolvedTimezone(
                tzinfo=ZoneInfo(tenant_default_timezone),
                timezone_used=tenant_default_timezone,
                timezone_source="tenant_default",
            )
        except ZoneInfoNotFoundError:
            pass
    return _ResolvedTimezone(
        tzinfo=ZoneInfo("UTC"),
        timezone_used="UTC",
        timezone_source="utc_fallback",
    )


def _is_within_window(created_local_time: time, window_start: time | None, window_end: time | None) -> bool:
    if window_start is None or window_end is None:
        return True
    if window_start == window_end:
        return False
    if window_start < window_end:
        return window_start <= created_local_time <= window_end
    return created_local_time >= window_start or created_local_time <= window_end


def _resolve_operational_reason(
    order: Order,
    *,
    profile: CustomerOperationalProfile | None,
    has_date_restriction: bool,
    tzinfo: ZoneInfo,
) -> str | None:
    reasons: list[str] = []

    if has_date_restriction:
        reasons.append("CUSTOMER_DATE_BLOCKED")

    if profile is not None:
        if not profile.accept_orders:
            reasons.append("CUSTOMER_NOT_ACCEPTING_ORDERS")

        created_local = ensure_aware_utc(order.created_at).astimezone(tzinfo)
        if not _is_within_window(created_local.time(), profile.window_start, profile.window_end):
            reasons.append("OUTSIDE_CUSTOMER_WINDOW")

        if profile.min_lead_hours > 0:
            service_start_local = datetime.combine(order.service_date, time.min, tzinfo=tzinfo)
            min_lead_delta = timedelta(hours=profile.min_lead_hours)
            if service_start_local - created_local < min_lead_delta:
                reasons.append("INSUFFICIENT_LEAD_TIME")

    if not reasons:
        return None

    reasons.sort(key=lambda item: _OPERATIONAL_REASON_PRIORITY[item])
    return reasons[0]


def _build_operational_explanation(
    reason_code: str | None,
    *,
    timezone: _ResolvedTimezone,
    reason_catalog_by_code: dict[str, OperationalReasonCatalog],
) -> _OperationalEvaluation:
    if reason_code is None:
        return _OperationalEvaluation(
            reason_code=None,
            reason_category=None,
            severity=None,
            timezone_used=timezone.timezone_used,
            timezone_source=timezone.timezone_source,
            rule_version=_OPERATIONAL_RULE_VERSION,
            catalog_status="not_applicable",
        )

    catalog_row = reason_catalog_by_code.get(reason_code)
    if catalog_row is None:
        return _OperationalEvaluation(
            reason_code=reason_code,
            reason_category=_OPERATIONAL_REASON_FALLBACK_CATEGORY,
            severity=_OPERATIONAL_REASON_FALLBACK_SEVERITY,
            timezone_used=timezone.timezone_used,
            timezone_source=timezone.timezone_source,
            rule_version=_OPERATIONAL_RULE_VERSION,
            catalog_status="missing",
        )
    if not catalog_row.active:
        return _OperationalEvaluation(
            reason_code=reason_code,
            reason_category=_OPERATIONAL_REASON_FALLBACK_CATEGORY,
            severity=_OPERATIONAL_REASON_FALLBACK_SEVERITY,
            timezone_used=timezone.timezone_used,
            timezone_source=timezone.timezone_source,
            rule_version=_OPERATIONAL_RULE_VERSION,
            catalog_status="inactive",
        )
    return _OperationalEvaluation(
        reason_code=reason_code,
        reason_category=catalog_row.category,
        severity=catalog_row.severity,
        timezone_used=timezone.timezone_used,
        timezone_source=timezone.timezone_source,
        rule_version=_OPERATIONAL_RULE_VERSION,
        catalog_status="active",
    )


def _default_operational_evaluation() -> _OperationalEvaluation:
    return _OperationalEvaluation(
        reason_code=None,
        reason_category=None,
        severity=None,
        timezone_used="UTC",
        timezone_source="utc_fallback",
        rule_version=_OPERATIONAL_RULE_VERSION,
        catalog_status="not_applicable",
    )


def _snapshot_bucket_bounds(now_utc: datetime) -> tuple[datetime, datetime]:
    bucket_start = now_utc.replace(minute=0, second=0, microsecond=0)
    bucket_end = bucket_start + timedelta(hours=_OPERATIONAL_SNAPSHOT_BUCKET_HOURS)
    return bucket_start, bucket_end


def _build_snapshot_evidence(
    order: Order,
    *,
    profile: CustomerOperationalProfile | None,
    timezone: _ResolvedTimezone,
) -> dict:
    created_local = ensure_aware_utc(order.created_at).astimezone(timezone.tzinfo)
    service_local = datetime.combine(order.service_date, time.min, tzinfo=timezone.tzinfo)
    window_start = profile.window_start if profile else None
    window_end = profile.window_end if profile else None

    if window_start is None or window_end is None:
        window_type = "none"
    elif window_start < window_end:
        window_type = "same_day"
    elif window_start > window_end:
        window_type = "cross_midnight"
    else:
        window_type = "invalid_equal"

    return {
        "window_type": window_type,
        "window_start": window_start.isoformat() if window_start else None,
        "window_end": window_end.isoformat() if window_end else None,
        "lead_hours_required": profile.min_lead_hours if profile else 0,
        "created_local": created_local.isoformat(),
        "service_local": service_local.isoformat(),
        "timezone_source": timezone.timezone_source,
    }


def _serialize_order(order: Order, lines: list[OrderLine], *, operational: _OperationalEvaluation) -> OrderOut:
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
        operational_state="restricted" if operational.reason_code else "eligible",
        operational_reason=operational.reason_code,
        operational_explanation=OperationalExplanationOut(
            reason_code=operational.reason_code,
            reason_category=operational.reason_category,
            severity=operational.severity,
            timezone_used=operational.timezone_used,
            timezone_source=operational.timezone_source,
            rule_version=operational.rule_version,
            catalog_status=operational.catalog_status,
        ),
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


def _load_operational_context(
    db: Session,
    *,
    tenant: Tenant,
    orders: list[Order],
) -> _OperationalContext:
    customer_ids = {order.customer_id for order in orders}
    service_dates = {order.service_date for order in orders}
    zone_ids = {order.zone_id for order in orders}

    profiles = list(
        db.scalars(
            select(CustomerOperationalProfile).where(
                CustomerOperationalProfile.tenant_id == tenant.id,
                CustomerOperationalProfile.customer_id.in_(customer_ids),
            )
        )
    )
    profiles_by_customer: dict[uuid.UUID, CustomerOperationalProfile] = {
        profile.customer_id: profile for profile in profiles
    }

    date_restriction_keys = {
        (customer_id, restriction_date)
        for customer_id, restriction_date in db.execute(
            select(
                CustomerOperationalException.customer_id,
                CustomerOperationalException.date,
            ).where(
                CustomerOperationalException.tenant_id == tenant.id,
                CustomerOperationalException.customer_id.in_(customer_ids),
                CustomerOperationalException.date.in_(service_dates),
                CustomerOperationalException.type.in_(
                    [
                        CustomerOperationalExceptionType.blocked,
                        CustomerOperationalExceptionType.restricted,
                    ]
                ),
            )
        ).all()
    }

    zones = list(
        db.scalars(
            select(Zone).where(
                Zone.tenant_id == tenant.id,
                Zone.id.in_(zone_ids),
            )
        )
    )
    zones_by_id: dict[uuid.UUID, Zone] = {zone.id: zone for zone in zones}

    reason_catalog_by_code: dict[str, OperationalReasonCatalog] = {
        row.code: row
        for row in db.scalars(
            select(OperationalReasonCatalog).where(
                OperationalReasonCatalog.code.in_(_OPERATIONAL_REASON_PRECEDENCE)
            )
        )
    }

    return _OperationalContext(
        profiles_by_customer=profiles_by_customer,
        date_restriction_keys=date_restriction_keys,
        zones_by_id=zones_by_id,
        reason_catalog_by_code=reason_catalog_by_code,
    )


def _build_operational_evaluation_map(
    db: Session,
    *,
    tenant: Tenant,
    orders: list[Order],
) -> dict[uuid.UUID, _OperationalEvaluation]:
    if not orders:
        return {}
    context = _load_operational_context(db, tenant=tenant, orders=orders)

    evaluation_by_order_id: dict[uuid.UUID, _OperationalEvaluation] = {}
    for order in orders:
        evaluation_by_order_id[order.id], _, _ = _evaluate_order_operational(
            order,
            tenant=tenant,
            context=context,
        )

    return evaluation_by_order_id


def _evaluate_order_operational(
    order: Order,
    *,
    tenant: Tenant,
    context: _OperationalContext,
) -> tuple[_OperationalEvaluation, _ResolvedTimezone, CustomerOperationalProfile | None]:
    zone = context.zones_by_id.get(order.zone_id)
    resolved_timezone = _resolve_timezone(
        tenant_default_timezone=tenant.default_timezone,
        zone_timezone=zone.timezone if zone else None,
    )
    profile = context.profiles_by_customer.get(order.customer_id)
    reason_code = _resolve_operational_reason(
        order,
        profile=profile,
        has_date_restriction=(order.customer_id, order.service_date) in context.date_restriction_keys,
        tzinfo=resolved_timezone.tzinfo,
    )
    evaluation = _build_operational_explanation(
        reason_code,
        timezone=resolved_timezone,
        reason_catalog_by_code=context.reason_catalog_by_code,
    )
    return evaluation, resolved_timezone, profile


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
    tenant = db.scalar(select(Tenant).where(Tenant.id == current.tenant_id))
    if not tenant:
        raise not_found("TENANT_NOT_FOUND", "Tenant no encontrado")

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

    operational_by_order = _build_operational_evaluation_map(db, tenant=tenant, orders=orders)
    serialized = [
        _serialize_order(
            order,
            lines_by_order.get(order.id, []),
            operational=operational_by_order.get(order.id) or _default_operational_evaluation(),
        )
        for order in orders
    ]
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


@router.get("/orders/operational-queue", response_model=OperationalQueueListResponse)
def list_operational_queue(
    service_date: date,
    zone_id: uuid.UUID | None = None,
    reason: str | None = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.office, UserRole.logistics, UserRole.admin)),
) -> OperationalQueueListResponse:
    tenant = db.scalar(select(Tenant).where(Tenant.id == current.tenant_id))
    if not tenant:
        raise not_found("TENANT_NOT_FOUND", "Tenant no encontrado")
    if reason is not None and reason not in _OPERATIONAL_REASON_PRIORITY:
        raise unprocessable(
            "INVALID_OPERATIONAL_FILTER",
            "reason debe ser CUSTOMER_DATE_BLOCKED, CUSTOMER_NOT_ACCEPTING_ORDERS, OUTSIDE_CUSTOMER_WINDOW o INSUFFICIENT_LEAD_TIME",
        )

    query = select(Order).where(Order.tenant_id == current.tenant_id, Order.service_date == service_date)
    if zone_id is not None:
        query = query.where(Order.zone_id == zone_id)

    orders = list(db.scalars(query))
    if not orders:
        return OperationalQueueListResponse(items=[], total=0)

    operational_by_order = _build_operational_evaluation_map(db, tenant=tenant, orders=orders)

    items: list[OperationalQueueItemOut] = []
    for order in orders:
        operational = operational_by_order.get(order.id) or _default_operational_evaluation()
        operational_reason = operational.reason_code
        if operational_reason is None:
            continue
        if reason is not None and operational_reason != reason:
            continue

        items.append(
            OperationalQueueItemOut(
                order_id=order.id,
                external_ref=order.external_ref,
                customer_id=order.customer_id,
                zone_id=order.zone_id,
                service_date=order.service_date,
                status=order.status.value,
                intake_type=order.intake_type.value,
                reason=operational_reason,
                created_at=order.created_at,
            )
        )

    items.sort(
        key=lambda item: (
            _OPERATIONAL_REASON_PRIORITY[item.reason],
            item.created_at,
            str(item.order_id),
        )
    )
    return OperationalQueueListResponse(items=items, total=len(items))


@router.post("/orders/operational-snapshots/run", response_model=OperationalSnapshotRunResponse)
def run_operational_snapshots(
    service_date: date,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.admin)),
) -> OperationalSnapshotRunResponse:
    tenant = db.scalar(select(Tenant).where(Tenant.id == current.tenant_id))
    if not tenant:
        raise not_found("TENANT_NOT_FOUND", "Tenant no encontrado")

    orders = list(
        db.scalars(
            select(Order)
            .where(
                Order.tenant_id == current.tenant_id,
                Order.service_date == service_date,
            )
            .order_by(Order.created_at.asc(), Order.id.asc())
        )
    )
    considered_orders = len(orders)

    run_ts = datetime.now(UTC)
    bucket_start, bucket_end = _snapshot_bucket_bounds(run_ts)
    generated_snapshot_ids: list[uuid.UUID] = []
    skipped_existing = 0

    if orders:
        context = _load_operational_context(db, tenant=tenant, orders=orders)
        order_ids = [order.id for order in orders]
        existing_order_ids = set(
            db.scalars(
                select(OrderOperationalSnapshot.order_id).where(
                    OrderOperationalSnapshot.tenant_id == current.tenant_id,
                    OrderOperationalSnapshot.service_date == service_date,
                    OrderOperationalSnapshot.rule_version == _OPERATIONAL_RULE_VERSION,
                    OrderOperationalSnapshot.evaluation_ts >= bucket_start,
                    OrderOperationalSnapshot.evaluation_ts < bucket_end,
                    OrderOperationalSnapshot.order_id.in_(order_ids),
                )
            )
        )

        for order in orders:
            if order.id in existing_order_ids:
                skipped_existing += 1
                continue

            evaluation, resolved_timezone, profile = _evaluate_order_operational(
                order,
                tenant=tenant,
                context=context,
            )
            state = "restricted" if evaluation.reason_code else "eligible"
            evidence = _build_snapshot_evidence(
                order,
                profile=profile,
                timezone=resolved_timezone,
            )
            snapshot = OrderOperationalSnapshot(
                tenant_id=current.tenant_id,
                order_id=order.id,
                service_date=order.service_date,
                operational_state=state,
                operational_reason=evaluation.reason_code,
                evaluation_ts=run_ts,
                timezone_used=evaluation.timezone_used,
                rule_version=evaluation.rule_version,
                evidence_json=evidence,
            )
            db.add(snapshot)
            db.flush()
            generated_snapshot_ids.append(snapshot.id)

    write_audit(
        db,
        tenant_id=current.tenant_id,
        entity_type=EntityType.tenant,
        entity_id=current.tenant_id,
        action="operational_snapshot_generated",
        actor_id=current.id,
        metadata={
            "service_date": service_date.isoformat(),
            "rule_version": _OPERATIONAL_RULE_VERSION,
            "evaluation_ts_bucket_start": bucket_start.isoformat(),
            "evaluation_ts_bucket_end": bucket_end.isoformat(),
            "considered_orders": considered_orders,
            "generated_snapshots": len(generated_snapshot_ids),
            "skipped_existing": skipped_existing,
            "generated_snapshot_ids": [str(item) for item in generated_snapshot_ids],
        },
    )

    db.commit()
    return OperationalSnapshotRunResponse(
        tenant_id=current.tenant_id,
        service_date=service_date,
        rule_version=_OPERATIONAL_RULE_VERSION,
        evaluation_ts_bucket=bucket_start,
        considered_orders=considered_orders,
        generated_snapshots=len(generated_snapshot_ids),
        skipped_existing=skipped_existing,
        generated_snapshot_ids=generated_snapshot_ids,
    )


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.office, UserRole.logistics, UserRole.admin)),
) -> OrderOut:
    tenant = db.scalar(select(Tenant).where(Tenant.id == current.tenant_id))
    if not tenant:
        raise not_found("TENANT_NOT_FOUND", "Tenant no encontrado")

    order = db.scalar(select(Order).where(Order.id == order_id, Order.tenant_id == current.tenant_id))
    if not order:
        raise not_found("ORDER_NOT_FOUND", "Pedido no encontrado")

    lines = list(db.scalars(select(OrderLine).where(OrderLine.order_id == order.id, OrderLine.tenant_id == current.tenant_id)))
    operational_by_order = _build_operational_evaluation_map(db, tenant=tenant, orders=[order])
    operational = operational_by_order.get(order.id) or _default_operational_evaluation()
    return _serialize_order(order, lines, operational=operational)


@router.patch("/orders/{order_id}/weight", response_model=OrderOut)
def update_order_weight(
    order_id: uuid.UUID,
    payload: OrderWeightUpdateRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.logistics, UserRole.admin)),
) -> OrderOut:
    tenant = db.scalar(select(Tenant).where(Tenant.id == current.tenant_id))
    if not tenant:
        raise not_found("TENANT_NOT_FOUND", "Tenant no encontrado")

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
    operational_by_order = _build_operational_evaluation_map(db, tenant=tenant, orders=[order])
    operational = operational_by_order.get(order.id) or _default_operational_evaluation()
    return _serialize_order(order, lines, operational=operational)
