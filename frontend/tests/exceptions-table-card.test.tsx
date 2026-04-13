import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { ExceptionsTableCard } from "../components/ExceptionsTableCard";
import type { ExceptionItem } from "../lib/api";

function renderCard(exceptions: ExceptionItem[]): string {
  return renderToStaticMarkup(
    <ExceptionsTableCard
      exceptionOrderId=""
      onExceptionOrderIdChange={() => {}}
      exceptionNote="Pedido fuera de corte"
      onExceptionNoteChange={() => {}}
      onCreateException={() => {}}
      exceptions={exceptions}
      onApproveException={() => {}}
      onRejectException={() => {}}
    />,
  );
}

test("renders controls and table headers", () => {
  const html = renderCard([]);
  assert.match(html, /Excepciones/);
  assert.match(html, /order_id/);
  assert.match(html, /nota/);
  assert.match(html, /Solicitar excepción/);
  assert.match(html, /<th>id<\/th>/);
  assert.match(html, /<th>order<\/th>/);
  assert.match(html, /<th>estado<\/th>/);
  assert.match(html, /<th>acción<\/th>/);
});

test("preserves backend order and action visibility by status", () => {
  const exceptions: ExceptionItem[] = [
    {
      id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      order_id: "11111111-1111-1111-1111-111111111111",
      type: "late_order",
      status: "pending",
      requested_by: "u1",
      resolved_by: null,
      resolved_at: null,
      note: "note 1",
      created_at: "2026-04-01T10:00:00Z",
    },
    {
      id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      order_id: "22222222-2222-2222-2222-222222222222",
      type: "late_order",
      status: "approved",
      requested_by: "u2",
      resolved_by: "u3",
      resolved_at: "2026-04-01T11:00:00Z",
      note: "note 2",
      created_at: "2026-04-01T09:00:00Z",
    },
  ];

  const html = renderCard(exceptions);
  const firstIndex = html.indexOf("bbbbbbbb");
  const secondIndex = html.indexOf("aaaaaaaa");

  assert.ok(firstIndex >= 0, "first exception should render");
  assert.ok(secondIndex >= 0, "second exception should render");
  assert.ok(firstIndex < secondIndex, "exceptions order should match backend order");
  assert.match(html, /Aprobar/);
  assert.match(html, /Rechazar/);
});
