"""
GoogleRouteOptimizationProvider

Implementación real del RouteOptimizationProvider usando:
  - Application Default Credentials (ADC) / service account
  - Route Optimization API (optimizeTours)

No persiste secretos ni credenciales en el repo.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime, time, timedelta

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


def _to_rfc3339_utc(value: datetime) -> str:
    # Route Optimization rechaza nanos en globalStartTime/globalEndTime.
    # Emitimos segundos enteros en RFC3339 UTC.
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class GoogleRouteOptimizationProvider(RouteOptimizationProvider):
    def __init__(self, *, project_id: str, location: str = "global", timeout_seconds: float = 30.0) -> None:
        if not project_id.strip():
            raise RuntimeError("GOOGLE_ROUTE_OPTIMIZATION_PROJECT_ID is required")
        self.project_id = project_id.strip()
        self.location = location.strip() or "global"
        self.timeout_seconds = timeout_seconds

    def _fetch_access_token(self) -> str:
        # Soporte para credenciales en variable de entorno (Vercel / entornos serverless).
        # Si GOOGLE_APPLICATION_CREDENTIALS_JSON existe, carga el service account desde JSON.
        # Si no, usa Application Default Credentials (ADC) estándar (Docker, GCE, etc.).
        credentials_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        if credentials_json:
            from google.oauth2 import service_account
            info = json.loads(credentials_json)
            credentials = service_account.Credentials.from_service_account_info(
                info, scopes=[_CLOUD_PLATFORM_SCOPE]
            )
        else:
            credentials, _ = google_auth_default(scopes=[_CLOUD_PLATFORM_SCOPE])
        if not credentials.valid or not credentials.token:
            credentials.refresh(GoogleAuthRequest())
        if not credentials.token:
            raise RuntimeError("Unable to obtain Google access token")
        return credentials.token

    def _build_parent(self) -> str:
        location = self.location.strip().lower()
        if location and location != "global":
            return f"projects/{self.project_id}/locations/{self.location.strip()}"
        return f"projects/{self.project_id}"

    def _build_global_window(self, request: OptimizationRequest) -> tuple[datetime, datetime]:
        now = datetime.now(UTC)
        min_start = now + timedelta(minutes=5)

        if request.service_date is not None:
            service_start = datetime.combine(request.service_date, time(hour=7), tzinfo=UTC)
            service_end = datetime.combine(request.service_date, time(hour=19), tzinfo=UTC)
        else:
            service_start = now
            service_end = now + timedelta(hours=12)

        global_start = service_start if service_start > min_start else min_start
        global_end = service_end if service_end > global_start else (global_start + timedelta(hours=12))
        return global_start, global_end

    def _build_time_windows(
        self,
        waypoint: "OptimizationWaypoint",
        service_date: "date | None",
        global_start: datetime,
        global_end: datetime,
    ) -> list[dict] | None:
        """
        Construye la lista timeWindows para un waypoint si tiene ventana definida.
        Retorna None si el waypoint no tiene restricción horaria.

        La ventana se ancla a service_date (o a global_start.date() como fallback).
        Si window_end cae antes o igual que window_start (p. ej. 09:00-08:00),
        se ignora la ventana para evitar enviar restricciones imposibles a Google.
        """
        if waypoint.window_start is None or waypoint.window_end is None:
            return None

        anchor_date = service_date if service_date is not None else global_start.date()
        from datetime import datetime as _dt
        window_start_dt = _dt.combine(anchor_date, waypoint.window_start, tzinfo=UTC)
        window_end_dt = _dt.combine(anchor_date, waypoint.window_end, tzinfo=UTC)

        if window_end_dt <= window_start_dt:
            return None  # ventana inválida — ignorar

        # Recortar al rango global para evitar ventanas fuera del horizonte
        window_start_dt = max(window_start_dt, global_start)
        window_end_dt = min(window_end_dt, global_end)

        if window_end_dt <= window_start_dt:
            return None  # ventana recortada quedó vacía

        return [
            {
                "startTime": _to_rfc3339_utc(window_start_dt),
                "endTime": _to_rfc3339_utc(window_end_dt),
            }
        ]

    def _build_body(self, request: OptimizationRequest) -> dict:
        global_start, global_end = self._build_global_window(request)
        shipments = []
        for waypoint in request.waypoints:
            delivery: dict = {
                "arrivalLocation": {
                    "latitude": waypoint.lat,
                    "longitude": waypoint.lng,
                },
                "duration": f"{max(1, waypoint.service_minutes) * 60}s",
            }
            time_windows = self._build_time_windows(
                waypoint, request.service_date, global_start, global_end
            )
            if time_windows:
                delivery["timeWindows"] = time_windows

            # F2 — CAPACITY-001: demanda de carga del pedido en gramos (int64).
            # Usamos gramos para preservar decimales de kg sin perder precisión.
            if waypoint.weight_kg is not None:
                delivery["loadDemands"] = {
                    "weight_kg": {"amount": str(round(waypoint.weight_kg * 1000))}
                }

            shipments.append(
                {
                    "label": str(waypoint.order_id),
                    "deliveries": [delivery],
                }
            )

        # F2 — CAPACITY-001: límite de carga del vehículo en gramos.
        vehicle: dict = {
            "label": "vehicle-0",
            "startLocation": {
                "latitude": request.depot_lat,
                "longitude": request.depot_lng,
            },
            "endLocation": {
                "latitude": request.depot_lat,
                "longitude": request.depot_lng,
            },
        }
        if request.vehicle_capacity_kg is not None:
            vehicle["loadLimits"] = {
                "weight_kg": {"maxLoad": str(round(request.vehicle_capacity_kg * 1000))}
            }

        # F4 — DOUBLE-TRIP-001: restricción de inicio para segundo viaje.
        # startTimeWindows con solo startTime indica "no antes de este momento".
        if request.trip_start_after is not None:
            vehicle["startTimeWindows"] = [
                {"startTime": _to_rfc3339_utc(request.trip_start_after)}
            ]

        model = {
            "globalStartTime": _to_rfc3339_utc(global_start),
            "globalEndTime": _to_rfc3339_utc(global_end),
            "shipments": shipments,
            "vehicles": [vehicle],
        }
        return {
            "label": str(request.route_id),
            "considerRoadTraffic": True,
            "populateTransitionPolylines": True,
            "model": model,
        }

    def _build_result(self, request: OptimizationRequest, response_json: dict) -> OptimizationResult:
        routes = response_json.get("routes") or []

        # --- Mapa de shipments que Google explícitamente omitió ---
        # skippedShipments es el mecanismo oficial de Google para indicar
        # que no pudo enrutar un pedido (ventana imposible, capacidad, etc.).
        # No es un error fatal: procedemos con las paradas que sí se enrutaron.
        skipped_reasons: dict[str, str] = {}
        for entry in response_json.get("skippedShipments", []):
            label = entry.get("label") or ""
            reasons = entry.get("reasons") or [{}]
            code = reasons[0].get("code", "UNKNOWN") if reasons else "UNKNOWN"
            skipped_reasons[label] = code

        if not routes and not skipped_reasons:
            # Respuesta completamente vacía — ni rutas ni omisiones declaradas
            raise RuntimeError("Google Route Optimization returned no routes")

        # --- Construir mapa label → (secuencia, ETA) a partir de las visitas ---
        visits = routes[0].get("visits") if routes else []
        label_to_visit: dict[str, tuple[int, datetime]] = {}
        for i, visit in enumerate(visits or [], start=1):
            shipment_label = visit.get("shipmentLabel")
            start_time = visit.get("startTime")
            if not shipment_label:
                continue
            eta = _parse_rfc3339(start_time) if start_time else datetime.now(UTC)
            label_to_visit[shipment_label] = (i, eta)

        # --- Detectar pedidos ausentes sin justificación ---
        # Un pedido "ausente" es aquel que no aparece en visitas NI en skippedShipments.
        # Esto sí es un error: indica respuesta incompleta o bug en el request.
        truly_missing = [
            str(w.order_id)
            for w in request.waypoints
            if str(w.order_id) not in label_to_visit and str(w.order_id) not in skipped_reasons
        ]
        if truly_missing:
            raise RuntimeError(
                "Google Route Optimization response missing shipments (not in visits nor skippedShipments): "
                + ", ".join(truly_missing)
            )

        # --- Construir stops solo para pedidos enrutados ---
        # Los pedidos en skippedShipments no reciben ETA; quedan sin actualizar.
        stops = []
        for waypoint in request.waypoints:
            label = str(waypoint.order_id)
            if label not in label_to_visit:
                # Pedido omitido por Google — loguear y continuar
                reason = skipped_reasons.get(label, "UNKNOWN")
                import logging
                logging.getLogger(__name__).warning(
                    "Shipment skipped by Google Route Optimization: %s reason=%s", label, reason
                )
                continue
            seq, eta = label_to_visit[label]
            stops.append(
                OptimizedStop(
                    order_id=waypoint.order_id,
                    sequence_number=seq,
                    estimated_arrival_at=eta,
                )
            )
        stops.sort(key=lambda s: s.sequence_number)

        if not stops:
            raise RuntimeError(
                "Google Route Optimization skipped all shipments: "
                + ", ".join(f"{k}={v}" for k, v in skipped_reasons.items())
            )

        request_id = response_json.get("requestLabel") or str(uuid.uuid4())
        enriched_response = dict(response_json)
        enriched_response["provider"] = "google"
        if skipped_reasons:
            enriched_response["skipped_shipments_summary"] = skipped_reasons
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
