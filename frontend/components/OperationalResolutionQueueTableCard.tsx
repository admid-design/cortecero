import React from "react";
import type {
  OperationalResolutionQueueItem,
  OperationalResolutionQueueReason,
  OperationalResolutionQueueSeverity,
} from "../lib/api";

type OperationalResolutionQueueTableCardProps = {
  serviceDate: string;
  onServiceDateChange: (value: string) => void;
  zoneId: string;
  onZoneIdChange: (value: string) => void;
  zoneOptions: string[];
  reason: "all" | OperationalResolutionQueueReason | string;
  onReasonChange: (value: "all" | OperationalResolutionQueueReason | string) => void;
  reasonOptions: string[];
  severity: "all" | OperationalResolutionQueueSeverity | string;
  onSeverityChange: (value: "all" | OperationalResolutionQueueSeverity | string) => void;
  severityOptions: readonly string[];
  items: OperationalResolutionQueueItem[];
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

function operationalSeverityBadgeClass(severity: string | null): string {
  if (severity === "critical") return "badge rejected";
  if (severity === "high") return "badge late";
  if (severity === "medium") return "badge intake-addon";
  if (severity === "low") return "badge ok";
  return "badge intake-unknown";
}

export function OperationalResolutionQueueTableCard({
  serviceDate,
  onServiceDateChange,
  zoneId,
  onZoneIdChange,
  zoneOptions,
  reason,
  onReasonChange,
  reasonOptions,
  severity,
  onSeverityChange,
  severityOptions,
  items,
  onApplyFilters,
}: OperationalResolutionQueueTableCardProps) {
  return (
    <div className="card grid operational-resolution-queue-table-card">
      <h2>Operational Resolution Queue</h2>
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
          <select value={reason} onChange={(e) => onReasonChange(e.target.value as "all" | OperationalResolutionQueueReason | string)}>
            <option value="all">all</option>
            {reasonOptions.map((optionReason) => (
              <option key={optionReason} value={optionReason}>
                {optionReason}
              </option>
            ))}
          </select>
        </label>
        <label>
          severity{" "}
          <select
            value={severity}
            onChange={(e) => onSeverityChange(e.target.value as "all" | OperationalResolutionQueueSeverity | string)}
          >
            <option value="all">all</option>
            {severityOptions.map((optionSeverity) => (
              <option key={optionSeverity} value={optionSeverity}>
                {optionSeverity}
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
            <th>severity</th>
            <th>created_at</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 && (
            <tr>
              <td colSpan={9} style={{ color: "var(--muted)" }}>
                Sin items de resolución para los filtros actuales.
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
                <span className={operationalReasonBadgeClass(item.operational_reason)}>{item.operational_reason}</span>
              </td>
              <td>
                <span className={operationalSeverityBadgeClass(item.severity)}>{item.severity}</span>
              </td>
              <td>{new Date(item.created_at).toLocaleString("es-ES")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
