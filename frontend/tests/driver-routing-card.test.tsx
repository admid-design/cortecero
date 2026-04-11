import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { DriverRoutingCard } from "../components/DriverRoutingCard";
import type {
  IncidentCreateRequest,
  RouteNextStopResponse,
  RoutingRoute,
  RoutingRouteStop,
} from "../lib/api";

// ── Fixtures ─────────────────────────────────────────────────────────────────

function makeStop(overrides: Partial<RoutingRouteStop> = {}): RoutingRouteStop {
  return {
    id: "stop-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    route_id: "route-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    order_id: "order-cccc-cccc-cccc-cccccccccccc",
    sequence_number: 1,
    estimated_arrival_at: null,
    estimated_service_minutes: 15,
    status: "pending",
    arrived_at: null,
    completed_at: null,
    failed_at: null,
    failure_reason: null,
    created_at: "2026-04-11T08:00:00Z",
    updated_at: "2026-04-11T08:00:00Z",
    ...overrides,
  };
}

function makeRoute(overrides: Partial<RoutingRoute> = {}): RoutingRoute {
  return {
    id: "route-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    plan_id: "plan-dddd-dddd-dddd-dddddddddddd",
    vehicle_id: "vehicle-eeee-eeee-eeee-eeeeeeeeeeee",
    driver_id: "driver-ffff-ffff-ffff-ffffffffffff",
    service_date: "2026-04-11",
    status: "dispatched",
    version: 1,
    optimization_request_id: null,
    optimization_response_json: null,
    created_at: "2026-04-11T07:00:00Z",
    updated_at: "2026-04-11T07:00:00Z",
    dispatched_at: "2026-04-11T08:00:00Z",
    completed_at: null,
    stops: [makeStop()],
    ...overrides,
  };
}

function makeNextStopResponse(stop: RoutingRouteStop | null, remaining = 1): RouteNextStopResponse {
  return {
    route_id: "route-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    next_stop: stop,
    remaining_stops: remaining,
  };
}

const NO_OP = () => {};
const NO_OP_INCIDENT = (_payload: IncidentCreateRequest) => {};

function renderCard(
  routes: RoutingRoute[],
  overrides: {
    selectedRoute?: RoutingRoute | null;
    selectedRouteId?: string;
    nextStopResponse?: RouteNextStopResponse | null;
  } = {},
): string {
  return renderToStaticMarkup(
    <DriverRoutingCard
      loading={false}
      routes={routes}
      selectedRouteId={overrides.selectedRouteId ?? ""}
      onSelectedRouteIdChange={NO_OP}
      selectedRoute={overrides.selectedRoute ?? null}
      nextStopResponse={overrides.nextStopResponse ?? null}
      nextStopLoading={false}
      actionLoadingStopId={null}
      incidentLoading={false}
      errorMessage={null}
      successMessage={null}
      onRefresh={NO_OP}
      onArrive={NO_OP}
      onComplete={NO_OP}
      onFail={NO_OP}
      onSkip={NO_OP}
      onReportIncident={NO_OP_INCIDENT}
    />,
  );
}

// ── Tests ────────────────────────────────────────────────────────────────────

test("renders card title", () => {
  const html = renderCard([]);
  assert.match(html, /Driver — Mis Rutas/);
});

test("shows empty state when no routes", () => {
  const html = renderCard([]);
  assert.match(html, /Sin rutas asignadas para hoy\./);
});

test("renders route selector when routes exist", () => {
  const route = makeRoute();
  const html = renderCard([route]);
  assert.match(html, /Selecciona una ruta/);
  assert.match(html, /dispatched/);
  assert.match(html, /1 parada/);
});

test("preserves backend route order without frontend re-sorting", () => {
  const routeA = makeRoute({ id: "aaaa-aaaa", service_date: "2026-04-11", status: "dispatched" });
  const routeB = makeRoute({ id: "bbbb-bbbb", service_date: "2026-04-11", status: "in_progress" });
  const html = renderCard([routeA, routeB]);

  const idxA = html.indexOf("aaaa-aaaa");
  const idxB = html.indexOf("bbbb-bbbb");
  assert.ok(idxA >= 0, "routeA id should render");
  assert.ok(idxB >= 0, "routeB id should render");
  assert.ok(idxA < idxB, "route order must match backend order");
});

