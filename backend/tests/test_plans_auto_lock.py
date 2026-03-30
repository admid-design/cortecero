from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.models import AuditLog, Plan, PlanStatus, Tenant, User, UserRole, Zone
from app.security import hash_password
from tests.helpers import auth_headers, login_as


def _tenant_by_slug(db_session, slug: str) -> Tenant:
    tenant = db_session.scalar(select(Tenant).where(Tenant.slug == slug))
    assert tenant is not None
    return tenant


def _set_autolock_window_reached(db_session, tenant: Tenant) -> None:
    tenant_now = datetime.now(ZoneInfo(tenant.default_timezone))
    tenant.auto_lock_enabled = True
    tenant.default_cutoff_time = (tenant_now - timedelta(minutes=1)).time().replace(microsecond=0)
    db_session.commit()


def _set_autolock_window_not_reached(db_session, tenant: Tenant) -> None:
    tenant_now = datetime.now(ZoneInfo(tenant.default_timezone))
    tenant.auto_lock_enabled = True
    tenant.default_cutoff_time = (tenant_now + timedelta(minutes=15)).time().replace(microsecond=0)
    db_session.commit()


def test_auto_lock_run_locks_only_eligible_plans_and_is_tenant_scoped(client, db_session):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )
    demo_tenant = _tenant_by_slug(db_session, "demo-cortecero")
    _set_autolock_window_reached(db_session, demo_tenant)

    target_service_date = datetime.now(ZoneInfo(demo_tenant.default_timezone)).date() + timedelta(days=1)
    demo_open_plans_before = list(
        db_session.scalars(
            select(Plan).where(
                Plan.tenant_id == demo_tenant.id,
                Plan.service_date == target_service_date,
                Plan.status == PlanStatus.open,
            )
        )
    )
    assert demo_open_plans_before, "Seed debería incluir al menos un plan open para mañana"

    tenant_b = Tenant(
        name="Tenant B AutoLock",
        slug="tenant-b-auto-lock",
        default_cutoff_time=demo_tenant.default_cutoff_time,
        default_timezone=demo_tenant.default_timezone,
        auto_lock_enabled=True,
        created_at=datetime.now(UTC),
    )
    db_session.add(tenant_b)
    db_session.flush()
    db_session.add(
        User(
            tenant_id=tenant_b.id,
            email="logistics@tenantb-autolock.cortecero.app",
            full_name="Tenant B Logistics",
            password_hash=hash_password("logisticsb123"),
            role=UserRole.logistics,
            is_active=True,
            created_at=datetime.now(UTC),
        )
    )
    zone_b = Zone(
        tenant_id=tenant_b.id,
        name="Zona Tenant B",
        default_cutoff_time=demo_tenant.default_cutoff_time,
        timezone=demo_tenant.default_timezone,
        active=True,
        created_at=datetime.now(UTC),
    )
    db_session.add(zone_b)
    db_session.flush()
    tenant_b_open_plan = Plan(
        tenant_id=tenant_b.id,
        service_date=target_service_date,
        zone_id=zone_b.id,
        status=PlanStatus.open,
        version=1,
        locked_at=None,
        locked_by=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(tenant_b_open_plan)
    db_session.commit()

    run_res = client.post("/plans/auto-lock/run", headers=auth_headers(token))
    assert run_res.status_code == 200, run_res.text
    body = run_res.json()
    assert body["auto_lock_enabled"] is True
    assert body["window_reached"] is True
    assert body["service_date"] == target_service_date.isoformat()
    assert body["considered_open_plans"] == len(demo_open_plans_before)
    assert body["locked_count"] == len(demo_open_plans_before)

    demo_open_plan_ids = {str(plan.id) for plan in demo_open_plans_before}
    assert set(body["locked_plan_ids"]) == demo_open_plan_ids

    demo_plans_after = list(
        db_session.scalars(
            select(Plan).where(
                Plan.tenant_id == demo_tenant.id,
                Plan.service_date == target_service_date,
            )
        )
    )
    for plan in demo_plans_after:
        if str(plan.id) in demo_open_plan_ids:
            assert plan.status == PlanStatus.locked
            assert plan.locked_by is not None

    tenant_b_plan_after = db_session.scalar(select(Plan).where(Plan.id == tenant_b_open_plan.id))
    assert tenant_b_plan_after is not None
    assert tenant_b_plan_after.status == PlanStatus.open

    audit_rows = list(
        db_session.scalars(
            select(AuditLog).where(
                AuditLog.tenant_id == demo_tenant.id,
                AuditLog.action == "auto_lock_plan",
            )
        )
    )
    assert len(audit_rows) == len(demo_open_plans_before)


def test_auto_lock_run_is_idempotent(client, db_session):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )
    demo_tenant = _tenant_by_slug(db_session, "demo-cortecero")
    _set_autolock_window_reached(db_session, demo_tenant)

    first_run = client.post("/plans/auto-lock/run", headers=auth_headers(token))
    assert first_run.status_code == 200, first_run.text
    first_body = first_run.json()
    assert first_body["locked_count"] >= 1

    second_run = client.post("/plans/auto-lock/run", headers=auth_headers(token))
    assert second_run.status_code == 200, second_run.text
    second_body = second_run.json()
    assert second_body["locked_count"] == 0
    assert second_body["considered_open_plans"] == 0
    assert second_body["locked_plan_ids"] == []

    audit_count = db_session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.tenant_id == demo_tenant.id,
            AuditLog.action == "auto_lock_plan",
        )
    )
    assert (audit_count or 0) == first_body["locked_count"]


def test_auto_lock_run_non_eligible_cases(client, db_session):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )
    demo_tenant = _tenant_by_slug(db_session, "demo-cortecero")

    target_service_date = datetime.now(ZoneInfo(demo_tenant.default_timezone)).date() + timedelta(days=1)
    open_before = list(
        db_session.scalars(
            select(Plan).where(
                Plan.tenant_id == demo_tenant.id,
                Plan.service_date == target_service_date,
                Plan.status == PlanStatus.open,
            )
        )
    )
    assert open_before

    demo_tenant.auto_lock_enabled = False
    demo_tenant.default_cutoff_time = (datetime.now(ZoneInfo(demo_tenant.default_timezone)) - timedelta(minutes=1)).time()
    db_session.commit()

    disabled_res = client.post("/plans/auto-lock/run", headers=auth_headers(token))
    assert disabled_res.status_code == 200, disabled_res.text
    disabled_body = disabled_res.json()
    assert disabled_body["auto_lock_enabled"] is False
    assert disabled_body["locked_count"] == 0
    assert disabled_body["considered_open_plans"] == 0

    _set_autolock_window_not_reached(db_session, demo_tenant)

    window_res = client.post("/plans/auto-lock/run", headers=auth_headers(token))
    assert window_res.status_code == 200, window_res.text
    window_body = window_res.json()
    assert window_body["auto_lock_enabled"] is True
    assert window_body["window_reached"] is False
    assert window_body["locked_count"] == 0
    assert window_body["considered_open_plans"] == 0

    open_after = list(
        db_session.scalars(
            select(Plan).where(
                Plan.tenant_id == demo_tenant.id,
                Plan.service_date == target_service_date,
                Plan.status == PlanStatus.open,
            )
        )
    )
    assert len(open_after) == len(open_before)
