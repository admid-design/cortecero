"""Tests para ROUTE-FROM-TEMPLATE-001.

Cubre:
  GET  /route-templates
    - Lista plantillas del tenant con stop_count y has_vehicle
    - Filtro por vehicle_id, day_of_week, season
    - Aislamiento multi-tenant

  POST /routes/from-template
    - Happy path: ruta draft creada con stops (order_id=null)
    - Override vehicle_id desde body
    - Driver opcional asignado
    - Error TEMPLATE_NOT_FOUND (404)
    - Error VEHICLE_NOT_FOUND (404)
    - Error DRIVER_NOT_FOUND (404)
    - Error VEHICLE_REQUIRED (422) — plantilla sin vehículo y body sin vehicle_id
    - Error TEMPLATE_HAS_NO_STOPS (422)
    - Unicidad: stop con order_id=null no viola uq_route_stops_route_sequence
    - RouteStop.order_id es null en DB
    - Route.plan_id es null en DB
"""

import uuid
from datetime import UTC, datetime, date, time

import pytest
from sqlalchemy import select

from app.models import (
    Driver,
    Route,
    RouteStatus,
    RouteStop,
    RouteTemplate,
    RouteTemplateStop,
    Tenant,
    Vehicle,
)
from tests.helpers import auth_headers, login_as


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _office_token(client) -> str:
    return login_as(
        client,
        tenant_slug="demo-cortecero",
        email="office@demo.cortecero.app",
        password="office123",
    )


def _demo_tenant(db_session) -> Tenant:
    return db_session.scalar(select(Tenant).where(Tenant.slug == "demo-cortecero"))


def _first_vehicle(db_session, tenant_id) -> Vehicle:
    return db_session.scalar(
        select(Vehicle).where(Vehicle.tenant_id == tenant_id).limit(1)
    )


def _create_template(
    db_session,
    tenant_id: uuid.UUID,
    vehicle_id: uuid.UUID | None = None,
    day_of_week: int = 1,
    season: str | None = None,
    n_stops: int = 2,
    name: str | None = None,
) -> RouteTemplate:
    now = datetime.now(UTC)
    uid = uuid.uuid4().hex[:6]
    tpl = RouteTemplate(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=name or f"Tpl-{uid}",
        season=season,
        vehicle_id=vehicle_id,
        day_of_week=day_of_week,
        created_at=now,
    )
    db_session.add(tpl)
    db_session.flush()

    for i in range(1, n_stops + 1):
        stop = RouteTemplateStop(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            template_id=tpl.id,
            sequence_number=i,
            customer_id=None,
            lat=None,
            lng=None,
            address=f"Calle {i}",
            duration_min=10,
            created_at=now,
        )
        db_session.add(stop)

    db_session.commit()
    return tpl


# ---------------------------------------------------------------------------
# GET /route-templates
# ---------------------------------------------------------------------------

class TestListRouteTemplates:
    def test_returns_templates_with_stop_count(self, client, db_session):
        tenant = _demo_tenant(db_session)
        vehicle = _first_vehicle(db_session, tenant.id)

        tpl = _create_template(db_session, tenant.id, vehicle_id=vehicle.id, n_stops=3)

        token = _office_token(client)
        res = client.get("/route-templates", headers=auth_headers(token))

        assert res.status_code == 200, res.text
        items = res.json()
        assert isinstance(items, list)

        found = next((x for x in items if x["id"] == str(tpl.id)), None)
        assert found is not None, "La plantilla creada no aparece en la lista"
        assert found["stop_count"] == 3
        assert found["has_vehicle"] is True
        assert found["vehicle_id"] == str(vehicle.id)

    def test_has_vehicle_false_when_vehicle_id_null(self, client, db_session):
        tenant = _demo_tenant(db_session)

        tpl = _create_template(db_session, tenant.id, vehicle_id=None, n_stops=1)

        token = _office_token(client)
        res = client.get("/route-templates", headers=auth_headers(token))

        assert res.status_code == 200
        found = next((x for x in res.json() if x["id"] == str(tpl.id)), None)
        assert found is not None
        assert found["has_vehicle"] is False
        assert found["vehicle_id"] is None

    def test_filter_by_vehicle_id(self, client, db_session):
        tenant = _demo_tenant(db_session)
        vehicles = db_session.scalars(
            select(Vehicle).where(Vehicle.tenant_id == tenant.id).limit(2)
        ).all()
        assert len(vehicles) >= 2

        v1, v2 = vehicles[0], vehicles[1]
        tpl1 = _create_template(db_session, tenant.id, vehicle_id=v1.id)
        tpl2 = _create_template(db_session, tenant.id, vehicle_id=v2.id)

        token = _office_token(client)
        res = client.get(
            "/route-templates",
            params={"vehicle_id": str(v1.id)},
            headers=auth_headers(token),
        )

        assert res.status_code == 200
        ids = {x["id"] for x in res.json()}
        assert str(tpl1.id) in ids
        assert str(tpl2.id) not in ids

    def test_filter_by_season(self, client, db_session):
        tenant = _demo_tenant(db_session)
        tpl_v = _create_template(db_session, tenant.id, season="verano-test")
        tpl_i = _create_template(db_session, tenant.id, season="invierno-test")

        token = _office_token(client)
        res = client.get(
            "/route-templates",
            params={"season": "verano-test"},
            headers=auth_headers(token),
        )

        assert res.status_code == 200
        ids = {x["id"] for x in res.json()}
        assert str(tpl_v.id) in ids
        assert str(tpl_i.id) not in ids

    def test_filter_by_day_of_week(self, client, db_session):
        tenant = _demo_tenant(db_session)
        tpl_lun = _create_template(db_session, tenant.id, day_of_week=1)
        tpl_vie = _create_template(db_session, tenant.id, day_of_week=5)

        token = _office_token(client)
        res = client.get(
            "/route-templates",
            params={"day_of_week": 1},
            headers=auth_headers(token),
        )

        assert res.status_code == 200
        ids = {x["id"] for x in res.json()}
        assert str(tpl_lun.id) in ids
        assert str(tpl_vie.id) not in ids


