import csv
import io
import uuid
from datetime import date
from math import ceil

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentUser, require_roles
from app.errors import unprocessable
from app.models import (
    Customer,
    Order,
    Plan,
    PlanOrder,
    Tenant,
    UserRole,
    Zone,
)
from app.routers.orders import _build_operational_evaluation_map
from app.schemas import OperationalDatasetExportResponse, OperationalDatasetItemOut


router = APIRouter(prefix="/exports", tags=["Exports"])

_VALID_EXPORT_FORMATS = {"json", "csv"}


def _anonymized(prefix: str, entity_id: uuid.UUID) -> str:
    return f"{prefix}-{str(entity_id)[:8]}"


@router.get("/operational-dataset", response_model=OperationalDatasetExportResponse)
def export_operational_dataset(
    date_from: date,
    date_to: date,
    zone_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 100,
    anonymize: bool = False,
    format: str = Query(default="json"),
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.logistics, UserRole.admin)),
) -> OperationalDatasetExportResponse | Response:
    if date_from > date_to:
        raise unprocessable("INVALID_EXPORT_FILTER", "date_from no puede ser mayor que date_to")
    if page < 1:
        raise unprocessable("INVALID_EXPORT_FILTER", "page debe ser mayor o igual a 1")
    if page_size < 1 or page_size > 500:
        raise unprocessable("INVALID_EXPORT_FILTER", "page_size debe estar entre 1 y 500")
    if format not in _VALID_EXPORT_FORMATS:
        raise unprocessable("INVALID_EXPORT_FILTER", "format debe ser json o csv")

    tenant = db.scalar(select(Tenant).where(Tenant.id == current.tenant_id))
    if tenant is None:
        raise unprocessable("INVALID_EXPORT_SCOPE", "Tenant no encontrado para export")

    filters = [
        Order.tenant_id == current.tenant_id,
        Order.service_date >= date_from,
        Order.service_date <= date_to,
    ]
    if zone_id is not None:
        filters.append(Order.zone_id == zone_id)

    total = db.scalar(select(func.count()).select_from(Order).where(*filters)) or 0
    total_pages = ceil(total / page_size) if total > 0 else 0
    offset = (page - 1) * page_size

    row_query = (
        select(
            Order,
            Customer.name.label("customer_name"),
            Zone.name.label("zone_name"),
            PlanOrder.plan_id.label("plan_id"),
            PlanOrder.inclusion_type.label("plan_inclusion_type"),
            Plan.status.label("plan_status"),
            Plan.locked_at.label("plan_locked_at"),
            Plan.vehicle_id.label("plan_vehicle_id"),
        )
        .join(Customer, and_(Customer.id == Order.customer_id, Customer.tenant_id == Order.tenant_id))
        .join(Zone, and_(Zone.id == Order.zone_id, Zone.tenant_id == Order.tenant_id))
        .outerjoin(PlanOrder, and_(PlanOrder.order_id == Order.id, PlanOrder.tenant_id == Order.tenant_id))
        .outerjoin(Plan, and_(Plan.id == PlanOrder.plan_id, Plan.tenant_id == PlanOrder.tenant_id))
        .where(*filters)
        .order_by(Order.service_date.asc(), Order.created_at.asc(), Order.id.asc())
        .offset(offset)
        .limit(page_size)
    )
    rows = db.execute(row_query).all()

    orders = [row.Order for row in rows]
    operational_by_order = _build_operational_evaluation_map(db, tenant=tenant, orders=orders)

    plan_ids = {row.plan_id for row in rows if row.plan_id is not None}
    plan_metrics: dict[uuid.UUID, dict] = {}
    if plan_ids:
        metrics_rows = db.execute(
            select(
                PlanOrder.plan_id.label("plan_id"),
                func.count(PlanOrder.order_id).label("orders_total"),
                func.count(Order.id).filter(Order.total_weight_kg.is_not(None)).label("orders_with_weight"),
                (
                    func.count(PlanOrder.order_id) - func.count(Order.id).filter(Order.total_weight_kg.is_not(None))
                ).label("orders_missing_weight"),
                func.sum(Order.total_weight_kg).label("total_weight_kg"),
            )
            .join(Order, and_(Order.id == PlanOrder.order_id, Order.tenant_id == PlanOrder.tenant_id))
            .where(
                PlanOrder.tenant_id == current.tenant_id,
                PlanOrder.plan_id.in_(plan_ids),
            )
            .group_by(PlanOrder.plan_id)
        ).all()
        plan_metrics = {
            row.plan_id: {
                "total": int(row.orders_total),
                "with_weight": int(row.orders_with_weight),
                "missing_weight": int(row.orders_missing_weight),
                "total_weight_kg": row.total_weight_kg,
            }
            for row in metrics_rows
        }

    items: list[OperationalDatasetItemOut] = []
    for row in rows:
        operational = operational_by_order.get(row.Order.id)
        if operational is None:
            continue
        metrics = plan_metrics.get(row.plan_id)

        external_ref = row.Order.external_ref
        customer_name = row.customer_name
        zone_name = row.zone_name
        if anonymize:
            external_ref = _anonymized("order", row.Order.id)
            customer_name = _anonymized("customer", row.Order.customer_id)
            zone_name = _anonymized("zone", row.Order.zone_id)

        items.append(
            OperationalDatasetItemOut(
                order_id=row.Order.id,
                external_ref=external_ref,
                service_date=row.Order.service_date,
                created_at=row.Order.created_at,
                order_status=row.Order.status.value,
                source_channel=row.Order.source_channel.value,
                intake_type=row.Order.intake_type.value,
                is_late=row.Order.is_late,
                customer_id=row.Order.customer_id,
                customer_name=customer_name,
                zone_id=row.Order.zone_id,
                zone_name=zone_name,
                operational_state="restricted" if operational.reason_code else "eligible",
                operational_reason=operational.reason_code,
                operational_reason_category=operational.reason_category,
                operational_severity=operational.severity,
                operational_catalog_status=operational.catalog_status,
                rule_version=operational.rule_version,
                timezone_used=operational.timezone_used,
                timezone_source=operational.timezone_source,
                planned=row.plan_id is not None,
                plan_id=row.plan_id,
                plan_status=row.plan_status.value if row.plan_status is not None else None,
                plan_inclusion_type=row.plan_inclusion_type.value if row.plan_inclusion_type is not None else None,
                plan_locked_at=row.plan_locked_at,
                plan_vehicle_id=row.plan_vehicle_id,
                total_weight_kg=row.Order.total_weight_kg,
                plan_total_weight_kg=metrics["total_weight_kg"] if metrics else None,
                plan_orders_total=metrics["total"] if metrics else None,
                plan_orders_with_weight=metrics["with_weight"] if metrics else None,
                plan_orders_missing_weight=metrics["missing_weight"] if metrics else None,
            )
        )

    if format == "csv":
        csv_buffer = io.StringIO()
        fieldnames = list(OperationalDatasetItemOut.model_fields.keys())
        writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            writer.writerow(item.model_dump(mode="json"))
        return Response(
            content=csv_buffer.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="operational-dataset.csv"',
                "X-Total-Count": str(total),
                "X-Page": str(page),
                "X-Page-Size": str(page_size),
                "X-Total-Pages": str(total_pages),
            },
        )

    return OperationalDatasetExportResponse(
        date_from=date_from,
        date_to=date_to,
        zone_id=zone_id,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
        anonymized=anonymize,
        items=items,
    )
