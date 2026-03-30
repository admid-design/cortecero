from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models import (
    Customer,
    InclusionType,
    Order,
    OrderIntakeType,
    OrderStatus,
    Plan,
    PlanOrder,
    PlanStatus,
    SourceChannel,
    Tenant,
    User,
    UserRole,
    Vehicle,
    Zone,
)
from app.security import hash_password
from tests.helpers import auth_headers, login_as


def _seed_plan_with_vehicle_and_weight(
    db_session,
    *,
    tenant_id,
    actor_id,
    service_date: date,
    capacity_kg: float | None,
    total_weight_kg: float | None,
    suffix: str,
    vehicle_active: bool = True,
) -> tuple[Zone, Plan]:
    now = datetime.now(UTC)
    zone = Zone(
        tenant_id=tenant_id,
        name=f"Zona Alert {suffix}",
        default_cutoff_time=now.time().replace(microsecond=0),
        timezone="Europe/Madrid",
        active=True,
        created_at=now,
    )
    db_session.add(zone)
    db_session.flush()

    customer = Customer(
        tenant_id=tenant_id,
        zone_id=zone.id,
        name=f"Cliente Alert {suffix}",
        priority=0,
        cutoff_override_time=None,
        active=True,
        created_at=now,
    )
    db_session.add(customer)
    db_session.flush()

    vehicle = Vehicle(
        tenant_id=tenant_id,
        code=f"VH-{suffix}",
        name=f"Vehiculo {suffix}",
        capacity_kg=capacity_kg,
        active=vehicle_active,
        created_at=now,
    )
    db_session.add(vehicle)
    db_session.flush()

    plan = Plan(
        tenant_id=tenant_id,
        service_date=service_date,
        zone_id=zone.id,
        status=PlanStatus.open,
        version=1,
        vehicle_id=vehicle.id,
        locked_at=None,
        locked_by=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(plan)
    db_session.flush()

    order = Order(
        tenant_id=tenant_id,
        customer_id=customer.id,
        zone_id=zone.id,
        external_ref=f"ALERT-{suffix}",
        requested_date=service_date,
        service_date=service_date,
        created_at=now,
        status=OrderStatus.planned,
        is_late=False,
        lateness_reason=None,
        effective_cutoff_at=now,
        source_channel=SourceChannel.office,
        intake_type=OrderIntakeType.new_order,
        total_weight_kg=total_weight_kg,
        ingested_at=now,
        updated_at=now,
    )
    db_session.add(order)
    db_session.flush()

    db_session.add(
        PlanOrder(
            tenant_id=tenant_id,
            plan_id=plan.id,
            order_id=order.id,
            inclusion_type=InclusionType.normal,
            added_at=now,
            added_by=actor_id,
        )
    )
    db_session.flush()
    return zone, plan


def test_capacity_alerts_are_derived_and_filterable(client, db_session):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )
    tenant = db_session.scalar(select(Tenant).where(Tenant.slug == "demo-cortecero"))
    assert tenant is not None
    actor = db_session.scalar(
        select(User).where(User.tenant_id == tenant.id, User.role == UserRole.logistics, User.is_active.is_(True))
    )
    assert actor is not None

    service_date = date(2099, 12, 27)
    zone_over, plan_over = _seed_plan_with_vehicle_and_weight(
        db_session,
        tenant_id=tenant.id,
        actor_id=actor.id,
        service_date=service_date,
        capacity_kg=100,
        total_weight_kg=120,
        suffix=f"OVER-{uuid4()}",
    )
    _, plan_near = _seed_plan_with_vehicle_and_weight(
        db_session,
        tenant_id=tenant.id,
        actor_id=actor.id,
        service_date=service_date,
        capacity_kg=100,
        total_weight_kg=90,
        suffix=f"NEAR-{uuid4()}",
    )
    _zone_ok, _plan_ok = _seed_plan_with_vehicle_and_weight(
        db_session,
        tenant_id=tenant.id,
        actor_id=actor.id,
        service_date=service_date,
        capacity_kg=100,
        total_weight_kg=70,
        suffix=f"OK-{uuid4()}",
    )
    _zone_no_cap, _plan_no_cap = _seed_plan_with_vehicle_and_weight(
        db_session,
        tenant_id=tenant.id,
        actor_id=actor.id,
        service_date=service_date,
        capacity_kg=None,
        total_weight_kg=130,
        suffix=f"NOCAP-{uuid4()}",
    )
    db_session.commit()

    res = client.get(
        "/plans/capacity-alerts",
        params={"service_date": service_date.isoformat()},
        headers=auth_headers(token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["near_threshold_ratio"] == pytest.approx(0.9)
    assert body["total"] == 2
    assert [item["alert_level"] for item in body["items"]] == ["OVER_CAPACITY", "NEAR_CAPACITY"]
    assert body["items"][0]["plan_id"] == str(plan_over.id)
    assert body["items"][1]["plan_id"] == str(plan_near.id)
    assert body["items"][0]["usage_ratio"] == pytest.approx(1.2)
    assert body["items"][1]["usage_ratio"] == pytest.approx(0.9)

    near_only_res = client.get(
        "/plans/capacity-alerts",
        params={"service_date": service_date.isoformat(), "level": "NEAR_CAPACITY"},
        headers=auth_headers(token),
    )
    assert near_only_res.status_code == 200, near_only_res.text
    near_items = near_only_res.json()["items"]
    assert len(near_items) == 1
    assert near_items[0]["plan_id"] == str(plan_near.id)

    zone_res = client.get(
        "/plans/capacity-alerts",
        params={"service_date": service_date.isoformat(), "zone_id": str(zone_over.id)},
        headers=auth_headers(token),
    )
    assert zone_res.status_code == 200, zone_res.text
    zone_items = zone_res.json()["items"]
    assert len(zone_items) == 1
    assert zone_items[0]["plan_id"] == str(plan_over.id)


def test_capacity_alerts_are_tenant_scoped(client, db_session):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )
    demo_tenant = db_session.scalar(select(Tenant).where(Tenant.slug == "demo-cortecero"))
    assert demo_tenant is not None
    demo_actor = db_session.scalar(
        select(User).where(User.tenant_id == demo_tenant.id, User.role == UserRole.logistics, User.is_active.is_(True))
    )
    assert demo_actor is not None

    service_date = date(2099, 12, 28)
    _zone_demo, plan_demo = _seed_plan_with_vehicle_and_weight(
        db_session,
        tenant_id=demo_tenant.id,
        actor_id=demo_actor.id,
        service_date=service_date,
        capacity_kg=100,
        total_weight_kg=120,
        suffix=f"DEMO-{uuid4()}",
    )

    now = datetime.now(UTC)
    tenant_b = Tenant(
        name="Tenant B Capacity Alerts",
        slug=f"tenant-b-capacity-{uuid4()}",
        default_cutoff_time=now.time().replace(microsecond=0),
        default_timezone="Europe/Madrid",
        auto_lock_enabled=False,
        created_at=now,
    )
    db_session.add(tenant_b)
    db_session.flush()

    actor_b = User(
        tenant_id=tenant_b.id,
        email=f"logistics-{uuid4()}@tenantb.cortecero.app",
        full_name="Tenant B Logistics",
        password_hash=hash_password("tenantb123"),
        role=UserRole.logistics,
        is_active=True,
        created_at=now,
    )
    db_session.add(actor_b)
    db_session.flush()

    _zone_b, plan_b = _seed_plan_with_vehicle_and_weight(
        db_session,
        tenant_id=tenant_b.id,
        actor_id=actor_b.id,
        service_date=service_date,
        capacity_kg=100,
        total_weight_kg=140,
        suffix=f"TB-{uuid4()}",
    )
    db_session.commit()

    res = client.get(
        "/plans/capacity-alerts",
        params={"service_date": service_date.isoformat()},
        headers=auth_headers(token),
    )
    assert res.status_code == 200, res.text
    plan_ids = {item["plan_id"] for item in res.json()["items"]}
    assert str(plan_demo.id) in plan_ids
    assert str(plan_b.id) not in plan_ids


def test_capacity_alerts_invalid_level_rejected(client):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )
    res = client.get(
        "/plans/capacity-alerts",
        params={"service_date": "2099-12-29", "level": "INVALID"},
        headers=auth_headers(token),
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "INVALID_FILTER"


def test_capacity_alerts_include_inactive_assigned_vehicle(client, db_session):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )
    tenant = db_session.scalar(select(Tenant).where(Tenant.slug == "demo-cortecero"))
    assert tenant is not None
    actor = db_session.scalar(
        select(User).where(User.tenant_id == tenant.id, User.role == UserRole.logistics, User.is_active.is_(True))
    )
    assert actor is not None

    service_date = date(2099, 12, 30)
    _zone, plan = _seed_plan_with_vehicle_and_weight(
        db_session,
        tenant_id=tenant.id,
        actor_id=actor.id,
        service_date=service_date,
        capacity_kg=100,
        total_weight_kg=130,
        suffix=f"INACTIVE-{uuid4()}",
        vehicle_active=False,
    )
    db_session.commit()

    res = client.get(
        "/plans/capacity-alerts",
        params={"service_date": service_date.isoformat()},
        headers=auth_headers(token),
    )
    assert res.status_code == 200, res.text
    plan_ids = {item["plan_id"] for item in res.json()["items"]}
    assert str(plan.id) in plan_ids
