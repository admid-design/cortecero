"""
Bloque D — Tests de ejecución conductor
Cubre:
  - POST /stops/{id}/arrive    (happy path, idempotencia, conflict 409)
  - POST /stops/{id}/complete  (happy path, idempotencia, conflict 409, order→delivered)
  - POST /stops/{id}/fail      (happy path, idempotencia, conflict 409, order→failed_delivery)
  - POST /incidents            (happy path, idempotencia)
  - GET  /incidents            (sin side effects)
  - route.started automático al primer arrive
  - route.completed automático cuando todas las paradas terminan
  - tenant isolation: stop de otro tenant → 404
"""

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from app.models import (
    Customer,
    Driver,
    Incident,
    Order,
    OrderIntakeType,
    OrderStatus,
    Plan,
    PlanStatus,
    Route,
    RouteEvent,
    RouteEventType,
    RouteStatus,
    RouteStop,
    RouteStopStatus,
    SourceChannel,
    Tenant,
    Vehicle,
    Zone,
)
from tests.helpers import auth_headers, login_as

# ---------------------------------------------------------------------------
# Helpers de setup
# ---------------------------------------------------------------------------


def _get_tenant(db_session) -> Tenant:
    t = db_session.scalar(select(Tenant).where(Tenant.slug == "demo-cortecero"))
    assert t is not None, "Tenant demo-cortecero no encontrado (seed no ejecutado)"
    return t


def _logistics_token(client) -> str:
    return login_as(
        client,
        tenant_slug="demo-cortecero",
        email="logistics@demo.cortecero.app",
        password="logistics123",
    )


def _build_route_with_stops(
    db_session,
    tenant_id: uuid.UUID,
    *,
    n_stops: int = 2,
    route_status: RouteStatus = RouteStatus.dispatched,
    stop_status: RouteStopStatus = RouteStopStatus.pending,
) -> tuple[Route, list[RouteStop]]:
    """
    Crea un Route + RouteStops directamente en la DB, en el estado indicado.
    Reutiliza vehículo y chofer del seed.  No llama a la API de planificación.
    """
    now = datetime.now(UTC)
    svc_date = date.today()

    vehicle = db_session.scalar(
        select(Vehicle).where(Vehicle.tenant_id == tenant_id, Vehicle.active.is_(True))
    )
    assert vehicle is not None, "No hay vehículos activos en seed"

    driver = db_session.scalar(
        select(Driver).where(Driver.tenant_id == tenant_id, Driver.is_active.is_(True))
    )
    assert driver is not None, "No hay choferes activos en seed"

    zone = db_session.scalar(select(Zone).where(Zone.tenant_id == tenant_id))
    assert zone is not None

    customer = db_session.scalar(select(Customer).where(Customer.tenant_id == tenant_id))
    assert customer is not None

    plan = db_session.scalar(
        select(Plan).where(
            Plan.tenant_id == tenant_id,
            Plan.status.in_([PlanStatus.locked, PlanStatus.open]),
        )
    )
    if plan is None:
        plan = Plan(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            service_date=svc_date,
            zone_id=zone.id,
            status=PlanStatus.locked,
            version=1,
            created_at=now,
            updated_at=now,
        )
        db_session.add(plan)
        db_session.flush()

    dispatched_at = now if route_status not in (RouteStatus.draft, RouteStatus.planned) else None
    route = Route(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        plan_id=plan.id,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        service_date=svc_date,
        status=route_status,
        version=1,
        optimization_request_id=None,
        optimization_response_json=None,
        created_at=now,
        updated_at=now,
        dispatched_at=dispatched_at,
        completed_at=None,
    )
    db_session.add(route)
    db_session.flush()

    stops: list[RouteStop] = []
    for i in range(n_stops):
        order = Order(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            customer_id=customer.id,
            zone_id=zone.id,
            external_ref=f"BLK-D-{uuid.uuid4()}",
            requested_date=svc_date,
            service_date=svc_date,
            created_at=now,
            status=OrderStatus.dispatched,
            is_late=False,
            lateness_reason=None,
            effective_cutoff_at=now,
            source_channel=SourceChannel.office,
            intake_type=OrderIntakeType.new_order,
            total_weight_kg=10.0,
            ingested_at=now,
            updated_at=now,
        )
        db_session.add(order)
        db_session.flush()

        arrived_at = (
            now
            if stop_status in (RouteStopStatus.arrived, RouteStopStatus.completed, RouteStopStatus.failed)
            else None
        )
        stop = RouteStop(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            route_id=route.id,
            order_id=order.id,
            sequence_number=i + 1,
            estimated_arrival_at=None,
            estimated_service_minutes=10,
            status=stop_status,
            arrived_at=arrived_at,
            completed_at=now if stop_status == RouteStopStatus.completed else None,
            failed_at=now if stop_status == RouteStopStatus.failed else None,
            failure_reason="setup reason" if stop_status == RouteStopStatus.failed else None,
            created_at=now,
            updated_at=now,
        )
        db_session.add(stop)
        db_session.flush()
        stops.append(stop)

    db_session.commit()

    # Refrescar para obtener IDs definitivos
    db_session.refresh(route)
    for s in stops:
        db_session.refresh(s)
    return route, stops


