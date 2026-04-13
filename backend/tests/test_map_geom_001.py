"""
MAP-GEOM-001 — Geometría vial estable en RouteOut.

Cubre:
  - route_geometry derivada desde optimization_response_json.routes[].transitions[].routePolyline
  - route_geometry = null cuando no hay transition polylines disponibles
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select

from app.models import Plan, PlanStatus, Route, RouteStatus, Tenant, Vehicle, Zone
from tests.helpers import auth_headers, login_as


def _logistics_token(client) -> str:
    return login_as(
        client,
        tenant_slug="demo-cortecero",
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )


def _pick_route(db_session):
    tenant = db_session.scalar(select(Tenant).where(Tenant.slug == "demo-cortecero"))
    assert tenant is not None, "Tenant demo-cortecero no encontrado"
    route = db_session.scalar(
        select(Route).where(Route.tenant_id == tenant.id).order_by(Route.created_at, Route.id)
    )
    if route is not None:
        return route

    now = datetime.now(UTC)
    service_date = date.today()
    zone = db_session.scalar(select(Zone).where(Zone.tenant_id == tenant.id).order_by(Zone.created_at, Zone.id))
    vehicle = db_session.scalar(
        select(Vehicle).where(Vehicle.tenant_id == tenant.id, Vehicle.active.is_(True)).order_by(Vehicle.created_at, Vehicle.id)
    )
    assert zone is not None, "No hay zona disponible en seed"
    assert vehicle is not None, "No hay vehículo activo en seed"

    plan = db_session.scalar(
        select(Plan).where(Plan.tenant_id == tenant.id, Plan.service_date == service_date, Plan.zone_id == zone.id)
    )
    if plan is None:
        plan = Plan(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            service_date=service_date,
            zone_id=zone.id,
            status=PlanStatus.open,
            version=1,
            locked_at=None,
            locked_by=None,
            created_at=now,
            updated_at=now,
        )
        db_session.add(plan)
        db_session.flush()

    route = Route(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        plan_id=plan.id,
        vehicle_id=vehicle.id,
        driver_id=None,
        service_date=service_date,
        status=RouteStatus.draft,
        version=1,
        optimization_request_id=None,
        optimization_response_json=None,
        created_at=now,
        updated_at=now,
        dispatched_at=None,
        completed_at=None,
    )
    db_session.add(route)
    db_session.commit()
    return route


def test_get_route_exposes_derived_route_geometry(client, db_session):
    route = _pick_route(db_session)
    route.optimization_response_json = {
        "provider": "google",
        "routes": [
            {
                "transitions": [
                    {"routePolyline": {"points": "poly-1"}},
                    {"routePolyline": {"points": "poly-2"}},
                ],
            }
        ],
    }
    db_session.commit()

    token = _logistics_token(client)
    res = client.get(f"/routes/{route.id}", headers=auth_headers(token))
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["route_geometry"] == {
        "provider": "google",
        "encoding": "google_encoded_polyline",
        "transition_polylines": ["poly-1", "poly-2"],
    }


def test_get_route_route_geometry_null_without_transition_polylines(client, db_session):
    route = _pick_route(db_session)
    route.optimization_response_json = {
        "provider": "google",
        "routes": [
            {
                "transitions": [
                    {"travelDuration": "100s"},
                ],
            }
        ],
    }
    db_session.commit()

    token = _logistics_token(client)
    res = client.get(f"/routes/{route.id}", headers=auth_headers(token))
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["route_geometry"] is None
