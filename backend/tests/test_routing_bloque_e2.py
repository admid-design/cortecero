"""
Bloque E.2 — Integración real de Route Optimization (Google, ADC)

Cubre:
  - selección de proveedor según config (mock vs google)
  - llamada HTTP esperada a optimizeTours
  - parseo de respuesta en secuencia/ETA
  - error explícito cuando faltan shipments en respuesta
"""

import uuid
from datetime import UTC, datetime

import pytest

from app.optimization.google_provider import GoogleRouteOptimizationProvider
from app.optimization.mock_provider import MockRouteOptimizationProvider
from app.optimization.protocol import OptimizationRequest, OptimizationWaypoint
from app.routers import routing


def test_provider_factory_returns_mock_without_project_id(monkeypatch):
    monkeypatch.setattr(routing.settings, "google_route_optimization_project_id", "", raising=False)
    provider = routing._get_optimization_provider()
    assert isinstance(provider, MockRouteOptimizationProvider)


def test_provider_factory_returns_google_with_project_id(monkeypatch):
    monkeypatch.setattr(
        routing.settings,
        "google_route_optimization_project_id",
        "demo-project",
        raising=False,
    )
    monkeypatch.setattr(
        routing.settings,
        "google_route_optimization_location",
        "europe-west1",
        raising=False,
    )
    monkeypatch.setattr(
        routing.settings,
        "google_route_optimization_timeout_seconds",
        42.0,
        raising=False,
    )

    provider = routing._get_optimization_provider()
    assert isinstance(provider, GoogleRouteOptimizationProvider)
    assert provider.project_id == "demo-project"
    assert provider.location == "europe-west1"
    assert provider.timeout_seconds == 42.0


def test_google_provider_optimize_happy_path(monkeypatch):
    provider = GoogleRouteOptimizationProvider(
        project_id="demo-project",
        location="europe-west1",
        timeout_seconds=10.0,
    )
    monkeypatch.setattr(provider, "_fetch_access_token", lambda: "fake-token")

    order_a = uuid.uuid4()
    order_b = uuid.uuid4()
    request = OptimizationRequest(
        route_id=uuid.uuid4(),
        depot_lat=39.57,
        depot_lng=2.65,
        waypoints=[
            OptimizationWaypoint(order_id=order_a, lat=39.56, lng=2.63, service_minutes=10),
            OptimizationWaypoint(order_id=order_b, lat=39.58, lng=2.67, service_minutes=12),
        ],
    )

    captured: dict = {}

    class _Response:
        status_code = 200
        text = "ok"

        @staticmethod
        def raise_for_status() -> None:
            return None

        @staticmethod
        def json() -> dict:
            return {
                "requestLabel": "req-123",
                "routes": [
                    {
                        "transitions": [
                            {"routePolyline": {"points": "abc123"}},
                            {"routePolyline": {"points": "def456"}},
                        ],
                        "visits": [
                            {"shipmentLabel": str(order_b), "startTime": "2026-04-11T09:15:00Z"},
                            {"shipmentLabel": str(order_a), "startTime": "2026-04-11T09:30:00Z"},
                        ]
                    }
                ],
            }

    def _fake_post(url, *, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr("app.optimization.google_provider.httpx.post", _fake_post)

    result = provider.optimize(request)

    assert captured["url"] == "https://routeoptimization.googleapis.com/v1/projects/demo-project/locations/europe-west1:optimizeTours"
    assert captured["headers"]["Authorization"] == "Bearer fake-token"
    assert captured["timeout"] == 10.0
    assert captured["json"]["label"] == str(request.route_id)
    assert captured["json"]["populateTransitionPolylines"] is True
    assert len(captured["json"]["model"]["shipments"]) == 2

    assert result.request_id == "req-123"
    assert result.response_json["provider"] == "google"
    assert result.response_json["routes"][0]["transitions"][0]["routePolyline"]["points"] == "abc123"
    assert [str(stop.order_id) for stop in result.stops] == [str(order_b), str(order_a)]
    assert [stop.sequence_number for stop in result.stops] == [1, 2]
    assert result.stops[0].estimated_arrival_at == datetime(2026, 4, 11, 9, 15, tzinfo=UTC)


def test_google_provider_optimize_missing_shipment_raises(monkeypatch):
    provider = GoogleRouteOptimizationProvider(project_id="demo-project")
    monkeypatch.setattr(provider, "_fetch_access_token", lambda: "fake-token")

    order_a = uuid.uuid4()
    order_b = uuid.uuid4()
    request = OptimizationRequest(
        route_id=uuid.uuid4(),
        depot_lat=39.57,
        depot_lng=2.65,
        waypoints=[
            OptimizationWaypoint(order_id=order_a, lat=39.56, lng=2.63, service_minutes=10),
            OptimizationWaypoint(order_id=order_b, lat=39.58, lng=2.67, service_minutes=12),
        ],
    )

    class _Response:
        status_code = 200
        text = "ok"

        @staticmethod
        def raise_for_status() -> None:
            return None

        @staticmethod
        def json() -> dict:
            return {
                "requestLabel": "req-123",
                "routes": [
                    {
                        "visits": [
                            {"shipmentLabel": str(order_a), "startTime": "2026-04-11T09:30:00Z"},
                        ]
                    }
                ],
            }

    monkeypatch.setattr("app.optimization.google_provider.httpx.post", lambda *args, **kwargs: _Response())

    with pytest.raises(RuntimeError, match="missing shipments"):
        provider.optimize(request)