# ===========================================================================
# POST /stops/{id}/arrive
# ===========================================================================


def test_stop_arrive_happy_path(client, db_session):
    tenant = _get_tenant(db_session)
    route, stops = _build_route_with_stops(db_session, tenant.id, n_stops=1)
    stop = stops[0]
    token = _logistics_token(client)

    res = client.post(f"/stops/{stop.id}/arrive", json={}, headers=auth_headers(token))

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "arrived"
    assert body["arrived_at"] is not None


def test_route_auto_starts_on_first_arrive(client, db_session):
    """Primera llegada en ruta dispatched → ruta pasa a in_progress."""
    tenant = _get_tenant(db_session)
    route, stops = _build_route_with_stops(
        db_session, tenant.id, n_stops=2, route_status=RouteStatus.dispatched
    )
    stop = stops[0]
    token = _logistics_token(client)

    assert route.status == RouteStatus.dispatched

    client.post(f"/stops/{stop.id}/arrive", json={}, headers=auth_headers(token))

    db_session.expire_all()
    updated_route = db_session.get(Route, route.id)
    assert updated_route.status == RouteStatus.in_progress

    # Evento route.started emitido
    events = list(
        db_session.scalars(
            select(RouteEvent).where(
                RouteEvent.route_id == route.id,
                RouteEvent.event_type == RouteEventType.route_started,
            )
        )
    )
    assert len(events) == 1


def test_stop_arrive_idempotency_same_key_no_duplicate_event(client, db_session):
    """
    Misma idempotency_key → segunda llamada devuelve 200 y no genera evento duplicado.
    """
    tenant = _get_tenant(db_session)
    route, stops = _build_route_with_stops(db_session, tenant.id, n_stops=1)
    stop = stops[0]
    token = _logistics_token(client)
    idem_key = str(uuid.uuid4())

    res1 = client.post(f"/stops/{stop.id}/arrive", json={"idempotency_key": idem_key}, headers=auth_headers(token))
    assert res1.status_code == 200, res1.text

    res2 = client.post(f"/stops/{stop.id}/arrive", json={"idempotency_key": idem_key}, headers=auth_headers(token))
    assert res2.status_code == 200, res2.text

    # Solo debe existir un evento stop.arrived para esta parada con esta clave
    db_session.expire_all()
    events = list(
        db_session.scalars(
            select(RouteEvent).where(
                RouteEvent.route_stop_id == stop.id,
                RouteEvent.event_type == RouteEventType.stop_arrived,
            )
        )
    )
    assert len(events) == 1, f"Se esperaba 1 evento arrive, hubo {len(events)}"


def test_stop_arrive_conflict_from_completed_state_returns_409(client, db_session):
    """Intentar arrive sobre una parada ya completed → 409."""
    tenant = _get_tenant(db_session)
    _, stops = _build_route_with_stops(
        db_session, tenant.id, n_stops=1, stop_status=RouteStopStatus.completed
    )
    stop = stops[0]
    token = _logistics_token(client)

    res = client.post(f"/stops/{stop.id}/arrive", json={}, headers=auth_headers(token))

    assert res.status_code == 409, res.text


