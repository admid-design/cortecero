import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { CapacityAlertsTableCard } from "../components/CapacityAlertsTableCard";
import type { PlanCapacityAlert } from "../lib/api";

function renderCard(alerts: PlanCapacityAlert[]): string {
  return renderToStaticMarkup(
    <CapacityAlertsTableCard
      serviceDate="2026-04-01"
      onServiceDateChange={() => {}}
      zoneId="all"
      onZoneIdChange={() => {}}
      zoneOptions={["all-zone", "zone-a"]}
      level="all"
      onLevelChange={() => {}}
      alerts={alerts}
      onApplyFilters={() => {}}
    />,
  );
}

test("renders controls and empty state", () => {
  const html = renderCard([]);
  assert.match(html, /Alertas de Capacidad/);
  assert.match(html, /service_date/);
  assert.match(html, /zone_id/);
  assert.match(html, /level/);
  assert.match(html, /Aplicar filtros/);
  assert.match(html, /Sin alertas para los filtros actuales\./);
});

test("preserves backend order without frontend re-sorting", () => {
  const alerts: PlanCapacityAlert[] = [
    {
      plan_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      service_date: "2026-04-01",
      zone_id: "11111111-1111-1111-1111-111111111111",
      vehicle_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      vehicle_code: "VH-B",
      vehicle_name: "Vehiculo B",
      total_weight_kg: 1000,
      vehicle_capacity_kg: 900,
      usage_ratio: 1.11,
      alert_level: "OVER_CAPACITY",
    },
    {
      plan_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      service_date: "2026-04-01",
      zone_id: "22222222-2222-2222-2222-222222222222",
      vehicle_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      vehicle_code: "VH-A",
      vehicle_name: "Vehiculo A",
      total_weight_kg: 800,
      vehicle_capacity_kg: 900,
      usage_ratio: 0.88,
      alert_level: "NEAR_CAPACITY",
    },
  ];

  const html = renderCard(alerts);
  const firstIndex = html.indexOf("Vehiculo B");
  const secondIndex = html.indexOf("Vehiculo A");

  assert.ok(firstIndex >= 0, "first alert should render");
  assert.ok(secondIndex >= 0, "second alert should render");
  assert.ok(firstIndex < secondIndex, "alerts order should match backend order");
});
