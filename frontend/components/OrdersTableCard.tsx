import React from "react";
import type { Order, OrderOperationalSeverity } from "../lib/api";

type IntakeBadgeMeta = { className: string; label: string };
type OrdersOperationalStateFilter = "all" | "eligible" | "restricted";

type OrdersTableCardProps = {
  ordersOperationalStateFilter: OrdersOperationalStateFilter;
  onOrdersOperationalStateFilterChange: (value: OrdersOperationalStateFilter) => void;
  ordersOperationalReasonFilter: string;
  onOrdersOperationalReasonFilterChange: (value: string) => void;
  ordersOperationalReasonOptions: string[];
  onRefresh: () => void;
  filteredOrders: Order[];
  canEditOrderWeight: boolean;
  weightDrafts: Record<string, string>;
  onWeightDraftChange: (orderId: string, value: string) => void;
  savingWeightOrderId: string | null;
  onSaveOrderWeight: (order: Order) => void;
  shortId: (value: string) => string;
  intakeBadgeMeta: (intakeType: string) => IntakeBadgeMeta;
  operationalStateBadgeMeta: (state: string) => IntakeBadgeMeta;
  operationalReasonBadgeClass: (reason: string) => string;
  operationalSeverityBadgeClass: (severity: OrderOperationalSeverity | string | null) => string;
};

export function OrdersTableCard({
  ordersOperationalStateFilter,
  onOrdersOperationalStateFilterChange,
  ordersOperationalReasonFilter,
  onOrdersOperationalReasonFilterChange,
  ordersOperationalReasonOptions,
  onRefresh,
  filteredOrders,
  canEditOrderWeight,
  weightDrafts,
  onWeightDraftChange,
  savingWeightOrderId,
  onSaveOrderWeight,
  shortId,
  intakeBadgeMeta,
  operationalStateBadgeMeta,
  operationalReasonBadgeClass,
  operationalSeverityBadgeClass,
}: OrdersTableCardProps) {
  return (
    <div className="card orders-table-card">
      <h2>Pedidos</h2>
      <div className="row" style={{ margin: "10px 0" }}>
        <label>
          operational_state{" "}
          <select
            value={ordersOperationalStateFilter}
            onChange={(e) => onOrdersOperationalStateFilterChange(e.target.value as OrdersOperationalStateFilter)}
          >
            <option value="all">all</option>
            <option value="eligible">eligible</option>
            <option value="restricted">restricted</option>
          </select>
        </label>
        <label>
          operational_reason{" "}
          <select value={ordersOperationalReasonFilter} onChange={(e) => onOrdersOperationalReasonFilterChange(e.target.value)}>
            <option value="all">all</option>
            {ordersOperationalReasonOptions.map((reason) => (
              <option key={reason} value={reason}>
                {reason}
              </option>
            ))}
          </select>
        </label>
        <button className="secondary" onClick={onRefresh}>
          Refrescar pedidos
        </button>
      </div>
      <table>
        <thead>
          <tr>
            <th>ref</th>
            <th>cliente</th>
            <th>zona</th>
            <th>tipo</th>
            <th>estado</th>
            <th>op_state</th>
            <th>op_reason</th>
            <th>op_severity</th>
            <th>op_timezone</th>
            <th>op_catalog</th>
            <th>late</th>
            <th>peso_kg</th>
            <th>editar_peso</th>
            <th>cutoff</th>
          </tr>
        </thead>
        <tbody>
          {filteredOrders.length === 0 && (
            <tr>
              <td colSpan={14} style={{ color: "#6b7280" }}>
                Sin pedidos para los filtros actuales.
              </td>
            </tr>
          )}
          {filteredOrders.map((order) => {
            const badgeClass = order.status === "exception_rejected" ? "badge rejected" : order.is_late ? "badge late" : "badge ok";
            const intakeMeta = intakeBadgeMeta(order.intake_type);
            const operationalStateMeta = operationalStateBadgeMeta(order.operational_state);
            const reasonCode = order.operational_explanation?.reason_code ?? order.operational_reason;
            const reasonSeverity = order.operational_explanation?.severity ?? null;
            const reasonTimezone = order.operational_explanation?.timezone_used ?? "—";
            const reasonTimezoneSource = order.operational_explanation?.timezone_source ?? "—";
            const reasonCatalogStatus = order.operational_explanation?.catalog_status ?? "—";
            const weightValue = weightDrafts[order.id] ?? (order.total_weight_kg == null ? "" : String(order.total_weight_kg));
            return (
              <tr key={order.id}>
                <td>{order.external_ref}</td>
                <td>{shortId(order.customer_id)}</td>
                <td>{shortId(order.zone_id)}</td>
                <td>
                  <span className={intakeMeta.className}>{intakeMeta.label}</span>
                </td>
                <td>{order.status}</td>
                <td>
                  <span className={operationalStateMeta.className}>{operationalStateMeta.label}</span>
                </td>
                <td>{reasonCode ? <span className={operationalReasonBadgeClass(reasonCode)}>{reasonCode}</span> : "—"}</td>
                <td>{reasonSeverity ? <span className={operationalSeverityBadgeClass(reasonSeverity)}>{reasonSeverity}</span> : "—"}</td>
                <td>
                  <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                    <span>{reasonTimezone}</span>
                    <span style={{ color: "#6b7280", fontSize: 12 }}>{reasonTimezoneSource}</span>
                  </div>
                </td>
                <td>{reasonCatalogStatus}</td>
                <td>
                  <span className={badgeClass}>{order.is_late ? "late" : "on_time"}</span>
                </td>
                <td>{order.total_weight_kg == null ? "—" : order.total_weight_kg}</td>
                <td>
                  {canEditOrderWeight ? (
                    <div className="row" style={{ gap: 6 }}>
                      <input
                        placeholder="kg"
                        value={weightValue}
                        onChange={(e) => onWeightDraftChange(order.id, e.target.value)}
                        style={{ width: 96 }}
                      />
                      <button className="secondary" onClick={() => onSaveOrderWeight(order)} disabled={savingWeightOrderId === order.id}>
                        {savingWeightOrderId === order.id ? "Guardando..." : "Guardar"}
                      </button>
                    </div>
                  ) : (
                    <span style={{ color: "#6b7280" }}>solo lectura</span>
                  )}
                </td>
                <td>{new Date(order.effective_cutoff_at).toLocaleString("es-ES")}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
