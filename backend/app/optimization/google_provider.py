"""
GoogleRouteOptimizationProvider

Implementación real del RouteOptimizationProvider usando:
  - Application Default Credentials (ADC) / service account
  - Route Optimization API (optimizeTours)

No persiste secretos ni credenciales en el repo.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
from google.auth import default as google_auth_default
from google.auth.transport.requests import Request as GoogleAuthRequest

from app.optimization.protocol import (
    OptimizationRequest,
    OptimizationResult,
    OptimizedStop,
    RouteOptimizationProvider,
)

_CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
_BASE_URL = "https://routeoptimization.googleapis.com/v1"


def _parse_rfc3339(value: str) -> datetime:
    # Route Optimization retorna RFC3339 (normalmente con sufijo Z).
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class GoogleRouteOptimizationProvider(RouteOptimizationProvider):
    def __init__(self, *, project_id: str, location: str = "global", timeout_seconds: float = 30.0) -> None:
        if not project_id.strip():
            raise RuntimeError("GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID is required")
        self.project_id = project_id.strip()
        self.location = location.strip() or "global"
        self.timeout_seconds = timeout_seconds

    def _fetch_access_token(self) -> str:
        credentials, _ = google_auth_default(scopes=[_CLOUD_PLATFORM_SCOPE])
        if not credentials.valid or not credentials.token:
            credentials.refresh(GoogleAuthRequest())
        if not credentials.token:
            raise RuntimeError("Unable to obtain Google access token from ADC")
        return credentials.token

    def _build_parent(self) -> str:
        if self.location:
            return f"projects/{self.project_id}/locations/{self.location}"
        return f"projects/{self.project_id}"

    def _build_body(self, request: OptimizationRequest) -> dict:
        shipments = []
        for waypoint in request.waypoints:
            shipments.append(
                {
                    "label": str(waypoint.order_id),
                    "deliveries": [
                        {
                            "arrivalLocation": {
                                "latLng": {
                                    "latitude": waypoint.lat,
                                    "longitude": waypoint.lng,
                                }
                            },
                            "duration": f"{max(1, waypoint.service_minutes) * 60}s",
                        }
                    ],
                }
            )

        model = {
            "shipments": shipments,
            "vehicles": [
                {
                    "label": "vehicle-0",
                    "startLocation": {
                        "latLng": {
                            "latitude": request.depot_lat,
                            "longitude": request.depot_lng,
                        }
                    },
                    "endLocation": {
                        "latLng": {
                            "latitude": request.depot_lat,
                            "longitude": request.depot_lng,
                        }
                    },
                }
            ],
        }
        return {
            "label": str(request.route_id),
            "considerRoadTraffic": True,
            "model": model,
        }

    def _build_result(self, request: OptimizationRequest, response_json: dict) -> OptimizationResult:
        routes = response_json.get("routes") or []
        if not routes:
            raise RuntimeError("Google Route Optimization returned no routes")

        visits = routes[0].get("visits") or []
        label_to_visit: dict[str, tuple[int, datetime]] = {}
        for i, visit in enumerate(visits, start=1):
            shipment_label = visit.get("shipmentLabel")
            start_time = visit.get("startTime")
            if not shipment_label:
                continue
            eta = _parse_rfc3339(start_time) if start_time else datetime.now(UTC)
            label_to_visit[shipment_label] = (i, eta)

        missing_labels = [str(w.order_id) for w in request.waypoints if str(w.order_id) not in label_to_visit]
        if missing_labels:
            raise RuntimeError(
                "Google Route Optimization response missing shipments: "
                + ", ".join(missing_labels)
            )

        stops = []
        for waypoint in request.waypoints:
            seq, eta = label_to_visit[str(waypoint.order_id)]
            stops.append(
                OptimizedStop(
                    order_id=waypoint.order_id,
                    sequence_number=seq,
                    estimated_arrival_at=eta,
                )
            )
        stops.sort(key=lambda s: s.sequence_number)

        request_id = response_json.get("requestLabel") or str(uuid.uuid4())
        enriched_response = dict(response_json)
        enriched_response["provider"] = "google"
        return OptimizationResult(
            request_id=request_id,
            response_json=enriched_response,
            stops=stops,
        )

    def optimize(self, request: OptimizationRequest) -> OptimizationResult:
        token = self._fetch_access_token()
        parent = self._build_parent()
        url = f"{_BASE_URL}/{parent}:optimizeTours"
        body = self._build_body(request)
        try:
            response = httpx.post(
                url,
                json=body,
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            raw = response.json()
        except httpx.HTTPError as exc:
            detail = getattr(exc.response, "text", str(exc))
            raise RuntimeError(f"Google Route Optimization call failed: {detail}") from exc
        except ValueError as exc:
            raise RuntimeError("Google Route Optimization returned invalid JSON") from exc

        return self._build_result(request, raw)
