import React from "react";
import type { CapacityAlertLevel, PlanCapacityAlert } from "../lib/api";

type CapacityAlertsTableCardProps = {
  serviceDate: string;
  onServiceDateChange: (value: string) => void;
  zoneId: string;
  onZoneIdChange: (value: string) => void;
  zoneOptions: string[];
  level: "all" | CapacityAlertLevel;
  onLevelChange: (value: "all" | CapacityAlertLevel) => void;
  alerts: PlanCapacityAlert[];
  onApplyFilters: () => void;
};

function shortId(value: string): string {
  return value.slice(0, 8);
}

export function CapacityAlertsTableCard({
  serviceDate,
  onServiceDateChange,
  zoneId,
  onZoneIdChange,
  zoneOptions,
  level,
  onLevelChange,
  alerts,
  onApplyFilters,
}: CapacityAlertsTableCardProps) {
  return (
    <div className="card grid capacity-alerts-table-card">
      <h2>Alertas de Capacidad</h2>
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
          level{" "}
          <select value={level} onChange={(e) => onLevelChange(e.target.value as "all" | CapacityAlertLevel)}>
            <option value="all">all</option>
            <option value="OVER_CAPACITY">OVER_CAPACITY</option>
            <option value="NEAR_CAPACITY">NEAR_CAPACITY</option>
          </select>
        </label>
        <button className="secondary" onClick={onApplyFilters}>
          Aplicar filtros
        </button>
      </div>
      <table>
        <thead>
          <tr>
            <th>plan_id</th>
            <th>zone_id</th>
            <th>vehículo</th>
            <th>peso_kg</th>
            <th>capacidad_kg</th>
            <th>usage_ratio</th>
            <th>alert_level</th>
          </tr>
        </thead>
        <tbody>
          {alerts.length === 0 && (
            <tr>
              <td colSpan={7} style={{ color: "#6b7280" }}>
                Sin alertas para los filtros actuales.
              </td>
            </tr>
          )}
          {alerts.map((item) => (
            <tr key={item.plan_id}>
              <td>{shortId(item.plan_id)}</td>
              <td>{shortId(item.zone_id)}</td>
              <td>{item.vehicle_name ?? item.vehicle_code ?? shortId(item.vehicle_id)}</td>
              <td>{item.total_weight_kg}</td>
              <td>{item.vehicle_capacity_kg}</td>
              <td>{item.usage_ratio.toFixed(2)}</td>
              <td>
                <span className={item.alert_level === "OVER_CAPACITY" ? "badge rejected" : "badge late"}>{item.alert_level}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
