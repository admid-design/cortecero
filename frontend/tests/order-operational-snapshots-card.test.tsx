import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { OrderOperationalSnapshotsCard } from "../components/OrderOperationalSnapshotsCard";
import type { OrderOperationalSnapshotItem } from "../lib/api";

function renderCard(items: OrderOperationalSnapshotItem[], selectedOrderId = "order-1"): string {
  return renderToStaticMarkup(
    <OrderOperationalSnapshotsCard
      selectedOrderId={selectedOrderId}
      onSelectedOrderIdChange={() => {}}
      orderOptions={[
        {
          id: "order-1",
          externalRef: "REF-1",
          serviceDate: "2026-04-01",
        },
      ]}
      items={items}
      loading={false}
      error=""
      onLoad={() => {}}
    />,
  );
}

test("renders controls and selected-order empty state", () => {
  const html = renderCard([]);
  assert.match(html, /Operational Snapshots Timeline/);
  assert.match(html, /order_id/);
  assert.match(html, /Cargar timeline/);
  assert.match(html, /Sin snapshots para el pedido seleccionado\./);
});

test("preserves backend order without frontend re-sorting", () => {
  const orderedItems: OrderOperationalSnapshotItem[] = [
    {
      id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      order_id: "order-1",
      service_date: "2026-04-01",
      operational_state: "restricted",
      operational_reason: "OUTSIDE_CUSTOMER_WINDOW",
      evaluation_ts: "2026-03-31T07:00:00Z",
      timezone_used: "Europe/Madrid",
      rule_version: "r6-v2",
      evidence_json: { window_type: "same_day", lead_hours_required: 0 },
    },
    {
      id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      order_id: "order-1",
      service_date: "2026-04-01",
      operational_state: "eligible",
      operational_reason: null,
      evaluation_ts: "2026-03-31T06:00:00Z",
      timezone_used: "Europe/Madrid",
      rule_version: "r6-v1",
      evidence_json: { window_type: "none", lead_hours_required: 0 },
    },
  ];

  const html = renderCard(orderedItems);
  const firstIndex = html.indexOf("r6-v2");
  const secondIndex = html.indexOf("r6-v1");

  assert.ok(firstIndex >= 0, "r6-v2 should be rendered");
  assert.ok(secondIndex >= 0, "r6-v1 should be rendered");
  assert.ok(firstIndex < secondIndex, "Rendered order should match backend order");
});