def test_stop_arrive_nonexistent_stop_returns_404(client, db_session):
    """Stop inexistente → 404 (tenant isolation implícita)."""
    token = _logistics_token(client)
    res = client.post(f"/stops/{uuid.uuid4()}/arrive", json={}, headers=auth_headers(token))
    assert res.status_code == 404, res.text


# ===========================================================================
# POST /stops/{id}/complete
# ===========================================================================


def test_stop_complete_happy_path_order_becomes_delivered(client, db_session):
    """arrive → complete: stop=completed, order=delivered."""
    tenant = _get_tenant(db_session)
    route, stops = _build_route_with_stops(
        db_session, tenant.id, n_stops=1, stop_status=RouteStopStatus.arrived
    )
    stop = stops[0]
    token = _logistics_token(client)

    res = client.post(f"/stops/{stop.id}/complete", json={}, headers=auth_headers(token))

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "completed"
    assert body["completed_at"] is not None

    # Verificar que la orden cambió a delivered
    db_session.expire_all()
    order = db_session.get(Order, stop.order_id)
    assert order.status == OrderStatus.delivered


def test_stop_complete_idempotency(client, db_session):
    """Misma idempotency_key en complete → segunda llamada devuelve 200, sin duplicado."""
    tenant = _get_tenant(db_session)
    _, stops = _build_route_with_stops(
        db_session, tenant.id, n_stops=1, stop_status=RouteStopStatus.arrived
    )
    stop = stops[0]
    token = _logistics_token(client)
    idem_key = str(uuid.uuid4())

    res1 = client.post(f"/stops/{stop.id}/complete", json={"idempotency_key": idem_key}, headers=auth_headers(token))
    assert res1.status_code == 200, res1.text

    res2 = client.post(f"/stops/{stop.id}/complete", json={"idempotency_key": idem_key}, headers=auth_headers(token))
    assert res2.status_code == 200, res2.text

    db_session.expire_all()
    events = list(
        db_session.scalars(
            select(RouteEvent).where(
                RouteEvent.route_stop_id == stop.id,
                RouteEvent.event_type == RouteEventType.stop_completed,
            )
        )
    )
    assert len(events) == 1


def test_stop_complete_from_pending_returns_409(client, db_session):
    """complete desde pending (sin pasar por arrived) → 409."""
    tenant = _get_tenant(db_session)
    _, stops = _build_route_with_stops(
        db_session, tenant.id, n_stops=1, stop_status=RouteStopStatus.pending
    )
    stop = stops[0]
    token = _logistics_token(client)

    res = client.post(f"/stops/{stop.id}/complete", json={}, headers=auth_headers(token))

    assert res.status_code == 409, res.text


# ===========================================================================
# POST /stops/{id}/fail
# ===========================================================================


def test_stop_fail_happy_path_order_becomes_failed_delivery(client, db_session):
    """arrive → fail: stop=failed, order=failed_delivery."""
    tenant = _get_tenant(db_session)
    route, stops = _build_route_with_stops(
        db_session, tenant.id, n_stops=1, stop_status=RouteStopStatus.arrived
    )
    stop = stops[0]
    token = _logistics_token(client)
    reason = "Cliente ausente al momento de la entrega"

    res = client.post(
        f"/stops/{stop.id}/fail",
        json={"failure_reason": reason},
        headers=auth_headers(token),
    )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "failed"
    assert body["failure_reason"] == reason
    assert body["failed_at"] is not None

    db_session.expire_all()
    order = db_session.get(Order, stop.order_id)
    assert order.status == OrderStatus.failed_delivery


