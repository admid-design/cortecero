import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.db import SessionLocal
from app.domain import build_effective_cutoff_at, compute_lateness, initial_order_status
from app.models import (
    Customer,
    EntityType,
    ExceptionItem,
    ExceptionStatus,
    ExceptionType,
    Order,
    OrderLine,
    Plan,
    PlanOrder,
    PlanStatus,
    SourceChannel,
    Tenant,
    User,
    UserRole,
    Zone,
    InclusionType,
    AuditLog,
)
from app.security import hash_password


def now_utc() -> datetime:
    return datetime.now(UTC)


def seed() -> None:
    db = SessionLocal()
    try:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == "demo-cortecero"))
        if not tenant:
            tenant = Tenant(
                id=uuid.uuid4(),
                name="CorteCero Demo",
                slug="demo-cortecero",
                default_cutoff_time=datetime.strptime("10:00", "%H:%M").time(),
                default_timezone="Europe/Madrid",
                auto_lock_enabled=False,
                created_at=now_utc(),
            )
            db.add(tenant)
            db.flush()

        users_by_role = {}
        for role, email in [
            (UserRole.office, "office@demo.local"),
            (UserRole.logistics, "logistics@demo.local"),
            (UserRole.admin, "admin@demo.local"),
        ]:
            user = db.scalar(select(User).where(User.tenant_id == tenant.id, User.email == email))
            if not user:
                user = User(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    email=email,
                    full_name=role.value.title(),
                    password_hash=hash_password(f"{role.value}123"),
                    role=role,
                    is_active=True,
                    created_at=now_utc(),
                )
                db.add(user)
                db.flush()
            users_by_role[role.value] = user

        zone_a = db.scalar(select(Zone).where(Zone.tenant_id == tenant.id, Zone.name == "Centro"))
        if not zone_a:
            zone_a = Zone(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                name="Centro",
                default_cutoff_time=datetime.strptime("10:00", "%H:%M").time(),
                timezone="Europe/Madrid",
                active=True,
                created_at=now_utc(),
            )
            db.add(zone_a)
            db.flush()

        zone_b = db.scalar(select(Zone).where(Zone.tenant_id == tenant.id, Zone.name == "Costa"))
        if not zone_b:
            zone_b = Zone(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                name="Costa",
                default_cutoff_time=datetime.strptime("09:30", "%H:%M").time(),
                timezone="Europe/Madrid",
                active=True,
                created_at=now_utc(),
            )
            db.add(zone_b)
            db.flush()

        customers = []
        for idx in range(10):
            zone = zone_a if idx < 5 else zone_b
            name = f"Cliente {idx + 1:02d}"
            customer = db.scalar(select(Customer).where(Customer.tenant_id == tenant.id, Customer.name == name))
            if not customer:
                customer = Customer(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    zone_id=zone.id,
                    name=name,
                    priority=0,
                    cutoff_override_time=None,
                    active=True,
                    created_at=now_utc(),
                )
                db.add(customer)
                db.flush()
            customers.append(customer)

        service_date = (datetime.now(ZoneInfo("Europe/Madrid")) + timedelta(days=1)).date()

        existing_orders = list(db.scalars(select(Order).where(Order.tenant_id == tenant.id, Order.service_date == service_date)))
        if len(existing_orders) < 20:
            for idx in range(20):
                customer = customers[idx % len(customers)]
                zone = zone_a if (idx % 2 == 0) else zone_b
                external_ref = f"DEMO-{service_date.strftime('%Y%m%d')}-{idx + 1:03d}"

                present = db.scalar(
                    select(Order).where(
                        Order.tenant_id == tenant.id,
                        Order.external_ref == external_ref,
                        Order.service_date == service_date,
                    )
                )
                if present:
                    continue

                cutoff_time = customer.cutoff_override_time or zone.default_cutoff_time or tenant.default_cutoff_time
                effective_cutoff = build_effective_cutoff_at(service_date, cutoff_time, zone.timezone)
                created_at = effective_cutoff - timedelta(hours=2) if idx < 12 else effective_cutoff + timedelta(hours=1)
                is_late, reason = compute_lateness(created_at, effective_cutoff)

                order = Order(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    customer_id=customer.id,
                    zone_id=zone.id,
                    external_ref=external_ref,
                    requested_date=service_date,
                    service_date=service_date,
                    created_at=created_at,
                    status=initial_order_status(is_late),
                    is_late=is_late,
                    lateness_reason=reason,
                    effective_cutoff_at=effective_cutoff,
                    source_channel=SourceChannel.office,
                    ingested_at=now_utc(),
                    updated_at=now_utc(),
                )
                db.add(order)
                db.flush()

                db.add(
                    OrderLine(
                        id=uuid.uuid4(),
                        tenant_id=tenant.id,
                        order_id=order.id,
                        sku=f"SKU-{idx + 1:03d}",
                        qty=1,
                        weight_kg=2.5,
                        volume_m3=0.02,
                        created_at=now_utc(),
                    )
                )

        open_plan = db.scalar(
            select(Plan).where(
                Plan.tenant_id == tenant.id,
                Plan.service_date == service_date,
                Plan.zone_id == zone_a.id,
            )
        )
        if not open_plan:
            open_plan = Plan(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                service_date=service_date,
                zone_id=zone_a.id,
                status=PlanStatus.open,
                version=1,
                locked_at=None,
                locked_by=None,
                created_at=now_utc(),
                updated_at=now_utc(),
            )
            db.add(open_plan)
            db.flush()

        locked_plan = db.scalar(
            select(Plan).where(
                Plan.tenant_id == tenant.id,
                Plan.service_date == service_date,
                Plan.zone_id == zone_b.id,
            )
        )
        if not locked_plan:
            locked_plan = Plan(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                service_date=service_date,
                zone_id=zone_b.id,
                status=PlanStatus.locked,
                version=2,
                locked_at=now_utc(),
                locked_by=users_by_role["logistics"].id,
                created_at=now_utc(),
                updated_at=now_utc(),
            )
            db.add(locked_plan)
            db.flush()

        all_orders = list(db.scalars(select(Order).where(Order.tenant_id == tenant.id, Order.service_date == service_date)))
        by_external = {o.external_ref: o for o in all_orders}

        planned_candidate = by_external.get(f"DEMO-{service_date.strftime('%Y%m%d')}-001")
        if planned_candidate:
            exists_plan_order = db.scalar(
                select(PlanOrder).where(PlanOrder.tenant_id == tenant.id, PlanOrder.order_id == planned_candidate.id)
            )
            if not exists_plan_order:
                db.add(
                    PlanOrder(
                        id=uuid.uuid4(),
                        tenant_id=tenant.id,
                        plan_id=open_plan.id,
                        order_id=planned_candidate.id,
                        inclusion_type=InclusionType.normal,
                        added_at=now_utc(),
                        added_by=users_by_role["logistics"].id,
                    )
                )
                planned_candidate.status = OrderStatus.planned

        pending_order = by_external.get(f"DEMO-{service_date.strftime('%Y%m%d')}-019")
        approved_order = by_external.get(f"DEMO-{service_date.strftime('%Y%m%d')}-020")
        rejected_order = by_external.get(f"DEMO-{service_date.strftime('%Y%m%d')}-018")

        for order_obj, status in [
            (pending_order, ExceptionStatus.pending),
            (approved_order, ExceptionStatus.approved),
            (rejected_order, ExceptionStatus.rejected),
        ]:
            if not order_obj:
                continue
            has_exception = db.scalar(select(ExceptionItem).where(ExceptionItem.tenant_id == tenant.id, ExceptionItem.order_id == order_obj.id))
            if has_exception:
                continue

            resolved_by = None if status == ExceptionStatus.pending else users_by_role["logistics"].id
            resolved_at = None if status == ExceptionStatus.pending else now_utc()

            db.add(
                ExceptionItem(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    order_id=order_obj.id,
                    type=ExceptionType.late_order,
                    status=status,
                    requested_by=users_by_role["office"].id,
                    resolved_by=resolved_by,
                    resolved_at=resolved_at,
                    note=f"Seed {status.value}",
                    created_at=now_utc(),
                )
            )

            if status == ExceptionStatus.rejected:
                order_obj.status = OrderStatus.exception_rejected

        db.add(
            AuditLog(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                entity_type=EntityType.plan,
                entity_id=open_plan.id,
                action="seed.generated",
                actor_id=users_by_role["admin"].id,
                ts=now_utc(),
                request_id="seed",
                metadata_json={"service_date": str(service_date)},
            )
        )

        db.commit()
        print("Seed OK")
        print("Users:")
        print(" - office@demo.local / office123")
        print(" - logistics@demo.local / logistics123")
        print(" - admin@demo.local / admin123")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
