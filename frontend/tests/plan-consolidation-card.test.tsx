import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { PlanConsolidationCard } from "../components/PlanConsolidationCard";
import type { Plan, PlanCustomerConsolidationResponse } from "../lib/api";

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

function makeConsolidation(
  overrides: Partial<PlanCustomerConsolidationResponse> = {},
): PlanCustomerConsolidationResponse {
  return {
    plan_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    service_date: "2026-04-13",
    zone_id: "11111111-1111-1111-1111-111111111111",
    total_customers: 2,
    items: [
      {
        customer_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        customer_name: "Cliente B",
        total_orders: 1,
        order_refs: ["REF-B"],
        total_weight_kg: 12,
        orders_with_weight: 1,
        orders_missing_weight: 0,
      },
      {
        customer_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        customer_name: "Cliente A",
        total_orders: 1,
        order_refs: ["REF-A"],
        total_weight_kg: 10,
        orders_with_weight: 1,
        orders_missing_weight: 0,
      },
    ],
    ...overrides,
  };
}

function renderCard(planConsolidation: PlanCustomerConsolidationResponse | null): string {
  return renderToStaticMarkup(
    <PlanConsolidationCard
      plans={[makePlan()]}
      selectedConsolidationPlanId=""
      onSelectedConsolidationPlanIdChange={() => {}}
      onLoadPlanConsolidation={() => {}}
      planConsolidationLoading={false}
      planConsolidation={planConsolidation}
      shortId={(value) => value.slice(0, 8)}
    />,
  );
}

test("renders controls and selected-plan empty state", () => {
  const html = renderCard(null);
  assert.match(html, /Consolidación por Cliente \(Plan\)/);
  assert.match(html, /Selecciona plan/);
  assert.match(html, /Cargar consolidación/);
  assert.match(html, /Selecciona un plan para ver la consolidación operativa por cliente\./);
});

test("preserves backend order without frontend re-sorting", () => {
  const html = renderCard(makeConsolidation());
  const firstIndex = html.indexOf("Cliente B");
  const secondIndex = html.indexOf("Cliente A");

  assert.ok(firstIndex >= 0, "first customer should render");
  assert.ok(secondIndex >= 0, "second customer should render");
  assert.ok(firstIndex < secondIndex, "items order should match backend order");
});