# ---------------------------------------------------------------------------
# POST /routes/from-template — happy path
# ---------------------------------------------------------------------------

class TestCreateRouteFromTemplate:
    def test_creates_draft_route_with_stops(self, client, db_session):
        tenant = _demo_tenant(db_session)
        vehicle = _first_vehicle(db_session, tenant.id)
        tpl = _create_template(db_session, tenant.id, vehicle_id=vehicle.id, n_stops=3)

        token = _office_token(client)
        res = client.post(
            "/routes/from-template",
            json={
                "template_id": str(tpl.id),
                "service_date": "2026-08-01",
            },
            headers=auth_headers(token),
        )

        assert res.status_code == 201, res.text
        body = res.json()

        # Ruta en draft
        assert body["status"] == "draft"
        assert body["plan_id"] is None
        assert body["vehicle_id"] == str(vehicle.id)
        assert len(body["stops"]) == 3

        # Stops con order_id null
        for stop in body["stops"]:
            assert stop["order_id"] is None, "Template stops deben tener order_id=null"

        # Verificar en DB
        route = db_session.scalar(select(Route).where(Route.id == uuid.UUID(body["id"])))
        assert route is not None
        assert route.status == RouteStatus.draft
        assert route.plan_id is None

        db_stops = db_session.scalars(
            select(RouteStop).where(RouteStop.route_id == route.id)
        ).all()
        assert len(db_stops) == 3
        for db_stop in db_stops:
            assert db_stop.order_id is None  # migration 029

    def test_vehicle_override_from_body(self, client, db_session):
        """El body.vehicle_id tiene prioridad sobre template.vehicle_id."""
        tenant = _demo_tenant(db_session)
        vehicles = db_session.scalars(
            select(Vehicle).where(Vehicle.tenant_id == tenant.id).limit(2)
        ).all()
        assert len(vehicles) >= 2
        v1, v2 = vehicles[0], vehicles[1]

        # Template tiene v1, body envía v2
        tpl = _create_template(db_session, tenant.id, vehicle_id=v1.id, n_stops=1)

        token = _office_token(client)
        res = client.post(
            "/routes/from-template",
            json={
                "template_id": str(tpl.id),
                "service_date": "2026-08-02",
                "vehicle_id": str(v2.id),
            },
            headers=auth_headers(token),
        )

        assert res.status_code == 201, res.text
        body = res.json()
        assert body["vehicle_id"] == str(v2.id)

    def test_driver_optional_assigned(self, client, db_session):
        tenant = _demo_tenant(db_session)
        vehicle = _first_vehicle(db_session, tenant.id)
        tpl = _create_template(db_session, tenant.id, vehicle_id=vehicle.id, n_stops=1)

        # Obtener un driver del tenant
        driver = db_session.scalar(
            select(Driver).where(Driver.tenant_id == tenant.id).limit(1)
        )
        assert driver is not None, "El seed debe tener al menos un conductor"

        token = _office_token(client)
        res = client.post(
            "/routes/from-template",
            json={
                "template_id": str(tpl.id),
                "service_date": "2026-08-03",
                "driver_id": str(driver.id),
            },
            headers=auth_headers(token),
        )

        assert res.status_code == 201, res.text
        body = res.json()
        assert body["driver_id"] == str(driver.id)

    def test_sequence_order_preserved(self, client, db_session):
        """Las paradas del template preservan el sequence_number en la ruta creada."""
        tenant = _demo_tenant(db_session)
        vehicle = _first_vehicle(db_session, tenant.id)
        tpl = _create_template(db_session, tenant.id, vehicle_id=vehicle.id, n_stops=4)

        token = _office_token(client)
        res = client.post(
            "/routes/from-template",
            json={"template_id": str(tpl.id), "service_date": "2026-08-04"},
            headers=auth_headers(token),
        )

        assert res.status_code == 201
        stops = res.json()["stops"]
        seqs = [s["sequence_number"] for s in stops]
        assert seqs == sorted(seqs), "sequence_number debe estar ordenado"


