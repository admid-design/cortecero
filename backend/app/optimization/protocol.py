"""
Contrato del proveedor de optimización de rutas.

Define el Protocol y los DTOs de entrada/salida.
El módulo no importa dependencias de proveedor externo:
cualquier implementación puede satisfacer el Protocol
sin acoplarse a la infraestructura de Google.

Proveedores disponibles en E.1:
  - MockRouteOptimizationProvider  (siempre activo en tests y entornos sin credenciales)

Proveedores previstos en E.2:
  - GoogleRouteOptimizationProvider  (service account / ADC, project + location)
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Protocol


@dataclass
class OptimizationWaypoint:
    """Un punto de entrega a visitar en la ruta."""

    order_id: uuid.UUID
    lat: float
    lng: float
    service_minutes: int = 10
    # F1 — TW-001: ventana horaria de entrega del cliente (time en hora local UTC).
    # Si ambos son None, no se envía restricción de ventana al proveedor.
    window_start: time | None = None
    window_end: time | None = None
    # F2 — CAPACITY-001: peso del pedido en kg.
    # Si None, no se envía demanda de carga al proveedor.
    weight_kg: float | None = None
    # F5 — ADR-001: el pedido contiene mercancías peligrosas.
    requires_adr: bool = False
    # F6 — ZBE-001: el cliente está en zona de bajas emisiones (requiere vehículo ZBE autorizado).
    requires_zbe: bool = False


@dataclass
class OptimizationRequest:
    """
    Solicitud de optimización para una ruta.

    depot_lat / depot_lng: coordenadas de la bodega de salida.
    waypoints: lista de paradas en el orden *original* enviado por el dispatcher.
    El proveedor puede reordenarlas según su criterio de optimización.
    """

    route_id: uuid.UUID
    depot_lat: float
    depot_lng: float
    service_date: date | None = None
    waypoints: list[OptimizationWaypoint] = field(default_factory=list)
    # F2 — CAPACITY-001: capacidad máxima del vehículo en kg.
    # Si None, no se envía restricción de carga al proveedor.
    vehicle_capacity_kg: float | None = None
    # F4 — DOUBLE-TRIP-001: momento mínimo de inicio del vehículo (para viaje 2).
    # Si None, el vehículo puede arrancar en cualquier momento dentro del globalStartTime.
    trip_start_after: datetime | None = None
    # F5 — ADR-001: el vehículo está certificado para mercancías peligrosas.
    vehicle_adr_certified: bool = False
    # F6 — ZBE-001: el vehículo está autorizado para circular por zona de bajas emisiones.
    vehicle_zbe_allowed: bool = False


@dataclass
class OptimizedStop:
    """Resultado de optimización para una parada."""

    order_id: uuid.UUID
    sequence_number: int        # 1-based; orden óptimo devuelto por el proveedor
    estimated_arrival_at: datetime


@dataclass
class OptimizationResult:
    """Resultado completo devuelto por el proveedor."""

    request_id: str             # ID asignado por el proveedor (o UUID generado por mock)
    response_json: dict         # Raw response del proveedor; se persiste en optimization_response_json
    stops: list[OptimizedStop]


class RouteOptimizationProvider(Protocol):
    """
    Interfaz cerrada del proveedor de optimización.

    Toda implementación concreta debe satisfacer esta firma.
    El caller no importa ninguna clase concreta; solo este Protocol.
    """

    def optimize(self, request: OptimizationRequest) -> OptimizationResult:
        """
        Recibe una solicitud con waypoints y devuelve la secuencia óptima
        con tiempos estimados de llegada.

        Raises:
            RuntimeError: si el proveedor no puede completar la optimización.
        """
        ...
