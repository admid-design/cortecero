import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { OrdersTableCard } from "../components/OrdersTableCard";
import type { Order } from "../lib/api";

function makeOrder(overrides: Partial<Order> = {}): Order {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    customer_id: "22222222-2222-2222-2222-222222222222",
    zone_id: "33333333-3333-3333-3333-333333333333",
    external_ref: "REF-001",
    service_date: "2026-04-13",
    status: "planned",
    operational_state: "eligible",
    operational_reason: null,
    operational_explanation: {
      reason_code: null,
      reason_category: null,
      severity: null,
      timezone_used: "Europe/Madrid",
      timezone_source: "zone",
      rule_version: "r6-operational-eval-v1",
      catalog_status: "not_applicable",
    },
    is_late: false,
    effective_cutoff_at: "2026-04-13T08:00:00Z",
    intake_type: "new_order",
    total_weight_kg: 12,
    ...overrides,
  };
}

function renderCard(filteredOrders: Order[]): string {
  return renderToStaticMarkup(
    <OrdersTableCard
      ordersOperationalStateFilter="all"
      onOrdersOperationalStateFilterChange={() => {}}
      ordersOperationalReasonFilter="all"
      onOrdersOperationalReasonFilterChange={() => {}}
      ordersOperationalReasonOptions={["CUSTOMER_DATE_BLOCKED", "OUTSIDE_CUSTOMER_WINDOW"]}
      onRefresh={() => {}}
      filteredOrders={filteredOrders}
      canEditOrderWeight={true}
      weightDrafts={{}}
      onWeightDraftChange={() => {}}
      savingWeightOrderId=""
      onSaveOrderWeight={() => {}}
      shortId={(value) => value.slice(0, 8)}
      intakeBadgeMeta={() => ({ className: "badge intake-new", label: "nuevo" })}
      operationalStateBadgeMeta={() => ({ className: "badge ok", label: "eligible" })}
      operationalReasonBadgeClass={() => "badge late"}
      operationalSeverityBadgeClass={() => "badge rejected"}
    />,
  );
}

test("renders controls and empty state", () => {
  const html = renderCard([]);
  assert.match(html, /Pedidos/);
  assert.match(html, /operational_state/);
  assert.match(html, /operational_reason/);
  assert.match(html, /Refrescar pedidos/);
  assert.match(html, /Sin pedidos para los filtros actuales\./);
});

test("preserves backend order without frontend re-sorting", () => {
  const orders: Order[] = [
    makeOrder({
      id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      external_ref: "REF-B",
    }),
    makeOrder({
      id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      external_ref: "REF-A",
    }),
  ];

  const html = renderCard(orders);
  const firstIndex = html.indexOf("REF-B");
  const secondIndex = html.indexOf("REF-A");

  assert.ok(firstIndex >= 0, "first order should render");
  assert.ok(secondIndex >= 0, "second order should render");
  assert.ok(firstIndex < secondIndex, "order order should match backend order");
});