def test_stop_fail_idempotency(client, db_session):
    """Misma idempotency_key en fail → segunda llamada 200, sin evento duplicado."""
    tenant = _get_tenant(db_session)
    _, stops = _build_route_with_stops(
        db_session, tenant.id, n_stops=1, stop_status=RouteStopStatus.arrived
    )
    stop = stops[0]
    token = _logistics_token(client)
    idem_key = str(uuid.uuid4())
    payload = {"failure_reason": "No acceso al edificio", "idempotency_key": idem_key}

    res1 = client.post(f"/stops/{stop.id}/fail", json=payload, headers=auth_headers(token))
    assert res1.status_code == 200, res1.text

    res2 = client.post(f"/stops/{stop.id}/fail", json=payload, headers=auth_headers(token))
    assert res2.status_code == 200, res2.text

    db_session.expire_all()
    events = list(
        db_session.scalars(
            select(RouteEvent).where(
                RouteEvent.route_stop_id == stop.id,
                RouteEvent.event_type == RouteEventType.stop_failed,
            )
        )
    )
    assert len(events) == 1


def test_stop_fail_from_pending_returns_409(client, db_session):
    """fail desde pending (sin arrived) → 409."""
    tenant = _get_tenant(db_session)
    _, stops = _build_route_with_stops(
        db_session, tenant.id, n_stops=1, stop_status=RouteStopStatus.pending
    )
    stop = stops[0]
    token = _logistics_token(client)

    res = client.post(
        f"/stops/{stop.id}/fail",
        json={"failure_reason": "Intento fallido"},
        headers=auth_headers(token),
    )

    assert res.status_code == 409, res.text


def test_stop_fail_missing_reason_returns_422(client, db_session):
    """fail sin failure_reason → 422 (validación de schema)."""
    tenant = _get_tenant(db_session)
    _, stops = _build_route_with_stops(
        db_session, tenant.id, n_stops=1, stop_status=RouteStopStatus.arrived
    )
    stop = stops[0]
    token = _logistics_token(client)

    res = client.post(f"/stops/{stop.id}/fail", json={}, headers=auth_headers(token))

    assert res.status_code == 422, res.text


# ===========================================================================
# Route auto-complete cuando todas las paradas terminan
# ===========================================================================


def test_route_auto_completes_when_all_stops_terminal(client, db_session):
    """
    Ruta con 2 paradas: una completa, otra falla.
    Cuando la última termina, la ruta debe pasar a completed.
    """
    tenant = _get_tenant(db_session)
    route, stops = _build_route_with_stops(
        db_session, tenant.id, n_stops=2, stop_status=RouteStopStatus.arrived
    )
    stop_a, stop_b = stops
    token = _logistics_token(client)

    # Completar primera parada
    res1 = client.post(f"/stops/{stop_a.id}/complete", json={}, headers=auth_headers(token))
    assert res1.status_code == 200, res1.text

    # Ruta todavía in_progress
    db_session.expire_all()
    r = db_session.get(Route, route.id)
    assert r.status == RouteStatus.in_progress

    # Fallar segunda parada
    res2 = client.post(
        f"/stops/{stop_b.id}/fail",
        json={"failure_reason": "Acceso bloqueado"},
        headers=auth_headers(token),
    )
    assert res2.status_code == 200, res2.text

    # Ahora la ruta debe estar completed
    db_session.expire_all()
    r = db_session.get(Route, route.id)
    assert r.status == RouteStatus.completed
    assert r.completed_at is not None

    # Evento route.completed emitido
    completed_events = list(
        db_session.scalars(
            select(RouteEvent).where(
                RouteEvent.route_id == route.id,
                RouteEvent.event_type == RouteEventType.route_completed,
            )
        )
    )
    assert len(completed_events) == 1


# ===========================================================================
# POST /incidents
# ===========================================================================


def test_incident_create_happy_path(client, db_session):
    """POST /incidents → 201, incident registrado."""
    tenant = _get_tenant(db_session)
    route, stops = _build_route_with_stops(db_session, tenant.id, n_stops=1)
    token = _logistics_token(client)

    payload = {
        "route_id": str(route.id),
        "route_stop_id": str(stops[0].id),
        "type": "customer_absent",
        "severity": "medium",
        "description": "Cliente no estaba en la dirección indicada.",
    }

    res = client.post("/incidents", json=payload, headers=auth_headers(token))

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["type"] == "customer_absent"
    assert body["severity"] == "medium"
    assert body["status"] == "open"
    assert body["route_id"] == str(route.id)

    # Evento incident.reported registrado en log
    db_session.expire_all()
    events = list(
        db_session.scalars(
            select(RouteEvent).where(
                RouteEvent.route_id == route.id,
                RouteEvent.event_type == RouteEventType.incident_reported,
            )
        )
    )
    assert len(events) == 1
    assert events[0].metadata_json.get("incident_id") == body["id"]


