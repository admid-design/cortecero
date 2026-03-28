from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentUser, require_roles
from app.models import ExceptionItem, ExceptionStatus, Order, Plan, PlanStatus, UserRole
from app.schemas import DashboardSummaryResponse


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


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
