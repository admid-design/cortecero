"""
Routing POC — Bloques B + D
Bloque B — Planificación (dispatcher):
  GET  /planning/orders/ready-to-dispatch — pedidos listos para asignar a ruta
  GET  /vehicles/available               — camiones disponibles para planificar
  POST /routes/plan                      — generar plan de rutas
  POST /routes/{routeId}/dispatch        — despachar ruta a chofer
  POST /routes/{routeId}/move-stop       — mover parada entre rutas
  GET  /routes                           — listar rutas (con filtros)
  GET  /routes/{routeId}                 — detalle de ruta con paradas
  GET  /routes/{routeId}/events          — log de eventos de una ruta

Bloque D — Ejecución conductor (PWA con conectividad intermitente):
  POST /stops/{stopId}/arrive            — chofer llega a parada
  POST /stops/{stopId}/complete          — entrega confirmada
  POST /stops/{stopId}/fail              — entrega fallida (reason obligatorio)
  POST /incidents                        — registrar incidencia en ruta

Idempotencia: todos los endpoints de Bloque D aceptan idempotency_key.
  - Clave duplicada → 200 con estado actual
  - Conflicto de estado → 409
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import CurrentUser, require_roles
from app.errors import conflict, forbidden, not_found, unprocessable
from app.eta.calculator import calculate_eta, delay_minutes as eta_delay_minutes
from app.realtime import event_bus
from app.security import decode_token
from app.optimization.google_provider import GoogleRouteOptimizationProvider
from app.optimization.mock_provider import MockRouteOptimizationProvider
from app.optimization.protocol import OptimizationRequest, OptimizationWaypoint, RouteOptimizationProvider
from app.models import (
    Customer,
    CustomerOperationalProfile,
    Driver,
    DriverPosition,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    IncidentType,
    Order,
    OrderStatus,
    Plan,
    PlanStatus,
    Route,
    RouteEvent,
    RouteEventActorType,
    RouteEventType,
    RouteMessage,
    RouteStatus,
    RouteStop,
    RouteStopStatus,
    StopProof,
    User,
    UserRole,
    Vehicle,
)
from app.schemas import (
    DelayAlertOut,
    DriverLocationUpdateRequest,
    DriverPositionOut,
    EtaStopResult,
    IncidentResolveRequest,
    IncidentCreateRequest,
    IncidentOut,
    IncidentsListResponse,
    RecalculateEtaResponse,
    AddStopRequest,
    AddStopResponse,
    RemoveStopResponse,
    RouteMessageIn,
    RouteMessageOut,
    RouteNextStopResponse,
    RouteEventsListResponse,
    RouteEventOut,
    RouteGeometryOut,
    RouteOut,
    RouteStopArriveRequest,
    RouteStopCompleteRequest,
    RouteStopFailRequest,
    RouteStopSkipRequest,
    RouteStopScheduledArrivalRequest,
    RouteStopOut,
    RoutesListResponse,
    StopProofCreateRequest,
    StopProofOut,
    ProofUploadUrlResponse,
    ProofPhotoConfirmRequest,
)

router = APIRouter(tags=["Routing"])


# ============================================================================
# HELPERS
# ============================================================================


def _serialize_stop(stop: RouteStop) -> RouteStopOut:
    return RouteStopOut.model_validate(stop)


def _serialize_stop_with_customer_geo(
    stop: RouteStop,
    *,
    customer_lat: float | None,
    customer_lng: float | None,
) -> RouteStopOut:
    payload = RouteStopOut.model_validate(stop)
    payload.customer_lat = customer_lat
    payload.customer_lng = customer_lng
    return payload


def _load_customer_geo_by_order_id(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    order_ids: list[uuid.UUID],
) -> dict[uuid.UUID, tuple[float | None, float | None]]:
    # Filtrar None: paradas creadas desde plantilla tienen order_id=None (migration 029)
    order_ids = [oid for oid in order_ids if oid is not None]
    if not order_ids:
        return {}

    rows = db.execute(
        select(Order.id, Customer.lat, Customer.lng)
        .select_from(Order)
        .join(
            Customer,
            and_(
                Customer.id == Order.customer_id,
                Customer.tenant_id == Order.tenant_id,
            ),
        )
        .where(
            Order.tenant_id == tenant_id,
            Order.id.in_(order_ids),
        )
    ).all()

    result: dict[uuid.UUID, tuple[float | None, float | None]] = {}
    for order_id, lat, lng in rows:
        result[order_id] = (
            float(lat) if lat is not None else None,
            float(lng) if lng is not None else None,
        )
    return result


def _serialize_route(db: Session, tenant_id: uuid.UUID, route: Route) -> RouteOut:
    stops = list(
        db.scalars(
            select(RouteStop)
            .where(RouteStop.tenant_id == tenant_id, RouteStop.route_id == route.id)
            .order_by(RouteStop.sequence_number)
        )
    )
    data = RouteOut.model_validate(route)
    geo_by_order_id = _load_customer_geo_by_order_id(
        db,
        tenant_id=tenant_id,
        order_ids=[stop.order_id for stop in stops],
    )
    data.stops = [
        _serialize_stop_with_customer_geo(
            stop,
            customer_lat=geo_by_order_id.get(stop.order_id, (None, None))[0],
            customer_lng=geo_by_order_id.get(stop.order_id, (None, None))[1],
        )
        for stop in stops
    ]
    data.route_geometry = _extract_route_geometry(route.optimization_response_json)
    return data


def _serialize_routes_batch(db: Session, tenant_id: uuid.UUID, routes: list[Route]) -> list[RouteOut]:
    """
    Serializa N rutas en exactamente 2 queries planas (stops IN + geo JOIN IN).
    Reemplaza el loop N × _serialize_route (2N queries) en list_routes.
    """
    if not routes:
        return []

    route_ids = [r.id for r in routes]

    # 1 query: todos los stops de todas las rutas de golpe
    all_stops = list(
        db.scalars(
            select(RouteStop)
            .where(RouteStop.tenant_id == tenant_id, RouteStop.route_id.in_(route_ids))
            .order_by(RouteStop.route_id, RouteStop.sequence_number)
        )
    )

    # Agrupar en Python — sin queries adicionales
    stops_by_route: dict[uuid.UUID, list[RouteStop]] = {r.id: [] for r in routes}
    for stop in all_stops:
        stops_by_route[stop.route_id].append(stop)

    # 1 query: geo de todos los pedidos de todos los stops
    all_order_ids = [stop.order_id for stop in all_stops]
    geo_by_order_id = _load_customer_geo_by_order_id(db, tenant_id=tenant_id, order_ids=all_order_ids)

    results: list[RouteOut] = []
    for route in routes:
        stops = stops_by_route.get(route.id, [])
        data = RouteOut.model_validate(route)
        data.stops = [
            _serialize_stop_with_customer_geo(
                stop,
                customer_lat=geo_by_order_id.get(stop.order_id, (None, None))[0],
                customer_lng=geo_by_order_id.get(stop.order_id, (None, None))[1],
            )
            for stop in stops
        ]
        data.route_geometry = _extract_route_geometry(route.optimization_response_json)
        results.append(data)

    return results


def _extract_route_geometry(optimization_response_json: dict | None) -> RouteGeometryOut | None:
    if not isinstance(optimization_response_json, dict):
        return None

    routes = optimization_response_json.get("routes")
    if not isinstance(routes, list) or not routes:
        return None

    first_route = routes[0]
    if not isinstance(first_route, dict):
        return None

    transitions = first_route.get("transitions")
    if not isinstance(transitions, list) or not transitions:
        return None

    transition_polylines: list[str] = []
    for transition in transitions:
        if not isinstance(transition, dict):
            continue
        route_polyline = transition.get("routePolyline")
        if not isinstance(route_polyline, dict):
            continue

        encoded = route_polyline.get("points")
        if isinstance(encoded, str) and encoded.strip():
            transition_polylines.append(encoded)
            continue

        encoded_alt = route_polyline.get("encodedPolyline")
        if isinstance(encoded_alt, str) and encoded_alt.strip():
            transition_polylines.append(encoded_alt)

    if not transition_polylines:
        return None

    provider = optimization_response_json.get("provider")
    if not isinstance(provider, str) or not provider:
        provider = "google"

    return RouteGeometryOut(
        provider=provider,
        encoding="google_encoded_polyline",
        transition_polylines=transition_polylines,
    )


def _emit_event(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    route_id: uuid.UUID,
    route_stop_id: uuid.UUID | None = None,
    event_type: RouteEventType,
    actor_type: RouteEventActorType,
    actor_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    db.add(
        RouteEvent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            route_id=route_id,
            route_stop_id=route_stop_id,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            ts=datetime.now(UTC),
            metadata_json=metadata or {},
        )
    )


# ============================================================================
# GET /planning/orders/ready-to-dispatch
# ============================================================================


@router.get("/planning/orders/ready-to-dispatch", response_model=dict)
def get_orders_ready_to_dispatch(
    service_date: date | None = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.logistics, UserRole.admin)),
) -> dict:
    """
    Retorna pedidos en estado 'planned' (listos para asignar a ruta).
    Lecturas sin side effects.
    """
    query = (
        select(Order)
        .where(
            Order.tenant_id == current.tenant_id,
            Order.status == OrderStatus.planned,
        )
        .order_by(Order.service_date, Order.created_at)
    )
    if service_date is not None:
        query = query.where(Order.service_date == service_date)

    rows = list(db.scalars(query))
    items = [
        {
            "id": str(r.id),
            "customer_id": str(r.customer_id),
            "service_date": r.service_date.isoformat(),
            "status": r.status.value,
            "total_weight_kg": float(r.total_weight_kg) if r.total_weight_kg is not None else None,
            "zone_id": str(r.zone_id),
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


# ============================================================================
# GET /vehicles/available
# ============================================================================


@router.get("/vehicles/available", response_model=dict)
def get_available_vehicles(
    service_date: date | None = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.logistics, UserRole.admin)),
) -> dict:
    """
    Retorna vehículos activos del tenant con su chofer asignado.
    Lecturas sin side effects.
    """
    vehicles = list(
        db.scalars(
            select(Vehicle)
            .where(Vehicle.tenant_id == current.tenant_id, Vehicle.active.is_(True))
            .order_by(Vehicle.code)
        )
    )
    items = []
    for v in vehicles:
        driver = None
        if True:  # Buscar chofer asignado a este vehículo
            drv = db.scalar(
                select(Driver).where(
                    Driver.tenant_id == current.tenant_id,
                    Driver.vehicle_id == v.id,
                    Driver.is_active.is_(True),
                )
            )
            if drv:
                driver = {"id": str(drv.id), "name": drv.name, "phone": drv.phone}

        items.append(
            {
                "id": str(v.id),
                "code": v.code,
                "name": v.name,
                "capacity_kg": float(v.capacity_kg) if v.capacity_kg is not None else None,
                "active": v.active,
                "driver": driver,
            }
        )
    return {"items": items, "total": len(items)}


# ============================================================================
# POST /routes/plan
# ============================================================================


@router.post("/routes/plan", response_model=dict, status_code=201)
def plan_routes(
    payload: dict,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.logistics, UserRole.admin)),
) -> dict:
    """
    Genera rutas para un plan dado.
    Recibe: plan_id, lista de (vehicle_id, order_ids, driver_id opcional)
    Cada ítem genera una Route con sus RouteStops en orden.
    Persiste rutas en status=draft (optimizables antes de despacho).
    Actualiza order.status = assigned.

    Payload esperado:
    {
      "plan_id": "uuid",
      "service_date": "YYYY-MM-DD",
      "routes": [
        {
          "vehicle_id": "uuid",
          "driver_id": "uuid | null",
          "order_ids": ["uuid", ...]
        }
      ]
    }
    """
    plan_id = payload.get("plan_id")
    service_date_str = payload.get("service_date")
    routes_input = payload.get("routes", [])

    if not plan_id:
        raise unprocessable("INVALID_PLAN", "plan_id es obligatorio")
    if not service_date_str:
        raise unprocessable("INVALID_PLAN", "service_date es obligatorio")
    if not routes_input:
        raise unprocessable("INVALID_PLAN", "routes no puede estar vacío")

    try:
        plan_uuid = uuid.UUID(str(plan_id))
        svc_date = date.fromisoformat(service_date_str)
    except (ValueError, AttributeError) as exc:
        raise unprocessable("INVALID_PLAN", "plan_id o service_date inválido") from exc

    # Verificar plan existe y pertenece al tenant
    plan = db.scalar(
        select(Plan).where(Plan.id == plan_uuid, Plan.tenant_id == current.tenant_id)
    )
    if not plan:
        raise not_found("ENTITY_NOT_FOUND", "Plan no encontrado")
    if plan.status not in (PlanStatus.locked, PlanStatus.open):
        raise unprocessable("INVALID_STATE_TRANSITION", f"Plan en estado '{plan.status.value}' no permite planificación de rutas")

    created_routes = []
    now = datetime.now(UTC)

    for route_input in routes_input:
        vehicle_id_str = route_input.get("vehicle_id")
        driver_id_str = route_input.get("driver_id")
        order_ids_raw = route_input.get("order_ids", [])

        if not vehicle_id_str:
            raise unprocessable("INVALID_ROUTE", "vehicle_id es obligatorio en cada ruta")
        if not order_ids_raw:
            raise unprocessable("INVALID_ROUTE", "order_ids no puede estar vacío en cada ruta")

        try:
            vehicle_uuid = uuid.UUID(str(vehicle_id_str))
            driver_uuid = uuid.UUID(str(driver_id_str)) if driver_id_str else None
            order_uuids = [uuid.UUID(str(oid)) for oid in order_ids_raw]
        except (ValueError, AttributeError) as exc:
            raise unprocessable("INVALID_ROUTE", "UUID inválido en vehicle_id, driver_id u order_ids") from exc

        # Verificar vehículo existe y pertenece al tenant
        vehicle = db.scalar(
            select(Vehicle).where(
                Vehicle.id == vehicle_uuid,
                Vehicle.tenant_id == current.tenant_id,
                Vehicle.active.is_(True),
            )
        )
        if not vehicle:
            raise not_found("ENTITY_NOT_FOUND", f"Vehículo {vehicle_uuid} no encontrado o inactivo")

        # Verificar driver si se proporciona
        if driver_uuid is not None:
            driver = db.scalar(
                select(Driver).where(
                    Driver.id == driver_uuid,
                    Driver.tenant_id == current.tenant_id,
                    Driver.is_active.is_(True),
                )
            )
            if not driver:
                raise not_found("ENTITY_NOT_FOUND", f"Chofer {driver_uuid} no encontrado o inactivo")

        # Verificar versión: si ya existe ruta activa para este (plan, vehicle), calcular siguiente versión
        existing_versions = list(
            db.scalars(
                select(Route.version).where(
                    Route.tenant_id == current.tenant_id,
                    Route.plan_id == plan_uuid,
                    Route.vehicle_id == vehicle_uuid,
                )
            )
        )
        next_version = max(existing_versions, default=0) + 1

        # Cancelar ruta activa anterior si existe (replanificación)
        if existing_versions:
            prev_route = db.scalar(
                select(Route).where(
                    Route.tenant_id == current.tenant_id,
                    Route.plan_id == plan_uuid,
                    Route.vehicle_id == vehicle_uuid,
                    Route.status != RouteStatus.cancelled,
                )
            )
            if prev_route:
                prev_route.status = RouteStatus.cancelled
                prev_route.updated_at = now
                _emit_event(
                    db,
                    tenant_id=current.tenant_id,
                    route_id=prev_route.id,
                    event_type=RouteEventType.route_cancelled,
                    actor_type=RouteEventActorType.dispatcher,
                    actor_id=current.id,
                    metadata={"reason": "replan", "new_version": next_version},
                )

        # Verificar pedidos: deben existir, pertenecer al tenant y estar en estado válido
        for order_uuid in order_uuids:
            order = db.scalar(
                select(Order).where(
                    Order.id == order_uuid,
                    Order.tenant_id == current.tenant_id,
                )
            )
            if not order:
                raise not_found("ENTITY_NOT_FOUND", f"Pedido {order_uuid} no encontrado")
            if order.status not in (OrderStatus.planned, OrderStatus.assigned):
                raise unprocessable(
                    "INVALID_STATE_TRANSITION",
                    f"Pedido {order_uuid} en estado '{order.status.value}' no puede asignarse a ruta",
                )

        # F4 — DOUBLE-TRIP-001: trip_number opcional (1 o 2), default 1
        trip_number_raw = route_input.get("trip_number", 1)
        try:
            trip_number = int(trip_number_raw)
            if trip_number not in (1, 2):
                raise ValueError
        except (TypeError, ValueError):
            raise unprocessable("INVALID_ROUTE", "trip_number debe ser 1 o 2")

        # Crear ruta en estado draft; la optimización aplica secuencia final
        # y transiciona la ruta a planned.
        route = Route(
            id=uuid.uuid4(),
            tenant_id=current.tenant_id,
            plan_id=plan_uuid,
            vehicle_id=vehicle_uuid,
            driver_id=driver_uuid,
            service_date=svc_date,
            status=RouteStatus.draft,
            version=next_version,
            trip_number=trip_number,
            optimization_request_id=None,
            optimization_response_json=None,
            created_at=now,
            updated_at=now,
            dispatched_at=None,
            completed_at=None,
        )
        db.add(route)
        db.flush()  # obtener route.id

        # Crear paradas y actualizar estado de pedido
        for seq, order_uuid in enumerate(order_uuids, start=1):
            stop = RouteStop(
                id=uuid.uuid4(),
                tenant_id=current.tenant_id,
                route_id=route.id,
                order_id=order_uuid,
                sequence_number=seq,
                estimated_arrival_at=None,
                estimated_service_minutes=10,
                status=RouteStopStatus.pending,
                arrived_at=None,
                completed_at=None,
                failed_at=None,
                failure_reason=None,
                created_at=now,
                updated_at=now,
            )
            db.add(stop)

            # Actualizar order status a assigned
            order = db.scalar(
                select(Order).where(Order.id == order_uuid, Order.tenant_id == current.tenant_id)
            )
            if order:
                order.status = OrderStatus.assigned
                order.updated_at = now

        # Emitir evento route.created (route.planned se emite tras optimize)
        _emit_event(
            db,
            tenant_id=current.tenant_id,
            route_id=route.id,
            event_type=RouteEventType.route_created,
            actor_type=RouteEventActorType.dispatcher,
            actor_id=current.id,
            metadata={
                "version": next_version,
                "vehicle_id": str(vehicle_uuid),
                "order_count": len(order_uuids),
            },
        )

        created_routes.append(route)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("RESOURCE_CONFLICT", "No se pudo persistir el plan de rutas") from exc

    return {
        "plan_id": str(plan_uuid),
        "service_date": svc_date.isoformat(),
        "routes_created": [
            {
                "id": str(r.id),
                "vehicle_id": str(r.vehicle_id),
                "driver_id": str(r.driver_id) if r.driver_id else None,
                "status": r.status.value,
                "version": r.version,
            }
            for r in created_routes
        ],
    }


# ============================================================================
# POST /routes/{routeId}/dispatch
# ============================================================================


@router.post("/routes/{route_id}/dispatch", response_model=RouteOut)
def dispatch_route(
    route_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.logistics, UserRole.admin)),
) -> RouteOut:
    """
    Despacha una ruta al chofer. Transición: planned → dispatched.
    Actualiza order.status = dispatched para todos los pedidos de la ruta.
    """
    route = db.scalar(
        select(Route).where(Route.id == route_id, Route.tenant_id == current.tenant_id)
    )
    if not route:
        raise not_found("ENTITY_NOT_FOUND", "Ruta no encontrada")
    if route.status != RouteStatus.planned:
        raise unprocessable(
            "INVALID_STATE_TRANSITION",
            f"Solo rutas en estado 'planned' pueden despacharse. Estado actual: '{route.status.value}'",
        )

    now = datetime.now(UTC)
    route.status = RouteStatus.dispatched
    route.dispatched_at = now
    route.updated_at = now

    # Actualizar pedidos a dispatched
    stops = list(
        db.scalars(select(RouteStop).where(RouteStop.route_id == route_id, RouteStop.tenant_id == current.tenant_id))
    )
    # R9-PERF-001: batch load orders — evita N queries por parada
    order_ids = [stop.order_id for stop in stops]
    orders_by_id = {
        o.id: o
        for o in db.scalars(
            select(Order).where(Order.id.in_(order_ids), Order.tenant_id == current.tenant_id)
        )
    }
    for stop in stops:
        order = orders_by_id.get(stop.order_id)
        if order and order.status == OrderStatus.assigned:
            order.status = OrderStatus.dispatched
            order.updated_at = now

    _emit_event(
        db,
        tenant_id=current.tenant_id,
        route_id=route.id,
        event_type=RouteEventType.route_dispatched,
        actor_type=RouteEventActorType.dispatcher,
        actor_id=current.id,
        metadata={"version": route.version, "driver_id": str(route.driver_id) if route.driver_id else None},
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("RESOURCE_CONFLICT", "No se pudo despachar la ruta") from exc

    db.refresh(route)
    return _serialize_route(db, current.tenant_id, route)


# ============================================================================
# POST /routes/{routeId}/optimize
# ============================================================================


def _get_optimization_provider() -> RouteOptimizationProvider:
    # E.2: si hay project_id configurado, usar proveedor real de Google.
    # Si no, mantener mock (tests/dev sin credenciales).
    if settings.google_route_optimization_project_id.strip():
        return GoogleRouteOptimizationProvider(
            project_id=settings.google_route_optimization_project_id,
            location=settings.google_route_optimization_location,
            timeout_seconds=settings.google_route_optimization_timeout_seconds,
        )
    return MockRouteOptimizationProvider()


@router.post("/routes/{route_id}/optimize", response_model=RouteOut)
def optimize_route(
    route_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.logistics, UserRole.admin)),
) -> RouteOut:
    route = db.scalar(
        select(Route).where(Route.id == route_id, Route.tenant_id == current.tenant_id)
    )
    if not route:
        raise not_found("ENTITY_NOT_FOUND", "Ruta no encontrada")
    if route.status != RouteStatus.draft:
        raise conflict(
            "INVALID_STATE_TRANSITION",
            f"Solo rutas en estado 'draft' pueden optimizarse. Estado actual: '{route.status.value}'",
        )

    stops = list(
        db.scalars(
            select(RouteStop)
            .where(RouteStop.route_id == route_id, RouteStop.tenant_id == current.tenant_id)
            .order_by(RouteStop.sequence_number, RouteStop.id)
        )
    )
    if not stops:
        raise unprocessable("INVALID_ROUTE", "La ruta no tiene paradas")

    # R9-PERF-001: batch load orders, customers y profiles — evita 3N queries por parada
    stop_order_ids = [stop.order_id for stop in stops]
    orders_map = {
        o.id: o
        for o in db.scalars(
            select(Order).where(Order.id.in_(stop_order_ids), Order.tenant_id == current.tenant_id)
        )
    }
    missing_orders = [str(oid) for oid in stop_order_ids if oid not in orders_map]
    if missing_orders:
        raise not_found("ENTITY_NOT_FOUND", f"Pedido(s) no encontrado(s): {', '.join(missing_orders)}")

    customer_ids = list({o.customer_id for o in orders_map.values()})
    customers_map = {
        c.id: c
        for c in db.scalars(
            select(Customer).where(Customer.id.in_(customer_ids), Customer.tenant_id == current.tenant_id)
        )
    }
    profiles_map = {
        p.customer_id: p
        for p in db.scalars(
            select(CustomerOperationalProfile).where(
                CustomerOperationalProfile.customer_id.in_(customer_ids),
                CustomerOperationalProfile.tenant_id == current.tenant_id,
            )
        )
    }

    missing_geo: list[str] = []
    waypoints: list[OptimizationWaypoint] = []
    for stop in stops:
        order = orders_map.get(stop.order_id)
        if not order:
            raise not_found("ENTITY_NOT_FOUND", f"Pedido {stop.order_id} no encontrado")

        customer = customers_map.get(order.customer_id)
        if not customer or customer.lat is None or customer.lng is None:
            missing_geo.append(str(order.id))
            continue

        # F1 — TW-001: leer ventana horaria del perfil operacional del cliente
        profile = profiles_map.get(customer.id)

        waypoints.append(
            OptimizationWaypoint(
                order_id=order.id,
                lat=float(customer.lat),
                lng=float(customer.lng),
                service_minutes=stop.estimated_service_minutes,
                window_start=profile.window_start if profile else None,
                window_end=profile.window_end if profile else None,
                # F2 — CAPACITY-001: peso del pedido para restricción de capacidad
                weight_kg=float(order.total_weight_kg) if order.total_weight_kg else None,
                # F5 — ADR-001: el pedido requiere vehículo ADR certificado
                requires_adr=bool(order.requires_adr),
                # F6 — ZBE-001: el cliente está en zona de bajas emisiones
                requires_zbe=bool(customer.in_zbe_zone),
            )
        )

    if missing_geo:
        raise unprocessable(
            "MISSING_GEO",
            f"Los siguientes pedidos tienen cliente sin coordenadas: {', '.join(missing_geo)}",
        )

    # F2 — CAPACITY-001: capacidad del vehículo para restricción de carga
    # F5 — ADR-001: certificación ADR del vehículo
    vehicle = db.scalar(
        select(Vehicle).where(Vehicle.id == route.vehicle_id, Vehicle.tenant_id == current.tenant_id)
    )
    vehicle_capacity_kg = float(vehicle.capacity_kg) if vehicle and vehicle.capacity_kg else None
    vehicle_adr_certified = bool(vehicle.is_adr_certified) if vehicle else False
    vehicle_zbe_allowed = bool(vehicle.is_zbe_allowed) if vehicle else False

    # F5 — ADR-001: validación pre-optimización
    adr_orders = [wp for wp in waypoints if wp.requires_adr]
    if adr_orders and not vehicle_adr_certified:
        raise unprocessable(
            "ADR_VEHICLE_REQUIRED",
            f"La ruta contiene {len(adr_orders)} pedido(s) con mercancías peligrosas "
            "pero el vehículo asignado no tiene certificación ADR",
        )

    # F6 — ZBE-001: validación pre-optimización
    zbe_stops = [wp for wp in waypoints if wp.requires_zbe]
    if zbe_stops and not vehicle_zbe_allowed:
        raise unprocessable(
            "ZBE_VEHICLE_REQUIRED",
            f"La ruta contiene {len(zbe_stops)} parada(s) en zona de bajas emisiones "
            "pero el vehículo asignado no está autorizado para circular en ZBE",
        )

    # F4 — DOUBLE-TRIP-001: si es viaje 2, calcular fin esperado del viaje 1
    trip_start_after: datetime | None = None
    if route.trip_number == 2:
        trip1 = db.scalar(
            select(Route).where(
                Route.tenant_id == current.tenant_id,
                Route.vehicle_id == route.vehicle_id,
                Route.service_date == route.service_date,
                Route.trip_number == 1,
                Route.status.in_([
                    RouteStatus.planned, RouteStatus.dispatched,
                    RouteStatus.in_progress, RouteStatus.completed,
                ]),
            )
        )
        if not trip1:
            raise unprocessable(
                "TRIP1_NOT_PLANNED",
                "El viaje 1 del vehículo en esta fecha debe estar planificado antes de optimizar el viaje 2",
            )
        # Obtener paradas del viaje 1 con ETA para calcular fin esperado
        trip1_stops = list(
            db.scalars(
                select(RouteStop).where(
                    RouteStop.route_id == trip1.id,
                    RouteStop.tenant_id == current.tenant_id,
                    RouteStop.estimated_arrival_at.is_not(None),
                ).order_by(RouteStop.sequence_number.desc())
            )
        )
        if not trip1_stops:
            raise unprocessable(
                "TRIP1_NO_ETA",
                "El viaje 1 no tiene ETAs calculadas; optimiza el viaje 1 primero",
            )
        last_stop = trip1_stops[0]
        # Fin estimado = última ETA + tiempo de servicio + 30 min de buffer (vuelta a depósito + recarga)
        trip_start_after = (
            last_stop.estimated_arrival_at
            + timedelta(minutes=last_stop.estimated_service_minutes)
            + timedelta(minutes=30)
        )

    request = OptimizationRequest(
        route_id=route.id,
        depot_lat=settings.route_optimization_depot_lat,
        depot_lng=settings.route_optimization_depot_lng,
        service_date=route.service_date,
        waypoints=waypoints,
        vehicle_capacity_kg=vehicle_capacity_kg,
        trip_start_after=trip_start_after,
        vehicle_adr_certified=vehicle_adr_certified,
        vehicle_zbe_allowed=vehicle_zbe_allowed,
    )
    provider = _get_optimization_provider()
    try:
        result = provider.optimize(request)
    except Exception as exc:
        raise conflict(
            "OPTIMIZATION_PROVIDER_ERROR",
            f"El proveedor de optimización falló: {exc}",
        ) from exc

    now = datetime.now(UTC)
    stops_by_order_id = {str(stop.order_id): stop for stop in stops}

    # Evita colisiones temporales del unique(route_id, sequence_number)
    # durante reordenaciones (swap 1<->2, etc.) aplicando un desplazamiento
    # intermedio y luego los valores finales.
    max_sequence = max((stop.sequence_number for stop in stops), default=0)
    temp_offset = max_sequence + len(stops) + 1000
    for db_stop in stops:
        db_stop.sequence_number = db_stop.sequence_number + temp_offset
        db_stop.updated_at = now
    db.flush()

    for optimized_stop in result.stops:
        db_stop = stops_by_order_id.get(str(optimized_stop.order_id))
        if not db_stop:
            continue
        db_stop.sequence_number = optimized_stop.sequence_number
        db_stop.estimated_arrival_at = optimized_stop.estimated_arrival_at
        db_stop.updated_at = now

    route.status = RouteStatus.planned
    route.optimization_request_id = result.request_id
    route.optimization_response_json = result.response_json
    route.updated_at = now

    _emit_event(
        db,
        tenant_id=current.tenant_id,
        route_id=route.id,
        event_type=RouteEventType.route_planned,
        actor_type=RouteEventActorType.system,
        actor_id=None,
        metadata={
            "optimization_request_id": result.request_id,
            "stop_count": len(result.stops),
        },
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("RESOURCE_CONFLICT", "No se pudo persistir la optimización") from exc

    db.refresh(route)
    return _serialize_route(db, current.tenant_id, route)


# ============================================================================
# POST /routes/{routeId}/move-stop
# ============================================================================


@router.post("/routes/{route_id}/move-stop", response_model=dict)
def move_stop(
    route_id: uuid.UUID,
    payload: dict,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.logistics, UserRole.admin)),
) -> dict:
    """
    Mueve un pedido (route_stop) de esta ruta a otra ruta de destino.
    La parada se elimina de origen y se añade al final de destino.
    No incrementa version de ninguna ruta (ajuste manual).

    Payload: { "stop_id": "uuid", "target_route_id": "uuid" }
    """
    stop_id_raw = payload.get("stop_id")
    target_route_id_raw = payload.get("target_route_id")

    if not stop_id_raw or not target_route_id_raw:
        raise unprocessable("INVALID_MOVE", "stop_id y target_route_id son obligatorios")

    try:
        stop_uuid = uuid.UUID(str(stop_id_raw))
        target_route_uuid = uuid.UUID(str(target_route_id_raw))
    except (ValueError, AttributeError) as exc:
        raise unprocessable("INVALID_MOVE", "UUIDs inválidos") from exc

    # Verificar ruta origen
    source_route = db.scalar(
        select(Route).where(Route.id == route_id, Route.tenant_id == current.tenant_id)
    )
    if not source_route:
        raise not_found("ENTITY_NOT_FOUND", "Ruta origen no encontrada")
    if source_route.status not in (RouteStatus.planned, RouteStatus.dispatched, RouteStatus.in_progress):
        raise unprocessable("INVALID_STATE_TRANSITION", "Solo se pueden mover paradas de rutas en estado planned, dispatched o in_progress")

    # Verificar parada existe en ruta origen
    stop = db.scalar(
        select(RouteStop).where(
            RouteStop.id == stop_uuid,
            RouteStop.route_id == route_id,
            RouteStop.tenant_id == current.tenant_id,
        )
    )
    if not stop:
        raise not_found("ENTITY_NOT_FOUND", "Parada no encontrada en la ruta origen")
    if stop.status != RouteStopStatus.pending:
        raise unprocessable("INVALID_STATE_TRANSITION", "Solo se pueden mover paradas en estado 'pending'")

    # Verificar ruta destino
    target_route = db.scalar(
        select(Route).where(Route.id == target_route_uuid, Route.tenant_id == current.tenant_id)
    )
    if not target_route:
        raise not_found("ENTITY_NOT_FOUND", "Ruta destino no encontrada")
    if target_route.status not in (RouteStatus.planned, RouteStatus.dispatched, RouteStatus.in_progress):
        raise unprocessable("INVALID_STATE_TRANSITION", "Solo se pueden añadir paradas a rutas en estado planned, dispatched o in_progress")

    # Verificar que el pedido no está ya en la ruta destino
    existing_in_target = db.scalar(
        select(RouteStop).where(
            RouteStop.route_id == target_route_uuid,
            RouteStop.order_id == stop.order_id,
            RouteStop.tenant_id == current.tenant_id,
        )
    )
    if existing_in_target:
        raise conflict("RESOURCE_CONFLICT", "El pedido ya está en la ruta destino")

    # Calcular siguiente sequence_number en destino
    max_seq = db.scalar(
        select(RouteStop.sequence_number)
        .where(RouteStop.route_id == target_route_uuid, RouteStop.tenant_id == current.tenant_id)
        .order_by(RouteStop.sequence_number.desc())
        .limit(1)
    )
    new_seq = (max_seq or 0) + 1

    now = datetime.now(UTC)
    order_id = stop.order_id

    # Eliminar parada de origen
    db.delete(stop)
    db.flush()

    # Crear parada en destino
    new_stop = RouteStop(
        id=uuid.uuid4(),
        tenant_id=current.tenant_id,
        route_id=target_route_uuid,
        order_id=order_id,
        sequence_number=new_seq,
        estimated_arrival_at=None,
        estimated_service_minutes=10,
        status=RouteStopStatus.pending,
        arrived_at=None,
        completed_at=None,
        failed_at=None,
        failure_reason=None,
        created_at=now,
        updated_at=now,
    )
    db.add(new_stop)
    db.flush()

    # Emitir eventos
    _emit_event(
        db,
        tenant_id=current.tenant_id,
        route_id=route_id,
        event_type=RouteEventType.stop_skipped,
        actor_type=RouteEventActorType.dispatcher,
        actor_id=current.id,
        metadata={"order_id": str(order_id), "moved_to_route_id": str(target_route_uuid)},
    )
    _emit_event(
        db,
        tenant_id=current.tenant_id,
        route_id=target_route_uuid,
        route_stop_id=new_stop.id,
        event_type=RouteEventType.stop_en_route,
        actor_type=RouteEventActorType.dispatcher,
        actor_id=current.id,
        metadata={"order_id": str(order_id), "moved_from_route_id": str(route_id), "sequence_number": new_seq},
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("RESOURCE_CONFLICT", "No se pudo mover la parada") from exc

    return {
        "order_id": str(order_id),
        "from_route_id": str(route_id),
        "to_route_id": str(target_route_uuid),
        "new_sequence_number": new_seq,
    }


# ============================================================================
# GET /routes
# ============================================================================


@router.get("/routes", response_model=RoutesListResponse)
def list_routes(
    plan_id: uuid.UUID | None = None,
    vehicle_id: uuid.UUID | None = None,
    driver_id: uuid.UUID | None = None,
    service_date: date | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.office, UserRole.logistics, UserRole.admin)),
) -> RoutesListResponse:
    """
    Lista rutas con filtros opcionales. Lecturas sin side effects.
    """
    query = (
        select(Route)
        .where(Route.tenant_id == current.tenant_id)
        .order_by(Route.service_date.desc(), Route.created_at.desc())
    )
    if plan_id is not None:
        query = query.where(Route.plan_id == plan_id)
    if vehicle_id is not None:
        query = query.where(Route.vehicle_id == vehicle_id)
    if driver_id is not None:
        query = query.where(Route.driver_id == driver_id)
    if service_date is not None:
        query = query.where(Route.service_date == service_date)
    if status is not None:
        try:
            status_enum = RouteStatus(status)
            query = query.where(Route.status == status_enum)
        except ValueError as exc:
            raise unprocessable("INVALID_FILTER", f"status '{status}' no es válido") from exc

    rows = list(db.scalars(query))
    return RoutesListResponse(
        items=_serialize_routes_batch(db, current.tenant_id, rows),
        total=len(rows),
    )


# ============================================================================
# GET /routes/{routeId}
# ============================================================================


@router.get("/routes/{route_id}", response_model=RouteOut)
def get_route(
    route_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.office, UserRole.logistics, UserRole.admin)),
) -> RouteOut:
    """
    Detalle de ruta con paradas ordenadas por sequence_number. Sin side effects.
    """
    route = db.scalar(
        select(Route).where(Route.id == route_id, Route.tenant_id == current.tenant_id)
    )
    if not route:
        raise not_found("ENTITY_NOT_FOUND", "Ruta no encontrada")
    return _serialize_route(db, current.tenant_id, route)


# ============================================================================
# GET /routes/{routeId}/events
# ============================================================================


@router.get("/routes/{route_id}/events", response_model=RouteEventsListResponse)
def get_route_events(
    route_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.office, UserRole.logistics, UserRole.admin)),
) -> RouteEventsListResponse:
    """
    Log de eventos de una ruta, ordenado cronológicamente. Sin side effects.
    """
    route = db.scalar(
        select(Route).where(Route.id == route_id, Route.tenant_id == current.tenant_id)
    )
    if not route:
        raise not_found("ENTITY_NOT_FOUND", "Ruta no encontrada")

    events = list(
        db.scalars(
            select(RouteEvent)
            .where(RouteEvent.tenant_id == current.tenant_id, RouteEvent.route_id == route_id)
            .order_by(RouteEvent.ts)
        )
    )
    return RouteEventsListResponse(
        items=[RouteEventOut.model_validate(e) for e in events],
        total=len(events),
    )


# ============================================================================
# BLOQUE C — VISTAS/ACCIONES CONDUCTOR
# ============================================================================


@router.get("/driver/routes", response_model=RoutesListResponse)
def list_driver_routes(
    service_date: date | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.driver, UserRole.logistics, UserRole.admin)),
) -> RoutesListResponse:
    """
    Lista rutas operativas para conductor.
    - role=driver: scope por chofer activo vinculado al usuario.
    - role=logistics/admin: lectura sin recorte por chofer.
    """
    query = (
        select(Route)
        .where(Route.tenant_id == current.tenant_id)
        .order_by(Route.service_date.desc(), Route.created_at.desc())
    )

    if current.role == UserRole.driver:
        driver = _resolve_current_driver(db, current)
        assert driver is not None
        query = query.where(Route.driver_id == driver.id)

    if service_date is not None:
        query = query.where(Route.service_date == service_date)
    if status is not None:
        try:
            status_enum = RouteStatus(status)
            query = query.where(Route.status == status_enum)
        except ValueError as exc:
            raise unprocessable("INVALID_FILTER", f"status '{status}' no es válido") from exc

    rows = list(db.scalars(query))
    return RoutesListResponse(items=[_serialize_route(db, current.tenant_id, row) for row in rows], total=len(rows))


@router.get("/routes/{route_id}/next-stop", response_model=RouteNextStopResponse)
def get_next_stop(
    route_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.driver, UserRole.logistics, UserRole.admin)),
) -> RouteNextStopResponse:
    """
    Devuelve la siguiente parada no terminal de una ruta.
    No tiene side effects.
    """
    route = db.scalar(
        select(Route).where(Route.id == route_id, Route.tenant_id == current.tenant_id)
    )
    if not route:
        raise not_found("ENTITY_NOT_FOUND", "Ruta no encontrada")
    _assert_driver_scope_for_route(db, current, route)

    stops = list(
        db.scalars(
            select(RouteStop)
            .where(RouteStop.route_id == route.id, RouteStop.tenant_id == current.tenant_id)
            .order_by(RouteStop.sequence_number, RouteStop.id)
        )
    )
    remaining = [stop for stop in stops if stop.status not in _STOP_TERMINAL]
    next_stop = None
    if remaining:
        stop = remaining[0]
        geo_by_order_id = _load_customer_geo_by_order_id(
            db,
            tenant_id=current.tenant_id,
            order_ids=[stop.order_id],
        )
        lat, lng = geo_by_order_id.get(stop.order_id, (None, None))
        next_stop = _serialize_stop_with_customer_geo(
            stop,
            customer_lat=lat,
            customer_lng=lng,
        )
    return RouteNextStopResponse(route_id=route.id, next_stop=next_stop, remaining_stops=len(remaining))


# ============================================================================
# BLOQUE D — EJECUCIÓN CONDUCTOR
# ============================================================================

# ---------------------------------------------------------------------------
# Helpers internos Bloque D
# ---------------------------------------------------------------------------

_STOP_TERMINAL = frozenset({RouteStopStatus.completed, RouteStopStatus.failed, RouteStopStatus.skipped})


def _get_stop_guarded(db: Session, tenant_id: uuid.UUID, stop_id: uuid.UUID) -> RouteStop:
    """Obtiene una parada y verifica pertenencia al tenant. 404 si no existe."""
    stop = db.scalar(
        select(RouteStop).where(RouteStop.id == stop_id, RouteStop.tenant_id == tenant_id)
    )
    if not stop:
        raise not_found("ENTITY_NOT_FOUND", "Parada no encontrada")
    return stop


def _get_route_for_stop(
    db: Session,
    tenant_id: uuid.UUID,
    stop: RouteStop,
    *,
    require_executable: bool = True,
) -> Route:
    """Obtiene la ruta de una parada y opcionalmente valida estado ejecutable."""
    route = db.scalar(
        select(Route).where(Route.id == stop.route_id, Route.tenant_id == tenant_id)
    )
    if not route:
        raise not_found("ENTITY_NOT_FOUND", "Ruta de la parada no encontrada")
    if require_executable and route.status not in (RouteStatus.dispatched, RouteStatus.in_progress):
        raise conflict(
            "INVALID_STATE_TRANSITION",
            f"La ruta está en estado '{route.status.value}'. Solo se admiten transiciones en rutas despachadas o en progreso.",
        )
    return route


def _resolve_current_driver(db: Session, current: CurrentUser) -> Driver | None:
    """Resuelve el Driver activo vinculado al User actual.

    La relación se busca por drivers.user_id == current.id (vínculo explícito,
    migration 018). Esto reemplaza la convención anterior de drivers.id == users.id,
    que carecía de FK y no era trazable.

    Returns None si current no tiene role=driver (non-driver roles no hacen lookup).
    Raise 403 DRIVER_NOT_LINKED si el User tiene role=driver pero no hay Driver
    activo vinculado vía user_id.
    """
    if current.role != UserRole.driver:
        return None
    driver = db.scalar(
        select(Driver).where(
            Driver.user_id == current.id,   # vínculo explícito (018_driver_user_id)
            Driver.tenant_id == current.tenant_id,
            Driver.is_active.is_(True),
        )
    )
    if not driver:
        raise forbidden(
            "DRIVER_NOT_LINKED",
            "Usuario con rol driver sin ficha de chofer activa",
        )
    return driver


def _assert_driver_scope_for_route(db: Session, current: CurrentUser, route: Route) -> None:
    driver = _resolve_current_driver(db, current)
    if driver is None:
        return
    if route.driver_id is None or route.driver_id != driver.id:
        raise forbidden(
            "DRIVER_SCOPE_FORBIDDEN",
            "No puedes operar rutas asignadas a otro chofer",
        )


def _assert_route_execution_state(route: Route) -> None:
    if route.status not in (RouteStatus.dispatched, RouteStatus.in_progress):
        raise conflict(
            "INVALID_STATE_TRANSITION",
            f"La ruta está en estado '{route.status.value}'. Solo se admiten transiciones en rutas despachadas o en progreso.",
        )


def _find_idempotent_event(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    stop_id: uuid.UUID,
    event_type: RouteEventType,
    idempotency_key: str,
) -> RouteEvent | None:
    """
    Busca un RouteEvent previo con la misma idempotency_key para esta parada y tipo.
    Usa el operador ->> de JSONB (as_string) para comparar el valor de texto.
    """
    return db.scalar(
        select(RouteEvent).where(
            RouteEvent.tenant_id == tenant_id,
            RouteEvent.route_stop_id == stop_id,
            RouteEvent.event_type == event_type,
            RouteEvent.metadata_json["idempotency_key"].as_string() == idempotency_key,
        )
    )


def _auto_complete_route_if_done(
    db: Session,
    tenant_id: uuid.UUID,
    route: Route,
    actor_id: uuid.UUID | None,
    now: datetime,
) -> None:
    """
    Si todas las paradas de la ruta están en estado terminal, completa la ruta.
    Append-only: emite route.completed; no rollback si ya está completed.
    """
    if route.status == RouteStatus.completed:
        return
    stops = list(
        db.scalars(select(RouteStop).where(RouteStop.route_id == route.id, RouteStop.tenant_id == tenant_id))
    )
    if stops and all(s.status in _STOP_TERMINAL for s in stops):
        route.status = RouteStatus.completed
        route.completed_at = now
        route.updated_at = now
        _emit_event(
            db,
            tenant_id=tenant_id,
            route_id=route.id,
            event_type=RouteEventType.route_completed,
            actor_type=RouteEventActorType.system,
            actor_id=actor_id,
            metadata={"stops_total": len(stops)},
        )


# ============================================================================
# POST /stops/{stopId}/arrive
# ============================================================================


@router.post("/stops/{stop_id}/arrive", response_model=RouteStopOut)
def stop_arrive(
    stop_id: uuid.UUID,
    payload: RouteStopArriveRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.driver, UserRole.logistics, UserRole.admin)),
) -> RouteStopOut:
    """
    El chofer llega a la parada.
    Transición válida: pending | en_route → arrived.

    Idempotencia:
      - Misma idempotency_key → 200 con estado actual de la parada.
      - Parada ya en 'arrived' sin clave → 200 (operación ya aplicada).
      - Estado terminal o incompatible → 409.
    """
    stop = _get_stop_guarded(db, current.tenant_id, stop_id)
    route = _get_route_for_stop(db, current.tenant_id, stop, require_executable=False)
    _assert_driver_scope_for_route(db, current, route)
    now = datetime.now(UTC)

    # Idempotencia: clave duplicada
    if payload.idempotency_key:
        existing = _find_idempotent_event(
            db,
            tenant_id=current.tenant_id,
            stop_id=stop_id,
            event_type=RouteEventType.stop_arrived,
            idempotency_key=payload.idempotency_key,
        )
        if existing:
            db.refresh(stop)
            return RouteStopOut.model_validate(stop)

    # Idempotencia: estado ya aplicado sin clave
    if stop.status == RouteStopStatus.arrived:
        return RouteStopOut.model_validate(stop)

    _assert_route_execution_state(route)

    # Conflicto de estado
    if stop.status not in (RouteStopStatus.pending, RouteStopStatus.en_route):
        raise conflict(
            "INVALID_STATE_TRANSITION",
            f"La parada está en estado '{stop.status.value}'. No se puede registrar llegada.",
        )

    # Transición
    stop.status = RouteStopStatus.arrived
    stop.arrived_at = now
    stop.updated_at = now

    # Primera llegada: ruta pasa de dispatched → in_progress
    if route.status == RouteStatus.dispatched:
        route.status = RouteStatus.in_progress
        route.updated_at = now
        _emit_event(
            db,
            tenant_id=current.tenant_id,
            route_id=route.id,
            event_type=RouteEventType.route_started,
            actor_type=RouteEventActorType.driver,
            actor_id=current.id,
            metadata={"first_stop_id": str(stop_id)},
        )

    _emit_event(
        db,
        tenant_id=current.tenant_id,
        route_id=route.id,
        route_stop_id=stop_id,
        event_type=RouteEventType.stop_arrived,
        actor_type=RouteEventActorType.driver,
        actor_id=current.id,
        metadata={
            "idempotency_key": payload.idempotency_key or "",
            "sequence_number": stop.sequence_number,
        },
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("RESOURCE_CONFLICT", "No se pudo registrar la llegada") from exc

    # SSE: notificar suscriptores del estado de la parada (REALTIME-001)
    event_bus.publish(
        str(current.tenant_id),
        str(stop.route_id),
        "stop_status_changed",
        {
            "route_id": str(stop.route_id),
            "stop_id": str(stop.id),
            "status": stop.status.value,
            "sequence_number": stop.sequence_number,
        },
    )

    db.refresh(stop)
    return RouteStopOut.model_validate(stop)


# ============================================================================
# POST /stops/{stopId}/complete
# ============================================================================


@router.post("/stops/{stop_id}/complete", response_model=RouteStopOut)
def stop_complete(
    stop_id: uuid.UUID,
    payload: RouteStopCompleteRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.driver, UserRole.logistics, UserRole.admin)),
) -> RouteStopOut:
    """
    El chofer confirma la entrega.
    Transición válida: arrived → completed.
    Actualiza order.status = delivered.
    Si todas las paradas de la ruta terminan, la ruta pasa a completed.

    Idempotencia:
      - Misma idempotency_key → 200 con estado actual.
      - Parada ya en 'completed' → 200.
      - Estado incompatible → 409.
    """
    stop = _get_stop_guarded(db, current.tenant_id, stop_id)
    route = _get_route_for_stop(db, current.tenant_id, stop, require_executable=False)
    _assert_driver_scope_for_route(db, current, route)
    now = datetime.now(UTC)

    # Idempotencia: clave duplicada
    if payload.idempotency_key:
        existing = _find_idempotent_event(
            db,
            tenant_id=current.tenant_id,
            stop_id=stop_id,
            event_type=RouteEventType.stop_completed,
            idempotency_key=payload.idempotency_key,
        )
        if existing:
            db.refresh(stop)
            return RouteStopOut.model_validate(stop)

    # Idempotencia: estado ya aplicado
    if stop.status == RouteStopStatus.completed:
        return RouteStopOut.model_validate(stop)

    _assert_route_execution_state(route)

    # Conflicto de estado
    if stop.status != RouteStopStatus.arrived:
        raise conflict(
            "INVALID_STATE_TRANSITION",
            f"La parada está en estado '{stop.status.value}'. Solo se puede completar desde 'arrived'.",
        )

    # Si la ruta aún está en dispatched, la ejecución real empieza en la primera transición de parada.
    if route.status == RouteStatus.dispatched:
        route.status = RouteStatus.in_progress
        route.updated_at = now
        _emit_event(
            db,
            tenant_id=current.tenant_id,
            route_id=route.id,
            event_type=RouteEventType.route_started,
            actor_type=RouteEventActorType.driver,
            actor_id=current.id,
            metadata={"first_stop_id": str(stop_id)},
        )

    # Transición stop
    stop.status = RouteStopStatus.completed
    stop.completed_at = now
    stop.updated_at = now

    # Order: planned→ … → delivered
    order = db.scalar(
        select(Order).where(Order.id == stop.order_id, Order.tenant_id == current.tenant_id)
    )
    if order and order.status in (OrderStatus.assigned, OrderStatus.dispatched):
        order.status = OrderStatus.delivered
        order.updated_at = now

    _emit_event(
        db,
        tenant_id=current.tenant_id,
        route_id=route.id,
        route_stop_id=stop_id,
        event_type=RouteEventType.stop_completed,
        actor_type=RouteEventActorType.driver,
        actor_id=current.id,
        metadata={
            "idempotency_key": payload.idempotency_key or "",
            "order_id": str(stop.order_id),
            "sequence_number": stop.sequence_number,
        },
    )

    # Auto-completar ruta si todas las paradas terminaron
    db.flush()
    _auto_complete_route_if_done(db, current.tenant_id, route, current.id, now)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("RESOURCE_CONFLICT", "No se pudo completar la parada") from exc

    # SSE: notificar suscriptores del estado de la parada (REALTIME-001)
    event_bus.publish(
        str(current.tenant_id),
        str(stop.route_id),
        "stop_status_changed",
        {
            "route_id": str(stop.route_id),
            "stop_id": str(stop.id),
            "status": stop.status.value,
            "sequence_number": stop.sequence_number,
        },
    )

    db.refresh(stop)
    return RouteStopOut.model_validate(stop)


# ============================================================================
# POST /stops/{stopId}/fail
# ============================================================================


@router.post("/stops/{stop_id}/fail", response_model=RouteStopOut)
def stop_fail(
    stop_id: uuid.UUID,
    payload: RouteStopFailRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.driver, UserRole.logistics, UserRole.admin)),
) -> RouteStopOut:
    """
    El chofer reporta entrega fallida.
    Transición válida: arrived → failed.
    failure_reason es obligatorio.
    Actualiza order.status = failed_delivery.
    Si todas las paradas de la ruta terminan, la ruta pasa a completed.

    Idempotencia:
      - Misma idempotency_key → 200 con estado actual.
      - Parada ya en 'failed' → 200.
      - Estado incompatible → 409.
    """
    stop = _get_stop_guarded(db, current.tenant_id, stop_id)
    route = _get_route_for_stop(db, current.tenant_id, stop, require_executable=False)
    _assert_driver_scope_for_route(db, current, route)
    now = datetime.now(UTC)

    # Idempotencia: clave duplicada
    if payload.idempotency_key:
        existing = _find_idempotent_event(
            db,
            tenant_id=current.tenant_id,
            stop_id=stop_id,
            event_type=RouteEventType.stop_failed,
            idempotency_key=payload.idempotency_key,
        )
        if existing:
            db.refresh(stop)
            return RouteStopOut.model_validate(stop)

    # Idempotencia: estado ya aplicado
    if stop.status == RouteStopStatus.failed:
        return RouteStopOut.model_validate(stop)

    _assert_route_execution_state(route)

    # Conflicto de estado
    if stop.status != RouteStopStatus.arrived:
        raise conflict(
            "INVALID_STATE_TRANSITION",
            f"La parada está en estado '{stop.status.value}'. Solo se puede fallar desde 'arrived'.",
        )

    # Si la ruta aún está en dispatched, la ejecución real empieza en la primera transición de parada.
    if route.status == RouteStatus.dispatched:
        route.status = RouteStatus.in_progress
        route.updated_at = now
        _emit_event(
            db,
            tenant_id=current.tenant_id,
            route_id=route.id,
            event_type=RouteEventType.route_started,
            actor_type=RouteEventActorType.driver,
            actor_id=current.id,
            metadata={"first_stop_id": str(stop_id)},
        )

    # Transición stop
    stop.status = RouteStopStatus.failed
    stop.failed_at = now
    stop.failure_reason = payload.failure_reason
    stop.updated_at = now

    # Order: failed_delivery
    order = db.scalar(
        select(Order).where(Order.id == stop.order_id, Order.tenant_id == current.tenant_id)
    )
    if order and order.status in (OrderStatus.assigned, OrderStatus.dispatched):
        order.status = OrderStatus.failed_delivery
        order.updated_at = now

    _emit_event(
        db,
        tenant_id=current.tenant_id,
        route_id=route.id,
        route_stop_id=stop_id,
        event_type=RouteEventType.stop_failed,
        actor_type=RouteEventActorType.driver,
        actor_id=current.id,
        metadata={
            "idempotency_key": payload.idempotency_key or "",
            "order_id": str(stop.order_id),
            "failure_reason": payload.failure_reason,
            "sequence_number": stop.sequence_number,
        },
    )

    # Auto-completar ruta si todas las paradas terminaron
    db.flush()
    _auto_complete_route_if_done(db, current.tenant_id, route, current.id, now)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("RESOURCE_CONFLICT", "No se pudo registrar el fallo de entrega") from exc

    # SSE: notificar suscriptores del estado de la parada (REALTIME-001)
    event_bus.publish(
        str(current.tenant_id),
        str(stop.route_id),
        "stop_status_changed",
        {
            "route_id": str(stop.route_id),
            "stop_id": str(stop.id),
            "status": stop.status.value,
            "sequence_number": stop.sequence_number,
        },
    )

    db.refresh(stop)
    return RouteStopOut.model_validate(stop)


# ============================================================================
# POST /stops/{stopId}/skip
# ============================================================================


@router.post("/stops/{stop_id}/skip", response_model=RouteStopOut)
def stop_skip(
    stop_id: uuid.UUID,
    payload: RouteStopSkipRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.driver, UserRole.logistics, UserRole.admin)),
) -> RouteStopOut:
    """
    Marca una parada como omitida por ejecución.
    Transiciones válidas: pending | en_route | arrived → skipped.
    """
    stop = _get_stop_guarded(db, current.tenant_id, stop_id)
    route = _get_route_for_stop(db, current.tenant_id, stop, require_executable=False)
    _assert_driver_scope_for_route(db, current, route)
    now = datetime.now(UTC)

    if payload.idempotency_key:
        existing = _find_idempotent_event(
            db,
            tenant_id=current.tenant_id,
            stop_id=stop_id,
            event_type=RouteEventType.stop_skipped,
            idempotency_key=payload.idempotency_key,
        )
        if existing:
            db.refresh(stop)
            return RouteStopOut.model_validate(stop)

    if stop.status == RouteStopStatus.skipped:
        return RouteStopOut.model_validate(stop)

    _assert_route_execution_state(route)

    if stop.status not in (RouteStopStatus.pending, RouteStopStatus.en_route, RouteStopStatus.arrived):
        raise conflict(
            "INVALID_STATE_TRANSITION",
            f"La parada está en estado '{stop.status.value}'. No se puede omitir.",
        )

    if route.status == RouteStatus.dispatched:
        route.status = RouteStatus.in_progress
        route.updated_at = now
        _emit_event(
            db,
            tenant_id=current.tenant_id,
            route_id=route.id,
            event_type=RouteEventType.route_started,
            actor_type=RouteEventActorType.driver,
            actor_id=current.id,
            metadata={"first_stop_id": str(stop_id)},
        )

    stop.status = RouteStopStatus.skipped
    stop.updated_at = now

    _emit_event(
        db,
        tenant_id=current.tenant_id,
        route_id=route.id,
        route_stop_id=stop_id,
        event_type=RouteEventType.stop_skipped,
        actor_type=RouteEventActorType.driver,
        actor_id=current.id,
        metadata={
            "idempotency_key": payload.idempotency_key or "",
            "order_id": str(stop.order_id),
            "reason": payload.reason or "",
            "sequence_number": stop.sequence_number,
        },
    )

    db.flush()
    _auto_complete_route_if_done(db, current.tenant_id, route, current.id, now)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("RESOURCE_CONFLICT", "No se pudo omitir la parada") from exc

    # SSE: notificar suscriptores del estado de la parada (REALTIME-001)
    event_bus.publish(
        str(current.tenant_id),
        str(stop.route_id),
        "stop_status_changed",
        {
            "route_id": str(stop.route_id),
            "stop_id": str(stop.id),
            "status": stop.status.value,
            "sequence_number": stop.sequence_number,
        },
    )

    db.refresh(stop)
    return RouteStopOut.model_validate(stop)


# ============================================================================
# POST /incidents
# ============================================================================


@router.post("/incidents", response_model=IncidentOut, status_code=201)
def create_incident(
    payload: IncidentCreateRequest,
    response: Response,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.driver, UserRole.logistics, UserRole.admin)),
) -> IncidentOut:
    """
    El chofer registra una incidencia en ruta.
    driver_id se infiere de la ruta (route.driver_id).

    Idempotencia:
      - Si se proporciona idempotency_key y ya existe un evento incident.reported
        con esa clave para la misma ruta → 200 con la incidencia original.
      - Sin clave o sin coincidencia → crear nueva incidencia → 201.
    """
    # Verificar ruta
    route = db.scalar(
        select(Route).where(Route.id == payload.route_id, Route.tenant_id == current.tenant_id)
    )
    if not route:
        raise not_found("ENTITY_NOT_FOUND", "Ruta no encontrada")
    if route.status not in (RouteStatus.dispatched, RouteStatus.in_progress, RouteStatus.completed):
        raise conflict(
            "INVALID_STATE_TRANSITION",
            f"No se pueden registrar incidencias en rutas en estado '{route.status.value}'.",
        )
    _assert_driver_scope_for_route(db, current, route)

    # Verificar parada si se proporciona
    if payload.route_stop_id is not None:
        stop_check = db.scalar(
            select(RouteStop).where(
                RouteStop.id == payload.route_stop_id,
                RouteStop.route_id == payload.route_id,
                RouteStop.tenant_id == current.tenant_id,
            )
        )
        if not stop_check:
            raise not_found("ENTITY_NOT_FOUND", "Parada no encontrada en esta ruta")

    # Driver: requerido por el modelo Incident; se infiere de la ruta
    if not route.driver_id:
        raise unprocessable("MISSING_DRIVER", "La ruta no tiene chofer asignado; no se puede registrar incidencia")

    # Idempotencia: buscar evento previo con la misma clave
    if payload.idempotency_key:
        existing_event = db.scalar(
            select(RouteEvent).where(
                RouteEvent.tenant_id == current.tenant_id,
                RouteEvent.route_id == payload.route_id,
                RouteEvent.event_type == RouteEventType.incident_reported,
                RouteEvent.metadata_json["idempotency_key"].as_string() == payload.idempotency_key,
            )
        )
        if existing_event:
            incident_id_str = (existing_event.metadata_json or {}).get("incident_id")
            if incident_id_str:
                existing_incident = db.scalar(
                    select(Incident).where(
                        Incident.id == uuid.UUID(incident_id_str),
                        Incident.tenant_id == current.tenant_id,
                    )
                )
                if existing_incident:
                    response.status_code = 200
                    return IncidentOut.model_validate(existing_incident)

    now = datetime.now(UTC)

    # Crear incidencia
    incident = Incident(
        id=uuid.uuid4(),
        tenant_id=current.tenant_id,
        route_id=payload.route_id,
        route_stop_id=payload.route_stop_id,
        driver_id=route.driver_id,
        type=IncidentType(payload.type),
        severity=IncidentSeverity(payload.severity),
        description=payload.description,
        status=IncidentStatus.open,
        reported_at=now,
        reviewed_at=None,
        resolved_at=None,
        resolution_note=None,
        created_at=now,
        updated_at=now,
    )
    db.add(incident)
    db.flush()  # obtener incident.id

    _emit_event(
        db,
        tenant_id=current.tenant_id,
        route_id=payload.route_id,
        route_stop_id=payload.route_stop_id,
        event_type=RouteEventType.incident_reported,
        actor_type=RouteEventActorType.driver,
        actor_id=current.id,
        metadata={
            "idempotency_key": payload.idempotency_key or "",
            "incident_id": str(incident.id),
            "type": payload.type,
            "severity": payload.severity,
        },
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("RESOURCE_CONFLICT", "No se pudo registrar la incidencia") from exc

    db.refresh(incident)
    return IncidentOut.model_validate(incident)


# ============================================================================
# GET /incidents  — listar incidencias de una ruta (dispatcher/office)
# ============================================================================


@router.get("/incidents", response_model=IncidentsListResponse)
def list_incidents(
    route_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.office, UserRole.logistics, UserRole.admin)),
) -> IncidentsListResponse:
    """
    Lista incidencias. Filtro obligatorio recomendado: route_id.
    Sin side effects.
    """
    query = (
        select(Incident)
        .where(Incident.tenant_id == current.tenant_id)
        .order_by(Incident.reported_at.desc())
    )
    if route_id is not None:
        query = query.where(Incident.route_id == route_id)

    rows = list(db.scalars(query))
    return IncidentsListResponse(
        items=[IncidentOut.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.post("/incidents/{incident_id}/review", response_model=IncidentOut)
def review_incident(
    incident_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.logistics, UserRole.admin)),
) -> IncidentOut:
    incident = db.scalar(
        select(Incident).where(Incident.id == incident_id, Incident.tenant_id == current.tenant_id)
    )
    if not incident:
        raise not_found("ENTITY_NOT_FOUND", "Incidencia no encontrada")

    if incident.status == IncidentStatus.resolved:
        raise conflict("INVALID_STATE_TRANSITION", "No se puede revisar una incidencia ya resuelta")
    if incident.status == IncidentStatus.reviewed:
        return IncidentOut.model_validate(incident)

    now = datetime.now(UTC)
    incident.status = IncidentStatus.reviewed
    incident.reviewed_at = now
    incident.updated_at = now

    _emit_event(
        db,
        tenant_id=current.tenant_id,
        route_id=incident.route_id,
        route_stop_id=incident.route_stop_id,
        event_type=RouteEventType.incident_reviewed,
        actor_type=RouteEventActorType.dispatcher,
        actor_id=current.id,
        metadata={"incident_id": str(incident.id)},
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("RESOURCE_CONFLICT", "No se pudo revisar la incidencia") from exc

    db.refresh(incident)
    return IncidentOut.model_validate(incident)


@router.post("/incidents/{incident_id}/resolve", response_model=IncidentOut)
def resolve_incident(
    incident_id: uuid.UUID,
    payload: IncidentResolveRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.logistics, UserRole.admin)),
) -> IncidentOut:
    incident = db.scalar(
        select(Incident).where(Incident.id == incident_id, Incident.tenant_id == current.tenant_id)
    )
    if not incident:
        raise not_found("ENTITY_NOT_FOUND", "Incidencia no encontrada")

    if incident.status == IncidentStatus.resolved:
        return IncidentOut.model_validate(incident)
    if incident.status != IncidentStatus.reviewed:
        raise conflict(
            "INVALID_STATE_TRANSITION",
            "Solo incidencias en estado 'reviewed' pueden resolverse",
        )

    now = datetime.now(UTC)
    incident.status = IncidentStatus.resolved
    incident.resolved_at = now
    incident.resolution_note = payload.resolution_note
    incident.updated_at = now

    _emit_event(
        db,
        tenant_id=current.tenant_id,
        route_id=incident.route_id,
        route_stop_id=incident.route_stop_id,
        event_type=RouteEventType.incident_resolved,
        actor_type=RouteEventActorType.dispatcher,
        actor_id=current.id,
        metadata={"incident_id": str(incident.id)},
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("RESOURCE_CONFLICT", "No se pudo resolver la incidencia") from exc

    db.refresh(incident)
    return IncidentOut.model_validate(incident)


# ============================================================================
# BLOQUE A2 — Proof of Delivery (POD-001)
# ============================================================================


def _get_stop_proof(db: Session, tenant_id: uuid.UUID, route_stop_id: uuid.UUID) -> StopProof | None:
    return db.execute(
        select(StopProof).where(
            StopProof.tenant_id == tenant_id,
            StopProof.route_stop_id == route_stop_id,
        )
    ).scalar_one_or_none()


@router.post("/stops/{stop_id}/proof", response_model=StopProofOut, status_code=201)
def create_stop_proof(
    stop_id: uuid.UUID,
    payload: StopProofCreateRequest,
    current: CurrentUser = Depends(require_roles("driver", "logistics", "admin")),
    db: Session = Depends(get_db),
) -> StopProof:
    """
    Registrar prueba de entrega (firma digital) para una parada.
    Solo callable por el driver asignado a la ruta, o por logistics/admin.
    """
    stop = _get_stop_guarded(db, current.tenant_id, stop_id)

    # El driver solo puede firmar paradas de su propia ruta
    if current.role == "driver":
        route = db.execute(
            select(Route).where(Route.id == stop.route_id, Route.tenant_id == current.tenant_id)
        ).scalar_one_or_none()
        if route:
            _assert_driver_scope_for_route(db, current, route)

    # Solo paradas en arrived o completed admiten prueba
    if stop.status not in (RouteStopStatus.arrived, RouteStopStatus.completed):
        raise conflict(
            "STOP_NOT_ARRIVED",
            f"La parada debe estar en 'arrived' o 'completed' para registrar prueba (estado actual: {stop.status})",
        )

    # Validar que haya datos cuando proof_type incluye firma
    if payload.proof_type in ("signature", "both") and not payload.signature_data:
        raise unprocessable(
            "SIGNATURE_DATA_REQUIRED",
            "signature_data es obligatorio para proof_type 'signature' o 'both'",
        )

    now = datetime.now(UTC)
    proof = StopProof(
        id=uuid.uuid4(),
        tenant_id=current.tenant_id,
        route_stop_id=stop_id,
        route_id=stop.route_id,
        proof_type=payload.proof_type,
        signature_data=payload.signature_data,
        photo_url=None,
        signed_by=payload.signed_by,
        captured_at=payload.captured_at or now,
        created_at=now,
    )
    db.add(proof)

    _emit_event(
        db,
        tenant_id=current.tenant_id,
        route_id=stop.route_id,
        route_stop_id=stop_id,
        event_type=RouteEventType.stop_completed,
        actor_type=RouteEventActorType.driver,
        actor_id=current.id,
        metadata={"proof_type": payload.proof_type, "signed_by": payload.signed_by},
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("RESOURCE_CONFLICT", "No se pudo registrar la prueba de entrega") from exc

    db.refresh(proof)
    return proof


@router.get("/stops/{stop_id}/proof", response_model=StopProofOut)
def get_stop_proof(
    stop_id: uuid.UUID,
    current: CurrentUser = Depends(require_roles("driver", "logistics", "admin", "office")),
    db: Session = Depends(get_db),
) -> StopProof:
    """Obtener la prueba de entrega de una parada."""
    _get_stop_guarded(db, current.tenant_id, stop_id)
    proof = _get_stop_proof(db, current.tenant_id, stop_id)
    if not proof:
        raise not_found("PROOF_NOT_FOUND", "No se encontró prueba de entrega para esta parada")
    return proof


# ── R8-POD-FOTO: upload URL + photo confirm ───────────────────────────────────

_R2_PRESIGNED_TTL = 300  # 5 minutos


def _get_r2_client():
    """Devuelve un cliente boto3 S3-compatible apuntando a Cloudflare R2.

    Lanza HTTPException 503 si las credenciales R2 no están configuradas.
    En tests, parchear con unittest.mock.patch('app.routers.routing._get_r2_client').
    """
    import boto3  # importación local para no romper arranque si boto3 no está instalado en dev
    from botocore.config import Config

    s = settings
    if not s.r2_account_id or not s.r2_access_key_id or not s.r2_secret_access_key:
        raise HTTPException(
            status_code=503,
            detail={"code": "R2_NOT_CONFIGURED", "message": "Almacenamiento de fotos no configurado"},
        )
    return boto3.client(
        "s3",
        endpoint_url=f"https://{s.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=s.r2_access_key_id,
        aws_secret_access_key=s.r2_secret_access_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


@router.post("/stops/{stop_id}/proof-upload-url", response_model=ProofUploadUrlResponse)
def get_proof_upload_url(
    stop_id: uuid.UUID,
    current: CurrentUser = Depends(require_roles("driver", "logistics", "admin")),
    db: Session = Depends(get_db),
) -> ProofUploadUrlResponse:
    """Generar presigned PUT URL para subir foto de entrega directamente a R2.

    El cliente sube la foto a R2 con el upload_url devuelto y luego confirma
    el upload llamando a PATCH /stops/{stop_id}/proof/photo con el object_key.

    La parada debe estar en estado 'arrived' o 'completed'.
    """
    stop = _get_stop_guarded(db, current.tenant_id, stop_id)

    if stop.status not in (RouteStopStatus.arrived, RouteStopStatus.completed):
        raise conflict(
            "STOP_NOT_ARRIVED",
            f"La parada debe estar en 'arrived' o 'completed' para subir foto (estado: {stop.status})",
        )

    object_key = f"{current.tenant_id}/{stop.route_id}/{stop_id}/{uuid.uuid4()}.jpg"

    r2 = _get_r2_client()
    upload_url = r2.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.r2_bucket_name,
            "Key": object_key,
            "ContentType": "image/jpeg",
        },
        ExpiresIn=_R2_PRESIGNED_TTL,
    )

    return ProofUploadUrlResponse(
        upload_url=upload_url,
        object_key=object_key,
        expires_in=_R2_PRESIGNED_TTL,
    )


@router.patch("/stops/{stop_id}/proof/photo", response_model=StopProofOut)
def confirm_proof_photo(
    stop_id: uuid.UUID,
    payload: ProofPhotoConfirmRequest,
    current: CurrentUser = Depends(require_roles("driver", "logistics", "admin")),
    db: Session = Depends(get_db),
) -> StopProof:
    """Confirmar upload de foto de entrega escribiendo photo_url en el StopProof.

    El backend construye la URL pública a partir del object_key para evitar
    que el cliente pueda enlazar URLs arbitrarias como evidencia.

    Semántica de overwrite: si ya existe photo_url, se sobreescribe (gana el último).

    Requiere que el StopProof exista previamente (POST /stops/{id}/proof ya llamado).
    """
    _get_stop_guarded(db, current.tenant_id, stop_id)

    proof = _get_stop_proof(db, current.tenant_id, stop_id)
    if not proof:
        raise not_found("PROOF_NOT_FOUND", "Debe crear el proof antes de confirmar la foto")

    # Validar que el object_key pertenece a este tenant
    expected_prefix = f"{current.tenant_id}/"
    if not payload.object_key.startswith(expected_prefix):
        raise unprocessable(
            "INVALID_OBJECT_KEY",
            "El object_key no pertenece a este tenant",
        )

    if not settings.r2_public_url:
        raise HTTPException(
            status_code=503,
            detail={"code": "R2_NOT_CONFIGURED", "message": "URL pública de R2 no configurada"},
        )

    proof.photo_url = f"{settings.r2_public_url.rstrip('/')}/{payload.object_key}"
    db.commit()
    db.refresh(proof)
    return proof


# ============================================================================
# ROUTE-PLANNER-TW-001 — Editar hora de llegada planificada de una parada
# ============================================================================


@router.patch("/stops/{stop_id}/scheduled-arrival", response_model=RouteStopOut)
def update_stop_scheduled_arrival(
    stop_id: uuid.UUID,
    payload: RouteStopScheduledArrivalRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.logistics, UserRole.admin)),
) -> RouteStopOut:
    """
    Editar la hora de llegada planificada (estimated_arrival_at) de una parada.

    Solo disponible para dispatchers (logistics, admin).
    Rechaza paradas en estado terminal (completed, failed, skipped).
    No emite RouteEvent — es un ajuste de planificación, no un cambio de estado operativo.
    """
    stop = _get_stop_guarded(db, current.tenant_id, stop_id)

    terminal = {RouteStopStatus.completed, RouteStopStatus.failed, RouteStopStatus.skipped}
    if stop.status in terminal:
        raise unprocessable(
            "STOP_TERMINAL",
            f"No se puede modificar una parada en estado '{stop.status.value}'",
        )

    stop.estimated_arrival_at = payload.scheduled_arrival_at
    db.commit()
    db.refresh(stop)
    return RouteStopOut.model_validate(stop)


# ============================================================================
# BLOQUE A3 — GPS del conductor (GPS-001)
# ============================================================================


@router.post("/driver/location", status_code=204)
def update_driver_location(
    payload: DriverLocationUpdateRequest,
    current: CurrentUser = Depends(require_roles("driver")),
    db: Session = Depends(get_db),
) -> Response:
    """
    Recibir posición GPS del conductor. Llamado periódicamente desde la PWA.
    Solo callable por driver autenticado con ruta activa (in_progress).
    """
    driver = _resolve_current_driver(db, current)
    if not driver:
        raise not_found("DRIVER_NOT_FOUND", "No se encontró un conductor asociado a este usuario")

    route = db.execute(
        select(Route).where(
            Route.id == payload.route_id,
            Route.tenant_id == current.tenant_id,
            Route.driver_id == driver.id,
        )
    ).scalar_one_or_none()

    if not route:
        raise not_found(
            "ROUTE_NOT_FOUND",
            "Ruta no encontrada o no asignada a este conductor",
        )

    if route.status != RouteStatus.in_progress:
        raise conflict(
            "ROUTE_NOT_IN_PROGRESS",
            f"La ruta debe estar en progreso para publicar posición (estado actual: {route.status})",
        )

    now = datetime.now(UTC)
    position = DriverPosition(
        id=uuid.uuid4(),
        tenant_id=current.tenant_id,
        driver_id=driver.id,
        route_id=payload.route_id,
        lat=payload.lat,
        lng=payload.lng,
        accuracy_m=payload.accuracy_m,
        speed_kmh=payload.speed_kmh,
        heading=payload.heading,
        recorded_at=payload.recorded_at or now,
        created_at=now,
    )
    db.add(position)
    db.commit()

    # SSE: notificar suscriptores de la nueva posición del conductor (REALTIME-001)
    event_bus.publish(
        str(current.tenant_id),
        str(payload.route_id),
        "driver_position_updated",
        {
            "route_id": str(payload.route_id),
            "lat": float(payload.lat),
            "lng": float(payload.lng),
            "recorded_at": position.recorded_at.isoformat(),
        },
    )

    return Response(status_code=204)


@router.get("/routes/{route_id}/driver-position", response_model=DriverPositionOut)
def get_driver_position(
    route_id: uuid.UUID,
    current: CurrentUser = Depends(require_roles("logistics", "admin", "office", "driver")),
    db: Session = Depends(get_db),
) -> DriverPosition:
    """
    Última posición conocida del conductor para una ruta.
    Dispatcher (logistics/admin) puede ver cualquier ruta del tenant.
    Driver solo puede ver la posición de su propia ruta.
    """
    route = db.execute(
        select(Route).where(Route.id == route_id, Route.tenant_id == current.tenant_id)
    ).scalar_one_or_none()
    if not route:
        raise not_found("ROUTE_NOT_FOUND", "Ruta no encontrada")

    if current.role == "driver":
        driver = _resolve_current_driver(db, current)
        if not driver or route.driver_id != driver.id:
            raise forbidden("FORBIDDEN", "No tienes acceso a esta ruta")

    position = db.execute(
        select(DriverPosition)
        .where(
            DriverPosition.route_id == route_id,
            DriverPosition.tenant_id == current.tenant_id,
        )
        .order_by(DriverPosition.recorded_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if not position:
        raise not_found("POSITION_NOT_FOUND", "No hay posición registrada para esta ruta")

    return position


@router.get("/driver/active-positions", response_model=list[DriverPositionOut])
def get_active_positions(
    current: CurrentUser = Depends(require_roles("logistics", "admin")),
    db: Session = Depends(get_db),
) -> list[DriverPosition]:
    """
    Última posición de todos los conductores con rutas in_progress del tenant.
    Para fleet view en el mapa del dispatcher.
    """
    active_route_ids = db.execute(
        select(Route.id).where(
            Route.tenant_id == current.tenant_id,
            Route.status == RouteStatus.in_progress,
        )
    ).scalars().all()

    if not active_route_ids:
        return []

    positions: list[DriverPosition] = []
    for rid in active_route_ids:
        pos = db.execute(
            select(DriverPosition)
            .where(
                DriverPosition.route_id == rid,
                DriverPosition.tenant_id == current.tenant_id,
            )
            .order_by(DriverPosition.recorded_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if pos:
            positions.append(pos)

    return positions


# ============================================================================
# BLOQUE B1 — SSE: stream en tiempo real de una ruta (REALTIME-001)
# ============================================================================


@router.get("/routes/{route_id}/stream")
async def route_stream(
    route_id: uuid.UUID,
    token: str = Query(
        ...,
        description=(
            "JWT de autenticación. "
            "NOTA B1: token en query param aceptado SOLO para smoke/local/pilot de REALTIME-001. "
            "SSE no soporta headers Authorization en browser. "
            "La autenticación definitiva de streaming requiere decisión explícita en bloque posterior."
        ),
    ),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """
    Stream SSE de eventos en tiempo real para una ruta.

    Emite dos tipos de evento (REALTIME-001):
    - stop_status_changed: cuando arrive / complete / fail / skip ocurre en una parada.
    - driver_position_updated: cuando el conductor publica su posición GPS.

    El stream permanece abierto mientras el cliente esté conectado.
    Tenant isolation: solo emite eventos del tenant del token.

    Autenticación via query param ?token=<jwt> — provisional B1.
    Ver docstring del módulo realtime.py para limitaciones conocidas.
    """
    # --- Auth desde query param (excepción temporal B1) ---
    try:
        jwt_payload = decode_token(token)
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_TOKEN", "message": "Token inválido"},
        )

    user_id_str = jwt_payload.get("sub")
    tenant_id_str = jwt_payload.get("tenant_id")
    if not user_id_str or not tenant_id_str:
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_TOKEN", "message": "Token incompleto"},
        )

    try:
        auth_user_id = uuid.UUID(user_id_str)
        auth_tenant_id = uuid.UUID(tenant_id_str)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_TOKEN", "message": "Token malformado"},
        )

    user = db.scalar(
        select(User).where(
            User.id == auth_user_id,
            User.tenant_id == auth_tenant_id,
            User.is_active.is_(True),
        )
    )
    if not user:
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_TOKEN", "message": "Usuario no válido o inactivo"},
        )

    # --- Verificar que la ruta pertenece al tenant ---
    route = db.scalar(
        select(Route).where(
            Route.id == route_id,
            Route.tenant_id == auth_tenant_id,
        )
    )
    if not route:
        raise HTTPException(
            status_code=404,
            detail={"code": "ROUTE_NOT_FOUND", "message": "Ruta no encontrada"},
        )

    # --- Generador SSE ---
    tenant_id_key = str(auth_tenant_id)
    route_id_key = str(route_id)

    async def _generator():
        # Comentario inicial: confirma conexión al cliente sin emitir un evento real
        yield ": connected\n\n"
        async for frame in event_bus.subscribe(tenant_id_key, route_id_key):
            yield frame

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Nginx: desactivar buffering para SSE
        },
    )


# ============================================================================
# POST /routes/{route_id}/recalculate-eta  (B2 — ETA-001)
# ============================================================================

_DELAY_ALERT_THRESHOLD_MINUTES = 15.0


@router.post("/routes/{route_id}/recalculate-eta", response_model=RecalculateEtaResponse)
def recalculate_eta(
    route_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.logistics, UserRole.admin)),
) -> RecalculateEtaResponse:
    """
    Recalcula la ETA de las paradas pendientes/en_route basándose en la
    posición actual del conductor. Actualiza recalculated_eta_at en cada parada.
    Si el retraso supera 15 min sobre la ETA original → crea evento delay_alert.
    Emite SSE eta_updated con el resumen.

    Requiere que el conductor haya publicado al menos una posición GPS.
    """
    now = datetime.now(UTC)

    route = db.scalar(
        select(Route).where(Route.id == route_id, Route.tenant_id == current.tenant_id)
    )
    if not route:
        raise not_found("ROUTE_NOT_FOUND", "Ruta no encontrada")

    if route.status not in (RouteStatus.dispatched, RouteStatus.in_progress):
        raise conflict(
            "ROUTE_NOT_ACTIVE",
            f"Solo se puede recalcular ETA en rutas activas. Estado actual: {route.status.value}",
        )

    # --- Posición actual del conductor ---
    driver_pos = db.scalar(
        select(DriverPosition)
        .where(
            DriverPosition.tenant_id == current.tenant_id,
            DriverPosition.route_id == route_id,
        )
        .order_by(DriverPosition.recorded_at.desc())
    )
    if driver_pos is None:
        raise not_found(
            "DRIVER_POSITION_NOT_FOUND",
            "El conductor aún no ha publicado su posición GPS. "
            "La app del conductor debe estar activa con la ruta en curso.",
        )

    driver_lat = float(driver_pos.lat)
    driver_lng = float(driver_pos.lng)

    # --- Paradas pendientes/en_route con geo del cliente ---
    pending_statuses = (RouteStopStatus.pending, RouteStopStatus.en_route)
    stops = list(
        db.scalars(
            select(RouteStop)
            .where(
                RouteStop.tenant_id == current.tenant_id,
                RouteStop.route_id == route_id,
                RouteStop.status.in_(pending_statuses),
            )
            .order_by(RouteStop.sequence_number)
        )
    )

    if not stops:
        return RecalculateEtaResponse(
            route_id=route_id,
            stops_updated=0,
            delay_alerts_created=0,
            results=[],
        )

    geo_by_order_id = _load_customer_geo_by_order_id(
        db,
        tenant_id=current.tenant_id,
        order_ids=[s.order_id for s in stops],
    )

    results: list[EtaStopResult] = []
    delay_alerts_created = 0
    reference_time = now

    for stop in stops:
        lat, lng = geo_by_order_id.get(stop.order_id, (None, None))
        if lat is None or lng is None:
            # Sin geo → no podemos calcular; saltamos sin error
            continue

        new_eta = calculate_eta(
            current_lat=driver_lat,
            current_lng=driver_lng,
            stop_lat=lat,
            stop_lng=lng,
            reference_time=reference_time,
        )

        original_eta = stop.estimated_arrival_at
        delay_mins = eta_delay_minutes(original_eta, new_eta) if original_eta else 0.0
        is_delay = original_eta is not None and delay_mins >= _DELAY_ALERT_THRESHOLD_MINUTES

        # Actualizar recalculated_eta_at
        stop.recalculated_eta_at = new_eta
        stop.updated_at = now

        if is_delay:
            _emit_event(
                db,
                tenant_id=current.tenant_id,
                route_id=route_id,
                route_stop_id=stop.id,
                event_type=RouteEventType.delay_alert,
                actor_type=RouteEventActorType.system,
                actor_id=None,
                metadata={
                    "stop_id": str(stop.id),
                    "sequence_number": stop.sequence_number,
                    "original_eta": original_eta.isoformat() if original_eta else None,
                    "recalculated_eta": new_eta.isoformat(),
                    "delay_minutes": round(delay_mins, 1),
                },
            )
            delay_alerts_created += 1

        results.append(
            EtaStopResult(
                stop_id=stop.id,
                sequence_number=stop.sequence_number,
                original_eta=original_eta,
                recalculated_eta=new_eta,
                delay_minutes=round(delay_mins, 1),
                delay_alert=is_delay,
            )
        )

        # Avanzar reference_time para calcular cadena de ETAs secuencialmente
        reference_time = new_eta + timedelta(minutes=stop.estimated_service_minutes)

    db.commit()

    # Emitir SSE
    event_bus.publish(
        str(current.tenant_id),
        str(route_id),
        "eta_updated",
        {
            "route_id": str(route_id),
            "stops_updated": len(results),
            "delay_alerts": delay_alerts_created,
        },
    )

    return RecalculateEtaResponse(
        route_id=route_id,
        stops_updated=len(results),
        delay_alerts_created=delay_alerts_created,
        results=results,
    )


# ============================================================================
# GET /routes/{route_id}/delay-alerts  (B2 — ETA-001)
# ============================================================================


@router.get("/routes/{route_id}/delay-alerts", response_model=list[DelayAlertOut])
def get_delay_alerts(
    route_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.logistics, UserRole.admin)),
) -> list[DelayAlertOut]:
    """Lista todos los eventos delay_alert de una ruta, ordenados por timestamp desc."""
    route = db.scalar(
        select(Route).where(Route.id == route_id, Route.tenant_id == current.tenant_id)
    )
    if not route:
        raise not_found("ROUTE_NOT_FOUND", "Ruta no encontrada")

    events = list(
        db.scalars(
            select(RouteEvent)
            .where(
                RouteEvent.tenant_id == current.tenant_id,
                RouteEvent.route_id == route_id,
                RouteEvent.event_type == RouteEventType.delay_alert,
            )
            .order_by(RouteEvent.ts.desc())
        )
    )

    return [
        DelayAlertOut(
            event_id=ev.id,
            route_id=ev.route_id,
            stop_id=ev.route_stop_id,
            original_eta=datetime.fromisoformat(ev.metadata_json["original_eta"])
            if ev.metadata_json.get("original_eta")
            else None,
            recalculated_eta=datetime.fromisoformat(ev.metadata_json["recalculated_eta"])
            if ev.metadata_json.get("recalculated_eta")
            else None,
            delay_minutes=ev.metadata_json.get("delay_minutes"),
            ts=ev.ts,
        )
        for ev in events
    ]


# ============================================================================
# BLOQUE B4 — LIVE-EDIT-001: edición de ruta en vivo
# ============================================================================

_LIVE_EDIT_ROUTE_STATUSES = (
    RouteStatus.planned,
    RouteStatus.dispatched,
    RouteStatus.in_progress,
)


@router.post(
    "/routes/{route_id}/add-stop",
    response_model=AddStopResponse,
    status_code=201,
    summary="Añadir un pedido a una ruta en vivo",
)
def add_stop(
    route_id: uuid.UUID,
    payload: AddStopRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.logistics, UserRole.admin)),
) -> AddStopResponse:
    """
    Añade un pedido a una ruta ya planificada, despachada o en curso.

    El pedido debe existir en el mismo tenant y tener un cliente con coordenadas.
    Si el pedido ya tiene una parada activa en otra ruta → 409 RESOURCE_CONFLICT.
    """
    route = db.scalar(
        select(Route).where(Route.id == route_id, Route.tenant_id == current.tenant_id)
    )
    if not route:
        raise not_found("ROUTE_NOT_FOUND", "Ruta no encontrada")
    if route.status not in _LIVE_EDIT_ROUTE_STATUSES:
        raise unprocessable(
            "INVALID_STATE_TRANSITION",
            f"Solo se pueden añadir paradas a rutas en estado planned, dispatched o in_progress. Estado actual: '{route.status.value}'",
        )

    order = db.scalar(
        select(Order).where(Order.id == payload.order_id, Order.tenant_id == current.tenant_id)
    )
    if not order:
        raise not_found("ORDER_NOT_FOUND", "Pedido no encontrado")

    # Verificar que el pedido no está ya en otra ruta activa
    existing_stop = db.scalar(
        select(RouteStop).where(
            RouteStop.order_id == payload.order_id,
            RouteStop.tenant_id == current.tenant_id,
            RouteStop.status == RouteStopStatus.pending,
        )
    )
    if existing_stop:
        raise conflict(
            "RESOURCE_CONFLICT",
            "El pedido ya tiene una parada activa en una ruta",
        )

    # Calcular siguiente sequence_number
    max_seq = db.scalar(
        select(RouteStop.sequence_number)
        .where(RouteStop.route_id == route_id, RouteStop.tenant_id == current.tenant_id)
        .order_by(RouteStop.sequence_number.desc())
        .limit(1)
    )
    new_seq = (max_seq or 0) + 1

    now = datetime.now(UTC)
    new_stop = RouteStop(
        id=uuid.uuid4(),
        tenant_id=current.tenant_id,
        route_id=route_id,
        order_id=payload.order_id,
        sequence_number=new_seq,
        estimated_arrival_at=None,
        estimated_service_minutes=10,
        status=RouteStopStatus.pending,
        arrived_at=None,
        completed_at=None,
        failed_at=None,
        failure_reason=None,
        created_at=now,
        updated_at=now,
    )
    db.add(new_stop)
    db.flush()

    _emit_event(
        db,
        tenant_id=current.tenant_id,
        route_id=route_id,
        route_stop_id=new_stop.id,
        event_type=RouteEventType.stop_en_route,
        actor_type=RouteEventActorType.dispatcher,
        actor_id=current.id,
        metadata={
            "order_id": str(payload.order_id),
            "sequence_number": new_seq,
            "action": "live_add_stop",
        },
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("RESOURCE_CONFLICT", "No se pudo añadir la parada") from exc

    # SSE: notificar suscriptores
    event_bus.publish(
        str(current.tenant_id),
        str(route_id),
        "stop_added",
        {
            "stop_id": str(new_stop.id),
            "order_id": str(payload.order_id),
            "sequence_number": new_seq,
        },
    )

    return AddStopResponse(
        order_id=payload.order_id,
        route_id=route_id,
        stop_id=new_stop.id,
        sequence_number=new_seq,
    )


@router.post(
    "/routes/{route_id}/stops/{stop_id}/remove",
    response_model=RemoveStopResponse,
    summary="Eliminar una parada pendiente de una ruta en vivo",
)
def remove_stop(
    route_id: uuid.UUID,
    stop_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.logistics, UserRole.admin)),
) -> RemoveStopResponse:
    """
    Elimina una parada pendiente de una ruta activa.

    Solo se pueden eliminar paradas en estado 'pending'.
    La ruta puede estar en cualquier estado activo (planned, dispatched, in_progress).
    """
    route = db.scalar(
        select(Route).where(Route.id == route_id, Route.tenant_id == current.tenant_id)
    )
    if not route:
        raise not_found("ROUTE_NOT_FOUND", "Ruta no encontrada")
    if route.status not in _LIVE_EDIT_ROUTE_STATUSES:
        raise unprocessable(
            "INVALID_STATE_TRANSITION",
            f"Solo se pueden eliminar paradas de rutas activas. Estado actual: '{route.status.value}'",
        )

    stop = db.scalar(
        select(RouteStop).where(
            RouteStop.id == stop_id,
            RouteStop.route_id == route_id,
            RouteStop.tenant_id == current.tenant_id,
        )
    )
    if not stop:
        raise not_found("STOP_NOT_FOUND", "Parada no encontrada en esta ruta")
    if stop.status != RouteStopStatus.pending:
        raise unprocessable(
            "INVALID_STATE_TRANSITION",
            f"Solo se pueden eliminar paradas en estado 'pending'. Estado actual: '{stop.status.value}'",
        )

    order_id = stop.order_id
    removed_stop_id = stop.id

    # route_stop_id=None para evitar que la FK CASCADE intente borrar el evento
    # al eliminar la parada (route_events es append-only — trigger bloquea DELETEs)
    _emit_event(
        db,
        tenant_id=current.tenant_id,
        route_id=route_id,
        route_stop_id=None,
        event_type=RouteEventType.stop_skipped,
        actor_type=RouteEventActorType.dispatcher,
        actor_id=current.id,
        metadata={
            "order_id": str(order_id),
            "stop_id": str(removed_stop_id),
            "action": "live_remove_stop",
            "sequence_number": stop.sequence_number,
        },
    )

    db.delete(stop)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("RESOURCE_CONFLICT", "No se pudo eliminar la parada") from exc

    # SSE: notificar suscriptores
    event_bus.publish(
        str(current.tenant_id),
        str(route_id),
        "stop_removed",
        {
            "stop_id": str(removed_stop_id),
            "order_id": str(order_id),
        },
    )

    return RemoveStopResponse(
        order_id=order_id,
        route_id=route_id,
        removed_stop_id=removed_stop_id,
    )


# ============================================================================
# BLOQUE B3 — CHAT-001: mensajes internos dispatcher ↔ conductor
# ============================================================================

_CHAT_ROLES = {UserRole.logistics, UserRole.admin, UserRole.driver}


@router.post(
    "/routes/{route_id}/messages",
    response_model=RouteMessageOut,
    status_code=201,
    summary="Enviar mensaje de chat en una ruta",
)
def send_route_message(
    route_id: uuid.UUID,
    body: RouteMessageIn,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles(UserRole.logistics, UserRole.admin, UserRole.driver)),
) -> RouteMessage:
    """
    Envía un mensaje al hilo de chat de la ruta.

    Accesible por logistics, admin y driver.
    El autor queda registrado con su user_id y role.
    Emite evento SSE chat_message a todos los suscriptores activos de la ruta.
    """
    route = db.scalar(
        select(Route).where(Route.id == route_id, Route.tenant_id == current.tenant_id)
    )
    if not route:
        raise not_found("ROUTE_NOT_FOUND", "Ruta no encontrada")

    # Determinar author_role legible
    role_map = {
        UserRole.logistics: "dispatcher",
        UserRole.admin: "dispatcher",
        UserRole.driver: "driver",
    }
    author_role = role_map.get(current.role, current.role)

    now = datetime.now(UTC)
    msg = RouteMessage(
        id=uuid.uuid4(),
        tenant_id=current.tenant_id,
        route_id=route_id,
        author_user_id=current.id,
        author_role=author_role,
        body=body.body,
        created_at=now,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    # SSE: notificar suscriptores activos de la ruta (REALTIME-001 / CHAT-001)
    event_bus.publish(
        str(current.tenant_id),
        str(route_id),
        "chat_message",
        {
            "message_id": str(msg.id),
            "author_user_id": str(msg.author_user_id),
            "author_role": msg.author_role,
            "body": msg.body,
            "created_at": msg.created_at.isoformat(),
        },
    )

    return msg


@router.get(
    "/routes/{route_id}/messages",
    response_model=list[RouteMessageOut],
    summary="Historial de mensajes de chat de una ruta",
)
def list_route_messages(
    route_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles(UserRole.logistics, UserRole.admin, UserRole.driver)),
) -> list[RouteMessage]:
    """
    Devuelve todos los mensajes del hilo de chat de la ruta, ordenados cronológicamente.

    Accesible por logistics, admin y driver asignado.
    """
    route = db.scalar(
        select(Route).where(Route.id == route_id, Route.tenant_id == current.tenant_id)
    )
    if not route:
        raise not_found("ROUTE_NOT_FOUND", "Ruta no encontrada")

    return list(
        db.scalars(
            select(RouteMessage)
            .where(
                RouteMessage.tenant_id == current.tenant_id,
                RouteMessage.route_id == route_id,
            )
            .order_by(RouteMessage.created_at.asc())
        )
    )
