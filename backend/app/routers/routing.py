"""
Routing POC — Bloques B + D
Bloque B — Planificación (dispatcher):
  GET  /orders/ready-to-dispatch         — pedidos listos para asignar a ruta
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
from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import CurrentUser, require_roles
from app.errors import conflict, forbidden, not_found, unprocessable
from app.optimization.google_provider import GoogleRouteOptimizationProvider
from app.optimization.mock_provider import MockRouteOptimizationProvider
from app.optimization.protocol import OptimizationRequest, OptimizationWaypoint, RouteOptimizationProvider
from app.models import (
    Customer,
    Driver,
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
    RouteStatus,
    RouteStop,
    RouteStopStatus,
    UserRole,
    Vehicle,
)
from app.schemas import (
    IncidentResolveRequest,
    IncidentCreateRequest,
    IncidentOut,
    IncidentsListResponse,
    RouteNextStopResponse,
    RouteEventsListResponse,
    RouteEventOut,
    RouteOut,
    RouteStopArriveRequest,
    RouteStopCompleteRequest,
    RouteStopFailRequest,
    RouteStopSkipRequest,
    RouteStopOut,
    RoutesListResponse,
)

router = APIRouter(tags=["Routing"])


# ============================================================================
# HELPERS
# ============================================================================


def _serialize_stop(stop: RouteStop) -> RouteStopOut:
    return RouteStopOut.model_validate(stop)


def _serialize_route(db: Session, tenant_id: uuid.UUID, route: Route) -> RouteOut:
    stops = list(
        db.scalars(
            select(RouteStop)
            .where(RouteStop.tenant_id == tenant_id, RouteStop.route_id == route.id)
            .order_by(RouteStop.sequence_number)
        )
    )
    data = RouteOut.model_validate(route)
    data.stops = [_serialize_stop(s) for s in stops]
    return data


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
# GET /orders/ready-to-dispatch
# ============================================================================


@router.get("/orders/ready-to-dispatch", response_model=dict)
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
    for stop in stops:
        order = db.scalar(
            select(Order).where(Order.id == stop.order_id, Order.tenant_id == current.tenant_id)
        )
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

    missing_geo: list[str] = []
    waypoints: list[OptimizationWaypoint] = []
    for stop in stops:
        order = db.scalar(
            select(Order).where(Order.id == stop.order_id, Order.tenant_id == current.tenant_id)
        )
        if not order:
            raise not_found("ENTITY_NOT_FOUND", f"Pedido {stop.order_id} no encontrado")

        customer = db.scalar(
            select(Customer).where(
                Customer.id == order.customer_id,
                Customer.tenant_id == current.tenant_id,
            )
        )
        if not customer or customer.lat is None or customer.lng is None:
            missing_geo.append(str(order.id))
            continue

        waypoints.append(
            OptimizationWaypoint(
                order_id=order.id,
                lat=float(customer.lat),
                lng=float(customer.lng),
                service_minutes=stop.estimated_service_minutes,
            )
        )

    if missing_geo:
        raise unprocessable(
            "MISSING_GEO",
            f"Los siguientes pedidos tienen cliente sin coordenadas: {', '.join(missing_geo)}",
        )

    request = OptimizationRequest(
        route_id=route.id,
        depot_lat=settings.route_optimization_depot_lat,
        depot_lng=settings.route_optimization_depot_lng,
        waypoints=waypoints,
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
    if source_route.status not in (RouteStatus.planned, RouteStatus.dispatched):
        raise unprocessable("INVALID_STATE_TRANSITION", "Solo se pueden mover paradas de rutas en estado planned o dispatched")

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
    if target_route.status not in (RouteStatus.planned, RouteStatus.dispatched):
        raise unprocessable("INVALID_STATE_TRANSITION", "Solo se pueden añadir paradas a rutas en estado planned o dispatched")

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
        items=[_serialize_route(db, current.tenant_id, r) for r in rows],
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
    next_stop = _serialize_stop(remaining[0]) if remaining else None
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
