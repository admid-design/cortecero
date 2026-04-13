import React from "react";
import type { AvailableVehicleItem, ReadyToDispatchItem } from "../lib/api";

type RoutingSidePanelsProps = {
  canManage: boolean;
  readyOrders: ReadyToDispatchItem[];
  availableVehicles: AvailableVehicleItem[];
  planId: string;
  onPlanIdChange: (value: string) => void;
  planVehicleId: string;
  onPlanVehicleIdChange: (value: string) => void;
  planDriverId: string;
  onPlanDriverIdChange: (value: string) => void;
  planOrderIds: string;
  onPlanOrderIdsChange: (value: string) => void;
  creatingPlan: boolean;
  onCreatePlan: () => void;
};

function shortId(value: string): string {
  return value.slice(0, 8);
}

export function RoutingSidePanels({
  canManage,
  readyOrders,
  availableVehicles,
  planId,
  onPlanIdChange,
  planVehicleId,
  onPlanVehicleIdChange,
  planDriverId,
  onPlanDriverIdChange,
  planOrderIds,
  onPlanOrderIdsChange,
  creatingPlan,
  onCreatePlan,
}: RoutingSidePanelsProps) {
  return (
    <>
      <div className="grid cols-2 routing-side-panels">
        <div className="card grid">
          <h3>Pedidos Ready to Dispatch</h3>
          {!canManage && (
            <p style={{ margin: 0, color: "#6b7280" }}>Solo `logistics/admin` pueden consultar este bloque.</p>
          )}
          {canManage && (
            <table>
              <thead>
                <tr>
                  <th>order_id</th>
                  <th>customer_id</th>
                  <th>zone_id</th>
                  <th>peso_kg</th>
                </tr>
              </thead>
              <tbody>
                {readyOrders.length === 0 && (
                  <tr>
                    <td colSpan={4} style={{ color: "#6b7280" }}>
                      Sin pedidos planned para esta fecha.
                    </td>
                  </tr>
                )}
                {readyOrders.map((item) => (
                  <tr key={item.id}>
                    <td>{shortId(item.id)}</td>
                    <td>{shortId(item.customer_id)}</td>
                    <td>{shortId(item.zone_id)}</td>
                    <td>{item.total_weight_kg == null ? "—" : item.total_weight_kg}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="card grid">
          <h3>Vehículos Disponibles</h3>
          {!canManage && (
            <p style={{ margin: 0, color: "#6b7280" }}>Solo `logistics/admin` pueden consultar este bloque.</p>
          )}
          {canManage && (
            <table>
              <thead>
                <tr>
                  <th>vehicle</th>
                  <th>capacidad_kg</th>
                  <th>driver</th>
                </tr>
              </thead>
              <tbody>
                {availableVehicles.length === 0 && (
                  <tr>
                    <td colSpan={3} style={{ color: "#6b7280" }}>
                      Sin vehículos activos disponibles.
                    </td>
                  </tr>
                )}
                {availableVehicles.map((item) => (
                  <tr key={item.id}>
                    <td>
                      {item.name}
                      <br />
                      <small style={{ color: "#6b7280" }}>{item.code}</small>
                    </td>
                    <td>{item.capacity_kg == null ? "—" : item.capacity_kg}</td>
                    <td>{item.driver ? `${item.driver.name} (${item.driver.phone})` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="card grid routing-plan-form">
        <h3>Planificar Ruta</h3>
        {!canManage && <p style={{ margin: 0, color: "#6b7280" }}>Solo `logistics/admin` pueden planificar.</p>}
        {canManage && (
          <>
            <div className="row">
              <input placeholder="plan_id (uuid)" value={planId} onChange={(e) => onPlanIdChange(e.target.value)} style={{ minWidth: 280 }} />
              <select value={planVehicleId} onChange={(e) => onPlanVehicleIdChange(e.target.value)}>
                <option value="">vehicle_id</option>
                {availableVehicles.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} · {item.code}
                  </option>
                ))}
              </select>
              <input
                placeholder="driver_id (uuid opcional)"
                value={planDriverId}
                onChange={(e) => onPlanDriverIdChange(e.target.value)}
                style={{ minWidth: 280 }}
              />
            </div>
            <textarea
              placeholder="order_ids (uuid separados por coma/espacio/salto)"
              rows={3}
              value={planOrderIds}
              onChange={(e) => onPlanOrderIdsChange(e.target.value)}
            />
            <button onClick={onCreatePlan} disabled={creatingPlan}>
              {creatingPlan ? "Planificando..." : "Planificar ruta"}
            </button>
          </>
        )}
      </div>
    </>
  );
}