def test_incident_create_idempotency(client, db_session):
    """Misma idempotency_key → segunda llamada devuelve 200 con la incidencia original."""
    tenant = _get_tenant(db_session)
    route, _ = _build_route_with_stops(db_session, tenant.id, n_stops=1)
    token = _logistics_token(client)
    idem_key = str(uuid.uuid4())

    payload = {
        "route_id": str(route.id),
        "type": "vehicle_issue",
        "severity": "high",
        "description": "Pinchazo de rueda.",
        "idempotency_key": idem_key,
    }

    res1 = client.post("/incidents", json=payload, headers=auth_headers(token))
    assert res1.status_code == 201, res1.text
    incident_id = res1.json()["id"]

    res2 = client.post("/incidents", json=payload, headers=auth_headers(token))
    assert res2.status_code == 200, res2.text
    assert res2.json()["id"] == incident_id

    # Solo un incidente creado en DB
    db_session.expire_all()
    incidents = list(
        db_session.scalars(
            select(Incident).where(Incident.route_id == route.id)
        )
    )
    assert len(incidents) == 1


def test_incident_route_not_found_returns_404(client, db_session):
    """route_id inexistente → 404."""
    token = _logistics_token(client)
    payload = {
        "route_id": str(uuid.uuid4()),
        "type": "other",
        "severity": "low",
        "description": "Test.",
    }
    res = client.post("/incidents", json=payload, headers=auth_headers(token))
    assert res.status_code == 404, res.text


# ===========================================================================
# GET /incidents — sin side effects
# ===========================================================================


def test_get_incidents_no_side_effects(client, db_session):
    """GET /incidents es lectura pura: no crea ni modifica registros."""
    tenant = _get_tenant(db_session)
    route, _ = _build_route_with_stops(db_session, tenant.id, n_stops=1)
    token = _logistics_token(client)

    # Contar incidentes y eventos antes
    incidents_before = db_session.scalars(select(Incident).where(Incident.tenant_id == tenant.id)).all()
    events_before = db_session.scalars(select(RouteEvent).where(RouteEvent.tenant_id == tenant.id)).all()

    res = client.get("/incidents", params={"route_id": str(route.id)}, headers=auth_headers(token))
    assert res.status_code == 200, res.text
    assert "items" in res.json()
    assert "total" in res.json()

    # Contar incidentes y eventos después — no deben haber aumentado
    db_session.expire_all()
    incidents_after = db_session.scalars(select(Incident).where(Incident.tenant_id == tenant.id)).all()
    events_after = db_session.scalars(select(RouteEvent).where(RouteEvent.tenant_id == tenant.id)).all()

    assert len(incidents_after) == len(incidents_before)
    assert len(events_after) == len(events_before)


def test_get_incidents_filters_by_route(client, db_session):
    """GET /incidents?route_id solo devuelve incidentes de esa ruta."""
    tenant = _get_tenant(db_session)
    route_a, _ = _build_route_with_stops(db_session, tenant.id, n_stops=1)
    route_b, _ = _build_route_with_stops(db_session, tenant.id, n_stops=1)
    token = _logistics_token(client)

    # Crear incidente en ruta_a
    payload = {
        "route_id": str(route_a.id),
        "type": "wrong_address",
        "severity": "low",
        "description": "Dirección equivocada.",
    }
    client.post("/incidents", json=payload, headers=auth_headers(token))

    # GET filtrando por ruta_b (debe devolver 0)
    res = client.get("/incidents", params={"route_id": str(route_b.id)}, headers=auth_headers(token))
    assert res.status_code == 200, res.text
    assert res.json()["total"] == 0

    # GET filtrando por ruta_a (debe devolver 1)
    res2 = client.get("/incidents", params={"route_id": str(route_a.id)}, headers=auth_headers(token))
    assert res2.status_code == 200
    assert res2.json()["total"] == 1
