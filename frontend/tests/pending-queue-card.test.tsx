import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { PendingQueueCard } from "../components/PendingQueueCard";
import type { PendingQueueItem } from "../lib/api";

function renderCard(items: PendingQueueItem[]): string {
  return renderToStaticMarkup(
    <PendingQueueCard
      serviceDate="2026-04-01"
      onServiceDateChange={() => {}}
      zoneId="all"
      onZoneIdChange={() => {}}
      zoneOptions={["all-zone", "zone-a"]}
      reason="all"
      onReasonChange={() => {}}
      items={items}
      onApplyFilters={() => {}}
    />,
  );
}

test("renders empty state and filter controls", () => {
  const html = renderCard([]);
  assert.match(html, /Pending Queue/);
  assert.match(html, /Sin pendientes para los filtros actuales\./);
  assert.match(html, /service_date/);
  assert.match(html, /zone_id/);
  assert.match(html, /reason/);
});

test("preserves backend order without frontend re-sorting", () => {
  const orderedItems: PendingQueueItem[] = [
    {
      order_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      external_ref: "REF-B",
      status: "late_pending_exception",
      reason: "LATE_PENDING_EXCEPTION",
      service_date: "2026-04-01",
      zone_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      created_at: "2026-03-31T07:00:00Z",
    },
    {
      order_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      external_ref: "REF-A",
      status: "late_pending_exception",
      reason: "LOCKED_PLAN_EXCEPTION_REQUIRED",
      service_date: "2026-04-01",
      zone_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
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

