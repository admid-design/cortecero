import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { PlansTableCard } from "../components/PlansTableCard";
import type { Plan } from "../lib/api";

function makePlan(overrides: Partial<Plan> = {}): Plan {
  return {
    id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    service_date: "2026-04-13",
    zone_id: "11111111-1111-1111-1111-111111111111",
    status: "open",
    version: 1,
    vehicle_id: null,
    vehicle_code: null,
    vehicle_name: null,
    vehicle_capacity_kg: null,
    locked_at: null,
    locked_by: null,
    total_weight_kg: 0,
    orders_total: 0,
    orders_with_weight: 0,
    orders_missing_weight: 0,
    orders: [],
    ...overrides,
  };
}

function renderCard(plans: Plan[]): string {
  return renderToStaticMarkup(
    <PlansTableCard
      plans={plans}
      canRunAutoLock={true}
      autoLockRunning={false}
      autoLockResult={null}
      onRunAutoLock={() => {}}
      newPlanZoneId=""
      onNewPlanZoneIdChange={() => {}}
      onCreatePlan={() => {}}
      includePlanId=""
      onIncludePlanIdChange={() => {}}
      includeOrderId=""
      onIncludeOrderIdChange={() => {}}
      onIncludeOrder={() => {}}
      canAssignPlanVehicle={true}
      vehicleDrafts={{}}
      onVehicleDraftChange={() => {}}
      savingVehiclePlanId={null}
      onSavePlanVehicle={() => {}}
      onLockPlan={() => {}}
      onLoadPlanConsolidation={() => {}}
      planConsolidationLoading={false}
      shortId={(value) => value.slice(0, 8)}
    />,
  );
}

test("renders controls and empty state", () => {
  const html = renderCard([]);
  assert.match(html, /Planes/);
  assert.match(html, /Ejecutar auto-lock/);
  assert.match(html, /zone_id para crear plan/);
  assert.match(html, /Incluir pedido/);
  assert.match(html, /Sin planes para la fecha actual\./);
});

test("preserves backend order without frontend re-sorting", () => {
  const plans: Plan[] = [
    makePlan({
      id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      zone_id: "00000000-0000-0000-0000-000000000000",
    }),
    makePlan({
      id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      zone_id: "ffffffff-ffff-ffff-ffff-ffffffffffff",
    }),
  ];

  const html = renderCard(plans);
  const firstIndex = html.indexOf("bbbbbbbb");
  const secondIndex = html.indexOf("aaaaaaaa");

  assert.ok(firstIndex >= 0, "first plan should render");
  assert.ok(secondIndex >= 0, "second plan should render");
  assert.ok(firstIndex < secondIndex, "plans order should match backend order");
});
