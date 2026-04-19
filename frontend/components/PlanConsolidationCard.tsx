import React from "react";
import type { Plan, PlanCustomerConsolidationResponse } from "../lib/api";

type PlanConsolidationCardProps = {
  plans: Plan[];
  selectedConsolidationPlanId: string;
  onSelectedConsolidationPlanIdChange: (value: string) => void;
  onLoadPlanConsolidation: () => void;
  planConsolidationLoading: boolean;
  planConsolidation: PlanCustomerConsolidationResponse | null;
  shortId: (value: string) => string;
};

export function PlanConsolidationCard({
  plans,
  selectedConsolidationPlanId,
  onSelectedConsolidationPlanIdChange,
  onLoadPlanConsolidation,
  planConsolidationLoading,
  planConsolidation,
  shortId,
}: PlanConsolidationCardProps) {
  return (
    <div className="card grid plan-consolidation-card">
      <h3>Consolidación por Cliente (Plan)</h3>
      <div className="row">
        <select
          value={selectedConsolidationPlanId}
          onChange={(e) => onSelectedConsolidationPlanIdChange(e.target.value)}
          style={{ minWidth: 320 }}
        >
          <option value="">Selecciona plan</option>
          {plans.map((plan) => (
            <option key={plan.id} value={plan.id}>
              {plan.service_date} · {shortId(plan.zone_id)} · {shortId(plan.id)}
            </option>
          ))}
        </select>
        <button className="secondary" onClick={onLoadPlanConsolidation} disabled={planConsolidationLoading}>
          {planConsolidationLoading ? "Cargando..." : "Cargar consolidación"}
        </button>
      </div>

      {!planConsolidation && !planConsolidationLoading && (
        <p style={{ margin: 0, color: "var(--muted)" }}>Selecciona un plan para ver la consolidación operativa por cliente.</p>
      )}

      {planConsolidation && (
        <>
          <div className="row" style={{ gap: 6 }}>
            <span className="pill">plan_id: {shortId(planConsolidation.plan_id)}</span>
            <span className="pill">service_date: {planConsolidation.service_date}</span>
            <span className="pill">zone_id: {shortId(planConsolidation.zone_id)}</span>
            <span className="pill">total_customers: {planConsolidation.total_customers}</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>customer_id</th>
                <th>customer_name</th>
                <th>total_orders</th>
                <th>order_refs</th>
                <th>total_weight_kg</th>
                <th>with/missing weight</th>
              </tr>
            </thead>
            <tbody>
              {planConsolidation.items.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ color: "var(--muted)" }}>
                    Sin pedidos incluidos para este plan.
                  </td>
                </tr>
              )}
              {planConsolidation.items.map((item) => (
                <tr key={item.customer_id}>
                  <td>{shortId(item.customer_id)}</td>
                  <td>{item.customer_name}</td>
                  <td>{item.total_orders}</td>
                  <td>{item.order_refs.join(", ")}</td>
                  <td>{item.total_weight_kg == null ? "—" : item.total_weight_kg}</td>
                  <td>
                    {item.orders_with_weight}/{item.total_orders}
                    {item.orders_missing_weight > 0 ? ` (${item.orders_missing_weight} sin peso)` : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
