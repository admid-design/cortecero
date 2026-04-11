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
from datetime import datetime
from typing import Protocol


@dataclass
class OptimizationWaypoint:
    """Un punto de entrega a visitar en la ruta."""

    order_id: uuid.UUID
    lat: float
    lng: float
    service_minutes: int = 10


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
    waypoints: list[OptimizationWaypoint] = field(default_factory=list)


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
