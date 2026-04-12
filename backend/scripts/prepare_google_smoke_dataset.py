#!/usr/bin/env python3
"""
DEMO-DATA-001 — Dataset mínimo geo-ready para GOOGLE-SMOKE-001.

Crea/actualiza 2 pedidos sintéticos en estado `planned` para un mismo
`service_date + zone_id` sobre un plan `locked`, usando clientes con lat/lng.

No usa datos reales y no requiere SQL manual fuera de repo.
"""

from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

# Permite ejecutar este script desde repo root o desde backend/.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db import SessionLocal
from app.models import (
    Customer,
    Order,
    OrderIntakeType,
    OrderStatus,
    Plan,
    PlanStatus,
    SourceChannel,
    Tenant,
)

TENANT_SLUG = "demo-cortecero"
EXTERNAL_REFS = ("SMOKE-GEO-001-A", "SMOKE-GEO-001-B")


def _bail(msg: str) -> None:
    print(f"[FATAL] {msg}")
    raise SystemExit(1)


def _pick_locked_plan_with_geo(db) -> tuple[Plan, list[Customer]]:
    plans = list(
        db.scalars(
            select(Plan)
            .join(Tenant, Tenant.id == Plan.tenant_id)
            .where(Tenant.slug == TENANT_SLUG, Plan.status == PlanStatus.locked)
            .order_by(Plan.service_date, Plan.id)
        )
    )
    if not plans:
        _bail(f"No hay planes locked para tenant={TENANT_SLUG}")

    for plan in plans:
        customers = list(
            db.scalars(
                select(Customer)
                .where(
                    Customer.tenant_id == plan.tenant_id,
                    Customer.zone_id == plan.zone_id,
                    Customer.active.is_(True),
                    Customer.lat.is_not(None),
                    Customer.lng.is_not(None),
                )
                .order_by(Customer.created_at, Customer.id)
                .limit(2)
            )
        )
        if len(customers) >= 2:
            return plan, customers[:2]

    _bail("No existe plan locked con al menos 2 clientes geo-ready en la misma zona")
    raise AssertionError("unreachable")


def main() -> None:
    now = datetime.now(UTC)
    created = 0
    updated = 0

    with SessionLocal() as db:
        plan, customers = _pick_locked_plan_with_geo(db)
        tenant_id = plan.tenant_id

        for idx, customer in enumerate(customers):
            external_ref = EXTERNAL_REFS[idx]
            existing = db.scalar(
                select(Order).where(
                    Order.tenant_id == tenant_id,
                    Order.external_ref == external_ref,
                    Order.service_date == plan.service_date,
                )
            )

            if existing:
                existing.customer_id = customer.id
                existing.zone_id = plan.zone_id
                existing.requested_date = plan.service_date
                existing.status = OrderStatus.planned
                existing.is_late = False
                existing.lateness_reason = None
                existing.effective_cutoff_at = now + timedelta(hours=1)
                existing.source_channel = SourceChannel.office
                existing.total_weight_kg = 10.0 + idx
                existing.updated_at = now
                updated += 1
                continue

            order = Order(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                customer_id=customer.id,
                zone_id=plan.zone_id,
                external_ref=external_ref,
                requested_date=plan.service_date,
                service_date=plan.service_date,
                created_at=now - timedelta(minutes=10 + idx),
                status=OrderStatus.planned,
                is_late=False,
                lateness_reason=None,
                effective_cutoff_at=now + timedelta(hours=1),
                source_channel=SourceChannel.office,
                intake_type=OrderIntakeType.new_order if idx == 0 else OrderIntakeType.same_customer_addon,
                ingested_at=now,
                updated_at=now,
                total_weight_kg=10.0 + idx,
            )
            db.add(order)
            created += 1

        db.commit()

        print("[OK] Demo dataset geo-ready preparado")
        print(f"  tenant_slug:   {TENANT_SLUG}")
        print(f"  plan_id:       {plan.id}")
        print(f"  service_date:  {plan.service_date}")
        print(f"  zone_id:       {plan.zone_id}")
        print(f"  refs:          {', '.join(EXTERNAL_REFS)}")
        print(f"  created:       {created}")
        print(f"  updated:       {updated}")


if __name__ == "__main__":
    main()
