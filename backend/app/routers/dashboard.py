import uuid
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentUser, require_roles
from app.errors import unprocessable
from app.models import ExceptionItem, ExceptionStatus, Order, Plan, PlanStatus, SourceChannel, UserRole
from app.schemas import DashboardSourceMetricsItem, DashboardSourceMetricsResponse, DashboardSummaryResponse


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

_SOURCE_CHANNEL_ORDER: tuple[SourceChannel, ...] = (
    SourceChannel.sales,
    SourceChannel.office,
    SourceChannel.direct_customer,
    SourceChannel.hotel_direct,
    SourceChannel.other,
)


@router.get("/daily-summary", response_model=DashboardSummaryResponse)
def daily_summary(
    service_date: date,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.office, UserRole.logistics, UserRole.admin)),
) -> DashboardSummaryResponse:
    total_orders = db.scalar(
        select(func.count()).select_from(Order).where(Order.tenant_id == current.tenant_id, Order.service_date == service_date)
    )
    late_orders = db.scalar(
        select(func.count())
        .select_from(Order)
        .where(Order.tenant_id == current.tenant_id, Order.service_date == service_date, Order.is_late.is_(True))
    )

    plans_open = db.scalar(
        select(func.count())
        .select_from(Plan)
        .where(Plan.tenant_id == current.tenant_id, Plan.service_date == service_date, Plan.status == PlanStatus.open)
    )
    plans_locked = db.scalar(
        select(func.count())
        .select_from(Plan)
        .where(Plan.tenant_id == current.tenant_id, Plan.service_date == service_date, Plan.status == PlanStatus.locked)
    )

    pending = db.scalar(
        select(func.count())
        .select_from(ExceptionItem)
        .join(Order, Order.id == ExceptionItem.order_id)
        .where(
            ExceptionItem.tenant_id == current.tenant_id,
            Order.service_date == service_date,
            ExceptionItem.status == ExceptionStatus.pending,
        )
    )
    approved = db.scalar(
        select(func.count())
        .select_from(ExceptionItem)
        .join(Order, Order.id == ExceptionItem.order_id)
        .where(
            ExceptionItem.tenant_id == current.tenant_id,
            Order.service_date == service_date,
            ExceptionItem.status == ExceptionStatus.approved,
        )
    )
    rejected = db.scalar(
        select(func.count())
        .select_from(ExceptionItem)
        .join(Order, Order.id == ExceptionItem.order_id)
        .where(
            ExceptionItem.tenant_id == current.tenant_id,
            Order.service_date == service_date,
            ExceptionItem.status == ExceptionStatus.rejected,
        )
    )

    return DashboardSummaryResponse(
        service_date=service_date,
        total_orders=total_orders or 0,
        late_orders=late_orders or 0,
        plans_open=plans_open or 0,
        plans_locked=plans_locked or 0,
        pending_exceptions=pending or 0,
        approved_exceptions=approved or 0,
        rejected_exceptions=rejected or 0,
    )


@router.get("/source-metrics", response_model=DashboardSourceMetricsResponse)
def source_metrics(
    date_from: date,
    date_to: date,
    zone_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.office, UserRole.logistics, UserRole.admin)),
) -> DashboardSourceMetricsResponse:
    if date_from > date_to:
        raise unprocessable("SOURCE_METRICS_RANGE_INVALID", "date_from no puede ser mayor que date_to")

    order_filters = [
        Order.tenant_id == current.tenant_id,
        Order.service_date >= date_from,
        Order.service_date <= date_to,
    ]
    if zone_id:
        order_filters.append(Order.zone_id == zone_id)

    order_rows = db.execute(
        select(
            Order.source_channel,
            func.count(Order.id).label("total_orders"),
            func.sum(case((Order.is_late.is_(True), 1), else_=0)).label("late_orders"),
        )
        .where(*order_filters)
        .group_by(Order.source_channel)
    ).all()

    exception_filters = [
        ExceptionItem.tenant_id == current.tenant_id,
        Order.tenant_id == current.tenant_id,
        Order.service_date >= date_from,
        Order.service_date <= date_to,
        ExceptionItem.status.in_((ExceptionStatus.approved, ExceptionStatus.rejected)),
    ]
    if zone_id:
        exception_filters.append(Order.zone_id == zone_id)

    exception_rows = db.execute(
        select(
            Order.source_channel,
            ExceptionItem.status,
            func.count(ExceptionItem.id).label("count"),
        )
        .select_from(ExceptionItem)
        .join(
            Order,
            and_(
                Order.id == ExceptionItem.order_id,
                Order.tenant_id == ExceptionItem.tenant_id,
            ),
        )
        .where(*exception_filters)
        .group_by(Order.source_channel, ExceptionItem.status)
    ).all()

    by_channel_totals: dict[SourceChannel, tuple[int, int]] = {
        row.source_channel: (int(row.total_orders or 0), int(row.late_orders or 0)) for row in order_rows
    }
    by_channel_exceptions: dict[SourceChannel, dict[ExceptionStatus, int]] = {}
    for row in exception_rows:
        source_channel = row.source_channel
        status = row.status
        by_channel_exceptions.setdefault(source_channel, {})[status] = int(row.count or 0)

    items: list[DashboardSourceMetricsItem] = []
    for channel in _SOURCE_CHANNEL_ORDER:
        total_orders, late_orders = by_channel_totals.get(channel, (0, 0))
        approved_exceptions = by_channel_exceptions.get(channel, {}).get(ExceptionStatus.approved, 0)
        rejected_exceptions = by_channel_exceptions.get(channel, {}).get(ExceptionStatus.rejected, 0)
        late_rate = float(late_orders / total_orders) if total_orders > 0 else 0.0

        items.append(
            DashboardSourceMetricsItem(
                source_channel=channel.value,
                total_orders=total_orders,
                late_orders=late_orders,
                late_rate=late_rate,
                approved_exceptions=approved_exceptions,
                rejected_exceptions=rejected_exceptions,
            )
        )

    return DashboardSourceMetricsResponse(
        date_from=date_from,
        date_to=date_to,
        zone_id=zone_id,
        items=items,
    )