test("shows next stop banner when route selected and next stop available", () => {
  const route = makeRoute();
  const stop = route.stops[0]!;
  const html = renderCard([route], {
    selectedRoute: route,
    selectedRouteId: route.id,
    nextStopResponse: makeNextStopResponse(stop, 1),
  });
  assert.match(html, /Siguiente parada/i);
  assert.match(html, /#1/);
  assert.match(html, /1 restante/);
});

test("shows no pending stops message when next_stop is null", () => {
  const route = makeRoute({ stops: [] });
  const html = renderCard([route], {
    selectedRoute: route,
    selectedRouteId: route.id,
    nextStopResponse: makeNextStopResponse(null, 0),
  });
  assert.match(html, /No hay paradas pendientes\./);
});

test("shows navigation fallback for stops without coordinates", () => {
  // API schema does not embed lat/lng in RouteStopOut —
  // button must be disabled with a clear explanation.
  const route = makeRoute();
  const html = renderCard([route], {
    selectedRoute: route,
    selectedRouteId: route.id,
  });
  assert.match(html, /Navegaci[oó]n no disponible/i);
  assert.match(html, /coordenadas no incluidas/i);
});

test("shows Llegar button for pending stop", () => {
  const route = makeRoute({ stops: [makeStop({ status: "pending" })] });
  const html = renderCard([route], {
    selectedRoute: route,
    selectedRouteId: route.id,
  });
  assert.match(html, /Llegar/);
  assert.match(html, /Omitir/);
  // Completar only visible after arriving
  assert.doesNotMatch(html, /Completar/);
});

test("shows Completar and Fallar buttons for arrived stop", () => {
  const route = makeRoute({ stops: [makeStop({ status: "arrived" })] });
  const html = renderCard([route], {
    selectedRoute: route,
    selectedRouteId: route.id,
  });
  assert.match(html, /Completar/);
  assert.match(html, /Fallar/);
  // Llegar not shown when already arrived
  assert.doesNotMatch(html, /Llegar/);
});

test("hides action buttons for terminal stops", () => {
  for (const status of ["completed", "failed", "skipped"] as const) {
    const route = makeRoute({ stops: [makeStop({ status })] });
    const html = renderCard([route], {
      selectedRoute: route,
      selectedRouteId: route.id,
    });
    assert.doesNotMatch(html, /Llegar/, `${status}: Llegar should not render`);
    assert.doesNotMatch(html, /Completar/, `${status}: Completar should not render`);
    assert.doesNotMatch(html, /Fallar/, `${status}: Fallar should not render`);
  }
});

test("always shows Reportar incidencia button for non-terminal stops", () => {
  const route = makeRoute({ stops: [makeStop({ status: "pending" })] });
  const html = renderCard([route], {
    selectedRoute: route,
    selectedRouteId: route.id,
  });
  assert.match(html, /Reportar incidencia/);
});

test("renders failure_reason when stop has it", () => {
  const stop = makeStop({ status: "failed", failure_reason: "Cliente no estaba en casa" });
  const route = makeRoute({ stops: [stop] });
  const html = renderCard([route], {
    selectedRoute: route,
    selectedRouteId: route.id,
  });
  assert.match(html, /Cliente no estaba en casa/);
});

test("shows error message when errorMessage is set", () => {
  const html = renderToStaticMarkup(
    <DriverRoutingCard
      loading={false}
      routes={[]}
      selectedRouteId=""
      onSelectedRouteIdChange={NO_OP}
      selectedRoute={null}
      nextStopResponse={null}
      nextStopLoading={false}
      actionLoadingStopId={null}
      incidentLoading={false}
      errorMessage="Error de conexión"
      successMessage={null}
      onRefresh={NO_OP}
      onArrive={NO_OP}
      onComplete={NO_OP}
      onFail={NO_OP}
      onSkip={NO_OP}
      onReportIncident={NO_OP_INCIDENT}
    />,
  );
  assert.match(html, /Error de conexi[oó]n/);
});

test("shows success message when successMessage is set", () => {
  const html = renderToStaticMarkup(
    <DriverRoutingCard
      loading={false}
      routes={[]}
      selectedRouteId=""
      onSelectedRouteIdChange={NO_OP}
      selectedRoute={null}
      nextStopResponse={null}
      nextStopLoading={false}
      actionLoadingStopId={null}
      incidentLoading={false}
      errorMessage={null}
      successMessage="Parada #1: llegada registrada."
      onRefresh={NO_OP}
      onArrive={NO_OP}
      onComplete={NO_OP}
      onFail={NO_OP}
      onSkip={NO_OP}
      onReportIncident={NO_OP_INCIDENT}
    />,
  );
  assert.match(html, /llegada registrada/);
});

test("shows Cargando rutas when loading=true and no routes", () => {
  const html = renderToStaticMarkup(
    <DriverRoutingCard
      loading={true}
      routes={[]}
      selectedRouteId=""
      onSelectedRouteIdChange={NO_OP}
      selectedRoute={null}
      nextStopResponse={null}
      nextStopLoading={false}
      actionLoadingStopId={null}
      incidentLoading={false}
      errorMessage={null}
      successMessage={null}
      onRefresh={NO_OP}
      onArrive={NO_OP}
      onComplete={NO_OP}
      onFail={NO_OP}
      onSkip={NO_OP}
      onReportIncident={NO_OP_INCIDENT}
    />,
  );
  assert.match(html, /Cargando rutas/);
});
