import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { DispatcherRoutingCard } from "../components/DispatcherRoutingCard";
import type { AvailableVehicleItem, ReadyToDispatchItem, RouteEventItem, RoutingRoute, RoutingRouteStop } from "../lib/api";

function renderCard(routes: RoutingRoute[], selectedRoute: RoutingRoute | null = null): string {
  const readyOrders: ReadyToDispatchItem[] = [];
  const vehicles: AvailableVehicleItem[] = [];
  const events: RouteEventItem[] = [];

  return renderToStaticMarkup(
    <DispatcherRoutingCard
      serviceDate="2026-04-11"
      onServiceDateChange={() => {}}
      routeStatus="all"
      onRouteStatusChange={() => {}}
      loading={false}
      canManage={true}
      readyOrders={readyOrders}
      availableVehicles={vehicles}
      routes={routes}
      selectedRouteId=""
      onSelectedRouteIdChange={() => {}}
      selectedRoute={selectedRoute}
      routeEvents={events}
      routeDetailLoading={false}
      planId=""
      onPlanIdChange={() => {}}
      planVehicleId=""
      onPlanVehicleIdChange={() => {}}
      planDriverId=""
      onPlanDriverIdChange={() => {}}
      planOrderIds=""
      onPlanOrderIdsChange={() => {}}
      creatingPlan={false}
      optimizingRouteId={null}
      dispatchingRouteId={null}
      moveSourceRouteId=""
      onMoveSourceRouteIdChange={() => {}}
      moveStopId=""
      onMoveStopIdChange={() => {}}
      moveTargetRouteId=""
      onMoveTargetRouteIdChange={() => {}}
      movingStop={false}
      onRefresh={() => {}}
      onCreatePlan={() => {}}
      onOptimizeRoute={() => {}}
      onDispatchRoute={() => {}}
      onMoveStop={() => {}}
    />,
  );
}

function makeStop(overrides: Partial<RoutingRouteStop> = {}): RoutingRouteStop {
  return {
    id: "44444444-4444-4444-4444-444444444444",
    route_id: "33333333-3333-3333-3333-333333333333",
    order_id: "22222222-2222-2222-2222-222222222222",
    sequence_number: 1,
    estimated_arrival_at: null,
    estimated_service_minutes: 10,
    status: "pending",
    arrived_at: null,
    completed_at: null,
    failed_at: null,
    failure_reason: null,
    customer_lat: 40.4168,
    customer_lng: -3.7038,
    created_at: "2026-04-11T10:00:00Z",
    updated_at: "2026-04-11T10:00:00Z",
    ...overrides,
  };
}

test("renders dispatcher routing controls and empty states", () => {
  const html = renderCard([]);
  assert.match(html, /Dispatcher Routing/);
  assert.match(html, /Pedidos Ready to Dispatch/);
  assert.match(html, /Vehículos Disponibles/);
  assert.match(html, /Planificar Ruta/);
  assert.match(html, /Sin rutas para los filtros actuales\./);
  assert.match(html, /Move Stop/);
});

test("preserves backend route order without frontend re-sorting", () => {
  const routes: RoutingRoute[] = [
    {
      id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      plan_id: "11111111-1111-1111-1111-111111111111",
      vehicle_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      driver_id: null,
      service_date: "2026-04-11",
      status: "draft",
      version: 1,
      optimization_request_id: null,
      optimization_response_json: null,
      created_at: "2026-04-11T10:00:00Z",
      updated_at: "2026-04-11T10:00:00Z",
      dispatched_at: null,
      completed_at: null,
      stops: [],
    },
    {
      id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      plan_id: "22222222-2222-2222-2222-222222222222",
      vehicle_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      driver_id: null,
      service_date: "2026-04-11",
      status: "planned",
      version: 2,
      optimization_request_id: "req-1",
      optimization_response_json: {},
      created_at: "2026-04-11T10:05:00Z",
      updated_at: "2026-04-11T10:05:00Z",
      dispatched_at: null,
      completed_at: null,
      stops: [],
    },
  ];

  const html = renderCard(routes);
  const firstIndex = html.indexOf("bbbbbbbb");
  const secondIndex = html.indexOf("aaaaaaaa");

  assert.ok(firstIndex >= 0, "first route id should render");
  assert.ok(secondIndex >= 0, "second route id should render");
  assert.ok(firstIndex < secondIndex, "route order should match backend order");
});

test("renders route map section when selected route is available", () => {
  const selectedRoute: RoutingRoute = {
    id: "33333333-3333-3333-3333-333333333333",
    plan_id: "11111111-1111-1111-1111-111111111111",
    vehicle_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    driver_id: null,
    service_date: "2026-04-11",
    status: "planned",
    version: 1,
    optimization_request_id: null,
    optimization_response_json: null,
    created_at: "2026-04-11T10:00:00Z",
    updated_at: "2026-04-11T10:00:00Z",
    dispatched_at: null,
    completed_at: null,
    stops: [makeStop()],
  };

  const html = renderCard([selectedRoute], selectedRoute);
  assert.match(html, /Mapa de Ruta/);
  assert.match(html, /paradas geo-ready: 1/);
});