# ---------------------------------------------------------------------------
# POST /routes/from-template — errores contractuales
# ---------------------------------------------------------------------------

class TestCreateRouteFromTemplateErrors:
    def test_template_not_found_404(self, client):
        token = _office_token(client)
        res = client.post(
            "/routes/from-template",
            json={
                "template_id": str(uuid.uuid4()),
                "service_date": "2026-08-01",
            },
            headers=auth_headers(token),
        )
        assert res.status_code == 404
        assert res.json()["detail"]["code"] == "TEMPLATE_NOT_FOUND"

    def test_vehicle_required_422_when_no_vehicle(self, client, db_session):
        """Plantilla sin vehicle_id y body sin vehicle_id → VEHICLE_REQUIRED."""
        tenant = _demo_tenant(db_session)
        tpl = _create_template(db_session, tenant.id, vehicle_id=None, n_stops=1)

        token = _office_token(client)
        res = client.post(
            "/routes/from-template",
            json={
                "template_id": str(tpl.id),
                "service_date": "2026-08-01",
            },
            headers=auth_headers(token),
        )
        assert res.status_code == 422
        assert res.json()["detail"]["code"] == "VEHICLE_REQUIRED"

    def test_vehicle_not_found_404(self, client, db_session):
        tenant = _demo_tenant(db_session)
        tpl = _create_template(db_session, tenant.id, vehicle_id=None, n_stops=1)

        token = _office_token(client)
        res = client.post(
            "/routes/from-template",
            json={
                "template_id": str(tpl.id),
                "service_date": "2026-08-01",
                "vehicle_id": str(uuid.uuid4()),
            },
            headers=auth_headers(token),
        )
        assert res.status_code == 404
        assert res.json()["detail"]["code"] == "VEHICLE_NOT_FOUND"

    def test_driver_not_found_404(self, client, db_session):
        tenant = _demo_tenant(db_session)
        vehicle = _first_vehicle(db_session, tenant.id)
        tpl = _create_template(db_session, tenant.id, vehicle_id=vehicle.id, n_stops=1)

        token = _office_token(client)
        res = client.post(
            "/routes/from-template",
            json={
                "template_id": str(tpl.id),
                "service_date": "2026-08-01",
                "driver_id": str(uuid.uuid4()),
            },
            headers=auth_headers(token),
        )
        assert res.status_code == 404
        assert res.json()["detail"]["code"] == "DRIVER_NOT_FOUND"

    def test_template_has_no_stops_422(self, client, db_session):
        tenant = _demo_tenant(db_session)
        vehicle = _first_vehicle(db_session, tenant.id)
        # Crear plantilla con 0 paradas
        tpl = _create_template(db_session, tenant.id, vehicle_id=vehicle.id, n_stops=0)

        token = _office_token(client)
        res = client.post(
            "/routes/from-template",
            json={
                "template_id": str(tpl.id),
                "service_date": "2026-08-01",
            },
            headers=auth_headers(token),
        )
        assert res.status_code == 422
        assert res.json()["detail"]["code"] == "TEMPLATE_HAS_NO_STOPS"

    def test_template_of_other_tenant_not_found(self, client, db_session):
        """Una plantilla de otro tenant devuelve 404 (no 403) por seguridad."""
        # Crear un tenant ficticio y una plantilla en él
        other_tenant = Tenant(
            id=uuid.uuid4(),
            name="Other Tenant",
            slug=f"other-{uuid.uuid4().hex[:6]}",
            default_cutoff_time=time(12, 0),
            default_timezone="Europe/Madrid",
            created_at=datetime.now(UTC),
        )
        db_session.add(other_tenant)
        db_session.flush()

        other_vehicle = Vehicle(
            id=uuid.uuid4(),
            tenant_id=other_tenant.id,
            code=f"OV-{uuid.uuid4().hex[:4]}",
            name="Other Vehicle",
            created_at=datetime.now(UTC),
        )
        db_session.add(other_vehicle)
        db_session.flush()

        tpl = _create_template(db_session, other_tenant.id, vehicle_id=other_vehicle.id, n_stops=1)

        token = _office_token(client)
        res = client.post(
            "/routes/from-template",
            json={
                "template_id": str(tpl.id),
                "service_date": "2026-08-01",
            },
            headers=auth_headers(token),
        )
        assert res.status_code == 404
        assert res.json()["detail"]["code"] == "TEMPLATE_NOT_FOUND"
