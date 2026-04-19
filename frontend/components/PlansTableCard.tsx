import React from "react";
import type { AutoLockRunResponse, Plan } from "../lib/api";

type PlansTableCardProps = {
  plans: Plan[];
  canRunAutoLock: boolean;
  autoLockRunning: boolean;
  autoLockResult: AutoLockRunResponse | null;
  onRunAutoLock: () => void;
  newPlanZoneId: string;
  onNewPlanZoneIdChange: (value: string) => void;
  onCreatePlan: () => void;
  includePlanId: string;
  onIncludePlanIdChange: (value: string) => void;
  includeOrderId: string;
  onIncludeOrderIdChange: (value: string) => void;
  onIncludeOrder: () => void;
  canAssignPlanVehicle: boolean;
  vehicleDrafts: Record<string, string>;
  onVehicleDraftChange: (planId: string, value: string) => void;
  savingVehiclePlanId: string | null;
  onSavePlanVehicle: (plan: Plan, clear?: boolean) => void;
  onLockPlan: (planId: string) => void;
  onLoadPlanConsolidation: (planId: string) => void;
  planConsolidationLoading: boolean;
  shortId: (value: string) => string;
};

export function PlansTableCard({
  plans,
  canRunAutoLock,
  autoLockRunning,
  autoLockResult,
  onRunAutoLock,
  newPlanZoneId,
  onNewPlanZoneIdChange,
  onCreatePlan,
  includePlanId,
  onIncludePlanIdChange,
  includeOrderId,
  onIncludeOrderIdChange,
  onIncludeOrder,
  canAssignPlanVehicle,
  vehicleDrafts,
  onVehicleDraftChange,
  savingVehiclePlanId,
  onSavePlanVehicle,
  onLockPlan,
  onLoadPlanConsolidation,
  planConsolidationLoading,
  shortId,
}: PlansTableCardProps) {
  return (
    <div className="card grid plans-table-card">
      <h2>Planes</h2>
      {canRunAutoLock && (
        <div className="row">
          <button className="secondary" onClick={onRunAutoLock} disabled={autoLockRunning}>
            {autoLockRunning ? "Ejecutando auto-lock..." : "Ejecutar auto-lock"}
          </button>
          {autoLockResult && (
            <span className="pill">
              service_date {autoLockResult.service_date} · locked {autoLockResult.locked_count}/{autoLockResult.considered_open_plans} ·
              enabled {autoLockResult.auto_lock_enabled ? "true" : "false"} · window{" "}
              {autoLockResult.window_reached ? "reached" : "not_reached"}
            </span>
          )}
        </div>
      )}
      <div className="row">
        <input placeholder="zone_id para crear plan" value={newPlanZoneId} onChange={(e) => onNewPlanZoneIdChange(e.target.value)} />
        <button onClick={onCreatePlan}>Crear plan</button>
      </div>
      <div className="row">
        <input placeholder="plan_id" value={includePlanId} onChange={(e) => onIncludePlanIdChange(e.target.value)} />
        <input placeholder="order_id" value={includeOrderId} onChange={(e) => onIncludeOrderIdChange(e.target.value)} />
        <button className="secondary" onClick={onIncludeOrder}>
          Incluir pedido
        </button>
      </div>
      <table>
        <thead>
          <tr>
            <th>id</th>
            <th>zona</th>
            <th>estado</th>
            <th>vehículo</th>
            <th>peso_kg</th>
            <th>con/sin peso</th>
            <th>asignar vehículo</th>
            <th>acción</th>
          </tr>
        </thead>
        <tbody>
          {plans.length === 0 && (
            <tr>
              <td colSpan={8} style={{ color: "var(--muted)" }}>
                Sin planes para la fecha actual.
              </td>
            </tr>
          )}
          {plans.map((plan) => (
            <tr key={plan.id}>
              <td>{shortId(plan.id)}</td>
              <td>{shortId(plan.zone_id)}</td>
              <td>{plan.status}</td>
              <td>
                {plan.vehicle_id ? (
                  <div className="grid" style={{ gap: 2 }}>
                    <span>{plan.vehicle_name ?? "vehículo"}</span>
                    <small style={{ color: "var(--muted)" }}>
                      {plan.vehicle_code ?? shortId(plan.vehicle_id)}
                      {plan.vehicle_capacity_kg != null ? ` · cap ${plan.vehicle_capacity_kg} kg` : ""}
                    </small>
                  </div>
                ) : (
                  "—"
                )}
              </td>
              <td>{plan.total_weight_kg}</td>
              <td>
                {plan.orders_with_weight}/{plan.orders_total}
                {plan.orders_missing_weight > 0 ? ` (${plan.orders_missing_weight} sin peso)` : ""}
              </td>
              <td>
                {canAssignPlanVehicle ? (
                  <div className="row" style={{ gap: 6 }}>
                    <input
                      placeholder="vehicle_id (uuid)"
                      value={vehicleDrafts[plan.id] ?? (plan.vehicle_id ?? "")}
                      onChange={(e) => onVehicleDraftChange(plan.id, e.target.value)}
                      style={{ width: 220 }}
                    />
                    <button className="secondary" onClick={() => onSavePlanVehicle(plan)} disabled={savingVehiclePlanId === plan.id}>
                      {savingVehiclePlanId === plan.id ? "Guardando..." : "Guardar"}
                    </button>
                    <button className="secondary" onClick={() => onSavePlanVehicle(plan, true)} disabled={savingVehiclePlanId === plan.id}>
                      Limpiar
                    </button>
                  </div>
                ) : (
                  <span style={{ color: "var(--muted)" }}>solo lectura</span>
                )}
              </td>
              <td className="row">
                {plan.status === "open" && <button onClick={() => onLockPlan(plan.id)}>Lock</button>}
                <button className="secondary" onClick={() => onLoadPlanConsolidation(plan.id)} disabled={planConsolidationLoading}>
                  Consolidar
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
