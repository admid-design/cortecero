"""
MockRouteOptimizationProvider

Devuelve la secuencia *original* de waypoints con estimated_arrival_at
calculado como: ahora + 15 min × posición_en_secuencia.

No llama a ningún servicio externo.
Activo por defecto en tests y en entornos sin credenciales de Google.
"""

import uuid
from datetime import UTC, datetime, timedelta

from app.optimization.protocol import (
    OptimizationRequest,
    OptimizationResult,
    OptimizedStop,
)

_MINUTES_PER_STOP = 15


class MockRouteOptimizationProvider:
    """Implementación mock del RouteOptimizationProvider Protocol."""

    def optimize(self, request: OptimizationRequest) -> OptimizationResult:
        now = datetime.now(UTC)
        request_id = str(uuid.uuid4())

        stops: list[OptimizedStop] = []
        for i, waypoint in enumerate(request.waypoints, start=1):
            stops.append(
                OptimizedStop(
                    order_id=waypoint.order_id,
                    sequence_number=i,
                    estimated_arrival_at=now + timedelta(minutes=_MINUTES_PER_STOP * i),
                )
            )

        response_json = {
            "provider": "mock",
            "request_id": request_id,
            "route_id": str(request.route_id),
            "depot": {"lat": request.depot_lat, "lng": request.depot_lng},
            "routes": [
                {
                    "visits": [
                        {
                            "order_id": str(s.order_id),
                            "sequence": s.sequence_number,
                            "estimated_arrival_at": s.estimated_arrival_at.isoformat(),
                        }
                        for s in stops
                    ]
                }
            ],
        }

        return OptimizationResult(
            request_id=request_id,
            response_json=response_json,
            stops=stops,
        )
