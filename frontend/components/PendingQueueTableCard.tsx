import React from "react";
import type { PendingQueueItem, PendingQueueReason } from "../lib/api";

type PendingQueueTableCardProps = {
  serviceDate: string;
  onServiceDateChange: (value: string) => void;
  zoneId: string;
  onZoneIdChange: (value: string) => void;
  zoneOptions: string[];
  reason: "all" | PendingQueueReason;
  onReasonChange: (value: "all" | PendingQueueReason) => void;
  items: PendingQueueItem[];
  onApplyFilters: () => void;
};

function shortId(value: string): string {
  return value.slice(0, 8);
}

export function PendingQueueTableCard({
  serviceDate,
  onServiceDateChange,
  zoneId,
  onZoneIdChange,
  zoneOptions,
  reason,
  onReasonChange,
  items,
  onApplyFilters,
}: PendingQueueTableCardProps) {
  return (
    <div className="card grid pending-queue-table-card">
      <h2>Pending Queue</h2>
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
          <select value={reason} onChange={(e) => onReasonChange(e.target.value as "all" | PendingQueueReason)}>
            <option value="all">all</option>
            <option value="LATE_PENDING_EXCEPTION">LATE_PENDING_EXCEPTION</option>
            <option value="LOCKED_PLAN_EXCEPTION_REQUIRED">LOCKED_PLAN_EXCEPTION_REQUIRED</option>
            <option value="EXCEPTION_REJECTED">EXCEPTION_REJECTED</option>
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
            <th>zone_id</th>
            <th>status</th>
            <th>reason</th>
            <th>created_at</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 && (
            <tr>
              <td colSpan={6} style={{ color: "#6b7280" }}>
                Sin pendientes para los filtros actuales.
              </td>
            </tr>
          )}
          {items.map((item) => (
            <tr key={item.order_id}>
              <td>{item.external_ref}</td>
              <td>{shortId(item.order_id)}</td>
              <td>{shortId(item.zone_id)}</td>
              <td>{item.status}</td>
              <td>{item.reason}</td>
              <td>{new Date(item.created_at).toLocaleString("es-ES")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
