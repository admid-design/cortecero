import React from "react";
import type { OperationalQueueItem, OperationalQueueReason } from "../lib/api";

type OperationalQueueCardProps = {
  serviceDate: string;
  onServiceDateChange: (value: string) => void;
  zoneId: string;
  onZoneIdChange: (value: string) => void;
  zoneOptions: string[];
  reason: "all" | OperationalQueueReason | string;
  onReasonChange: (value: "all" | OperationalQueueReason | string) => void;
  reasonOptions: string[];
  items: OperationalQueueItem[];
  onApplyFilters: () => void;
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

export function OperationalQueueCard({
  serviceDate,
  onServiceDateChange,
  zoneId,
  onZoneIdChange,
  zoneOptions,
  reason,
  onReasonChange,
  reasonOptions,
  items,
  onApplyFilters,
}: OperationalQueueCardProps) {
  return (
    <div className="card grid">
      <h2>Operational Queue</h2>
      <div className="row">
        <label>
          service_date <input type="date" value={serviceDate} onChange={(e) => onServiceDateChange(e.target.value)} />
        </label>
        <label>
          zone_id{" "}
          <select value={zoneId} onChange={(e) => onZoneIdChange(e.target.value)}>
            <option value="all">all</option>
            {zoneOptions.map((optionZoneId) => (
              <option key={optionZoneId} value={optionZoneId}>
                {optionZoneId}
              </option>
            ))}
          </select>
        </label>
        <label>
          reason{" "}
          <select value={reason} onChange={(e) => onReasonChange(e.target.value as "all" | OperationalQueueReason | string)}>
            <option value="all">all</option>
            {reasonOptions.map((optionReason) => (
              <option key={optionReason} value={optionReason}>
                {optionReason}
              </option>
            ))}
          </select>
        </label>
        <button className="secondary" onClick={onApplyFilters}>
          Aplicar filtros
        </button>
      </div>
      <table>
        <thead>
          <tr>
            <th>ref</th>
            <th>order_id</th>
            <th>customer_id</th>
            <th>zone_id</th>
            <th>status</th>
            <th>intake_type</th>
            <th>reason</th>
            <th>created_at</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 && (
            <tr>
              <td colSpan={8} style={{ color: "#6b7280" }}>
                Sin restricciones operativas para los filtros actuales.
              </td>
            </tr>
          )}
          {items.map((item) => (
            <tr key={item.order_id}>
              <td>{item.external_ref}</td>
              <td>{shortId(item.order_id)}</td>
              <td>{shortId(item.customer_id)}</td>
              <td>{shortId(item.zone_id)}</td>
              <td>{item.status}</td>
              <td>{item.intake_type}</td>
              <td>
                <span className={operationalReasonBadgeClass(item.reason)}>{item.reason}</span>
              </td>
              <td>{new Date(item.created_at).toLocaleString("es-ES")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

