import React from "react";
import type { OrderOperationalSnapshotItem } from "../lib/api";

type OrderOption = {
  id: string;
  externalRef: string;
  serviceDate: string;
};

type OrderSnapshotsTimelineCardProps = {
  selectedOrderId: string;
  onSelectedOrderIdChange: (value: string) => void;
  orderOptions: OrderOption[];
  items: OrderOperationalSnapshotItem[];
  loading: boolean;
  error: string;
  onLoad: () => void;
};

function shortId(value: string): string {
  return value.slice(0, 8);
}

function operationalReasonBadgeClass(reason: string): string {
  if (reason === "CUSTOMER_DATE_BLOCKED" || reason === "CUSTOMER_NOT_ACCEPTING_ORDERS") {
    return "badge rejected";
  }
  if (reason === "OUTSIDE_CUSTOMER_WINDOW" || reason === "INSUFFICIENT_LEAD_TIME") {
    return "badge late";
  }
  return "badge intake-unknown";
}

function operationalStateBadgeClass(state: string): string {
  if (state === "eligible") return "badge ok";
  if (state === "restricted") return "badge late";
  return "badge intake-unknown";
}

function readEvidenceValue(evidence: Record<string, unknown>, key: string): string {
  const value = evidence[key];
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

export function OrderSnapshotsTimelineCard({
  selectedOrderId,
  onSelectedOrderIdChange,
  orderOptions,
  items,
  loading,
  error,
  onLoad,
}: OrderSnapshotsTimelineCardProps) {
  return (
    <div className="card grid order-snapshots-timeline-card">
      <h2>Operational Snapshots Timeline</h2>
      <div className="row">
        <label>
          order_id{" "}
          <select value={selectedOrderId} onChange={(e) => onSelectedOrderIdChange(e.target.value)}>
            <option value="">select-order</option>
            {orderOptions.map((order) => (
              <option key={order.id} value={order.id}>
                {order.externalRef} | {shortId(order.id)} | {order.serviceDate}
              </option>
            ))}
          </select>
        </label>
        <button className="secondary" onClick={onLoad} disabled={!selectedOrderId || loading}>
          {loading ? "Cargando..." : "Cargar timeline"}
        </button>
      </div>
      {error && (
        <div style={{ color: "var(--danger-text)", background: "var(--danger-bg)", border: "1px solid var(--danger-border)", padding: 8 }}>{error}</div>
      )}
      <table>
        <thead>
          <tr>
            <th>evaluation_ts</th>
            <th>state</th>
            <th>reason</th>
            <th>timezone</th>
            <th>rule_version</th>
            <th>window_type</th>
            <th>lead_hours_required</th>
          </tr>
        </thead>
        <tbody>
          {!selectedOrderId && (
            <tr>
              <td colSpan={7} style={{ color: "var(--muted)" }}>
                Selecciona un pedido y pulsa Cargar timeline.
              </td>
            </tr>
          )}
          {selectedOrderId && !loading && items.length === 0 && (
            <tr>
              <td colSpan={7} style={{ color: "var(--muted)" }}>
                Sin snapshots para el pedido seleccionado.
              </td>
            </tr>
          )}
          {items.map((item) => (
            <tr key={item.id}>
              <td>{new Date(item.evaluation_ts).toLocaleString("es-ES")}</td>
              <td>
                <span className={operationalStateBadgeClass(item.operational_state)}>{item.operational_state}</span>
              </td>
              <td>
                {item.operational_reason ? (
                  <span className={operationalReasonBadgeClass(item.operational_reason)}>{item.operational_reason}</span>
                ) : (
                  "—"
                )}
              </td>
              <td>{item.timezone_used}</td>
              <td>{item.rule_version}</td>
              <td>{readEvidenceValue(item.evidence_json, "window_type")}</td>
              <td>{readEvidenceValue(item.evidence_json, "lead_hours_required")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
