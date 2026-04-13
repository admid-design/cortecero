import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { OperationalQueueTableCard } from "../components/OperationalQueueTableCard";
import type { OperationalQueueItem } from "../lib/api";

function renderCard(items: OperationalQueueItem[]): string {
  return renderToStaticMarkup(
    <OperationalQueueTableCard
      serviceDate="2026-04-01"
      onServiceDateChange={() => {}}
      zoneId="all"
      onZoneIdChange={() => {}}
      zoneOptions={["all-zone", "zone-a"]}
      reason="all"
      onReasonChange={() => {}}
      reasonOptions={[
        "CUSTOMER_DATE_BLOCKED",
        "CUSTOMER_NOT_ACCEPTING_ORDERS",
        "OUTSIDE_CUSTOMER_WINDOW",
        "INSUFFICIENT_LEAD_TIME",
      ]}
      items={items}
      onApplyFilters={() => {}}
    />,
  );
}

test("renders empty state and filter controls", () => {
  const html = renderCard([]);
  assert.match(html, /Operational Queue/);
  assert.match(html, /Sin restricciones operativas para los filtros actuales\./);
  assert.match(html, /service_date/);
  assert.match(html, /zone_id/);
  assert.match(html, /reason/);
});

test("preserves backend order without frontend re-sorting", () => {
  const orderedItems: OperationalQueueItem[] = [
    {
      order_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      external_ref: "REF-B",
      customer_id: "11111111-1111-1111-1111-111111111111",
      zone_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      service_date: "2026-04-01",
      status: "ready_for_planning",
      intake_type: "new_order",
      reason: "OUTSIDE_CUSTOMER_WINDOW",
      created_at: "2026-03-31T07:00:00Z",
    },
    {
      order_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      external_ref: "REF-A",
      customer_id: "22222222-2222-2222-2222-222222222222",
      zone_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      service_date: "2026-04-01",
      status: "ready_for_planning",
      intake_type: "same_customer_addon",
      reason: "INSUFFICIENT_LEAD_TIME",
      created_at: "2026-03-31T06:00:00Z",
    },
  ];

  const html = renderCard(orderedItems);
  const refBIndex = html.indexOf("REF-B");
  const refAIndex = html.indexOf("REF-A");

  assert.ok(refBIndex >= 0, "REF-B should be rendered");
  assert.ok(refAIndex >= 0, "REF-A should be rendered");
  assert.ok(refBIndex < refAIndex, "Rendered order should match backend order");
});
