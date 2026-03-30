import uuid
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from app.models import Tenant, Vehicle
from tests.helpers import auth_headers, login_as


def _demo_tenant_id(db_session) -> uuid.UUID:
    tenant = db_session.scalar(select(Tenant).where(Tenant.slug == "demo-cortecero"))
    assert tenant is not None
    return tenant.id


def _create_demo_plan(client, office_token: str, logistics_token: str, service_date: str) -> str:
    orders_res = client.get("/orders", headers=auth_headers(office_token))
    assert orders_res.status_code == 200, orders_res.text
    zone_id = orders_res.json()["items"][0]["zone_id"]

    create_res = client.post(
        "/plans",
        json={"service_date": service_date, "zone_id": zone_id},
        headers=auth_headers(logistics_token),
    )
    assert create_res.status_code == 201, create_res.text
    return create_res.json()["id"]


def test_plan_assignment_exposes_vehicle_fields(client):
    token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )

    plans_res = client.get("/plans", headers=auth_headers(token))
    assert plans_res.status_code == 200, plans_res.text
    assert plans_res.json()["items"]
    first = plans_res.json()["items"][0]
    assert "vehicle_id" in first
    assert "vehicle_code" in first
    assert "vehicle_name" in first
    assert "vehicle_capacity_kg" in first


def test_plan_vehicle_assignment_and_unassignment_with_audit(client, db_session):
    office_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )
    logistics_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )
    plan_id = _create_demo_plan(client, office_token, logistics_token, service_date="2099-12-21")

    vehicle = Vehicle(
        tenant_id=_demo_tenant_id(db_session),
        code=f"VH-{uuid4()}",
        name="Furgoneta Norte",
        capacity_kg=1200,
        active=True,
        created_at=datetime.now(UTC),
    )
    db_session.add(vehicle)
    db_session.commit()
    db_session.refresh(vehicle)

    assign_res = client.patch(
        f"/plans/{plan_id}/vehicle",
        json={"vehicle_id": str(vehicle.id)},
        headers=auth_headers(logistics_token),
    )
    assert assign_res.status_code == 200, assign_res.text
    assigned = assign_res.json()
    assert assigned["vehicle_id"] == str(vehicle.id)
    assert assigned["vehicle_code"] == vehicle.code
    assert assigned["vehicle_name"] == vehicle.name
    assert float(assigned["vehicle_capacity_kg"]) == 1200.0
    assert assigned["version"] == 2

    idempotent_res = client.patch(
        f"/plans/{plan_id}/vehicle",
        json={"vehicle_id": str(vehicle.id)},
        headers=auth_headers(logistics_token),
    )
    assert idempotent_res.status_code == 200, idempotent_res.text
    assert idempotent_res.json()["version"] == 2

    audit_res = client.get(
        "/audit",
        params={"entity_type": "plan", "entity_id": plan_id},
        headers=auth_headers(logistics_token),
    )
    assert audit_res.status_code == 200, audit_res.text
    vehicle_events = [item for item in audit_res.json()["items"] if item["action"] == "plan.vehicle_updated"]
    assert len(vehicle_events) == 1
    assert vehicle_events[0]["metadata_json"]["new_vehicle_id"] == str(vehicle.id)

    clear_res = client.patch(
        f"/plans/{plan_id}/vehicle",
        json={"vehicle_id": None},
        headers=auth_headers(logistics_token),
    )
    assert clear_res.status_code == 200, clear_res.text
    cleared = clear_res.json()
    assert cleared["vehicle_id"] is None
    assert cleared["vehicle_code"] is None
    assert cleared["vehicle_name"] is None
    assert cleared["vehicle_capacity_kg"] is None
    assert cleared["version"] == 3


def test_plan_vehicle_assignment_enforces_rbac_and_tenant_scope(client, db_session):
    office_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )
    logistics_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )
    plan_id = _create_demo_plan(client, office_token, logistics_token, service_date="2099-12-22")

    forbidden_res = client.patch(
        f"/plans/{plan_id}/vehicle",
        json={"vehicle_id": None},
        headers=auth_headers(office_token),
    )
    assert forbidden_res.status_code == 403
    assert forbidden_res.json()["detail"]["code"] == "RBAC_FORBIDDEN"

    tenant_b = Tenant(
        name="Tenant B Vehicles",
        slug="tenant-b-vehicles",
        default_cutoff_time=datetime.now(UTC).time().replace(microsecond=0),
        default_timezone="Europe/Madrid",
        auto_lock_enabled=False,
        created_at=datetime.now(UTC),
    )
    db_session.add(tenant_b)
    db_session.flush()

    vehicle_b = Vehicle(
        tenant_id=tenant_b.id,
        code=f"VB-{uuid4()}",
        name="Vehiculo Tenant B",
        capacity_kg=1000,
        active=True,
        created_at=datetime.now(UTC),
    )
    db_session.add(vehicle_b)
    db_session.commit()

    cross_tenant_res = client.patch(
        f"/plans/{plan_id}/vehicle",
        json={"vehicle_id": str(vehicle_b.id)},
        headers=auth_headers(logistics_token),
    )
    assert cross_tenant_res.status_code == 404
    assert cross_tenant_res.json()["detail"]["code"] == "VEHICLE_NOT_FOUND"


def test_plan_vehicle_assignment_rejects_inactive_vehicle(client, db_session):
    office_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )
    logistics_token = login_as(
        client,
        tenant_slug="demo-cortecero",
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )
    plan_id = _create_demo_plan(client, office_token, logistics_token, service_date="2099-12-23")

    vehicle = Vehicle(
        tenant_id=_demo_tenant_id(db_session),
        code=f"VX-{uuid4()}",
        name="Vehiculo Inactivo",
        capacity_kg=700,
        active=False,
        created_at=datetime.now(UTC),
    )
    db_session.add(vehicle)
    db_session.commit()

    assign_res = client.patch(
        f"/plans/{plan_id}/vehicle",
        json={"vehicle_id": str(vehicle.id)},
        headers=auth_headers(logistics_token),
    )
    assert assign_res.status_code == 422
    assert assign_res.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"
