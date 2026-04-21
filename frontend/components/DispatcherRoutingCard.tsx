import React from "react";
import type {
  AvailableVehicleItem,
  ReadyToDispatchItem,
  RouteEventItem,
  RoutingRoute,
  RoutingRouteStatus,
} from "../lib/api";

type LocalDriverPosition = {
  lat?: number | null;
  lng?: number | null;
  updated_at?: string | null;
};
import { RouteDetailCard } from "./RouteDetailCard";
import { RoutingSidePanels } from "./RoutingSidePanels";

type DispatcherRoutingCardProps = {
  serviceDate: string;
  onServiceDateChange: (value: string) => void;
  routeStatus: "all" | RoutingRouteStatus;
  onRouteStatusChange: (value: "all" | RoutingRouteStatus) => void;
  loading: boolean;
  canManage: boolean;
  readyOrders: ReadyToDispatchItem[];
  availableVehicles: AvailableVehicleItem[];
  routes: RoutingRoute[];
  selectedRouteId: string;
  onSelectedRouteIdChange: (value: string) => void;
  selectedRoute: RoutingRoute | null;
  routeEvents: RouteEventItem[];
  routeDetailLoading: boolean;
  planId: string;
  onPlanIdChange: (value: string) => void;
  planVehicleId: string;
  onPlanVehicleIdChange: (value: string) => void;
  planDriverId: string;
  onPlanDriverIdChange: (value: string) => void;
  planOrderIds: string;
  onPlanOrderIdsChange: (value: string) => void;
  creatingPlan: boolean;
  optimizingRouteId: string | null;
  dispatchingRouteId: string | null;
  recalculatingEtaRouteId?: string | null;
  moveSourceRouteId: string;
  onMoveSourceRouteIdChange: (value: string) => void;
  moveStopId: string;
  onMoveStopIdChange: (value: string) => void;
  moveTargetRouteId: string;
  onMoveTargetRouteIdChange: (value: string) => void;
  movingStop: boolean;
  onRefresh: () => void;
  onCreatePlan: () => void;
  onOptimizeRoute: (routeId: string) => void;
  onDispatchRoute: (routeId: string) => void;
  onRecalculateEta?: (routeId: string) => void;
  onMoveStop: () => void;
  /** Posición actual del conductor — actualizada por polling en page.tsx. */
  driverPosition?: LocalDriverPosition | null;
};

function routeStatusBadgeClass(status: RoutingRouteStatus): string {
  if (status === "completed") return "badge ok";
  if (status === "draft") return "badge intake-addon";
  if (status === "planned" || status === "dispatched" || status === "in_progress") return "badge late";
  if (status === "cancelled") return "badge rejected";
  return "badge intake-unknown";
}

export function DispatcherRoutingCard({
  serviceDate,
  onServiceDateChange,
  routeStatus,
  onRouteStatusChange,
  loading,
  canManage,
  readyOrders,
  availableVehicles,
  routes,
  selectedRouteId,
  onSelectedRouteIdChange,
  selectedRoute,
  routeEvents,
  routeDetailLoading,
  planId,
  onPlanIdChange,
  planVehicleId,
  onPlanVehicleIdChange,
  planDriverId,
  onPlanDriverIdChange,
  planOrderIds,
  onPlanOrderIdsChange,
  creatingPlan,
  optimizingRouteId,
  dispatchingRouteId,
  // recalculatingEtaRouteId — accepted but not rendered in legacy card
  moveSourceRouteId,
  onMoveSourceRouteIdChange,
  moveStopId,
  onMoveStopIdChange,
  moveTargetRouteId,
  onMoveTargetRouteIdChange,
  movingStop,
  onRefresh,
  onCreatePlan,
  onOptimizeRoute,
  onDispatchRoute,
  // onRecalculateEta — accepted but not rendered in legacy card
  onMoveStop,
  driverPosition,
}: DispatcherRoutingCardProps) {
  return (
    <div className="card grid">
      <h2>Dispatcher Routing</h2>
      <div className="row">
        <label>
          service_date <input type="date" value={serviceDate} onChange={(e) => onServiceDateChange(e.target.value)} />
        </label>
        <label>
          route_status{" "}
          <select value={routeStatus} onChange={(e) => onRouteStatusChange(e.target.value as "all" | RoutingRouteStatus)}>
            <option value="all">all</option>
            <option value="draft">draft</option>
            <option value="planned">planned</option>
            <option value="dispatched">dispatched</option>
            <option value="in_progress">in_progress</option>
            <option value="completed">completed</option>
            <option value="cancelled">cancelled</option>
          </select>
        </label>
        <button className="secondary" onClick={onRefresh}>
          {loading ? "Cargando..." : "Refrescar routing"}
        </button>
      </div>

      <RoutingSidePanels
        canManage={canManage}
        readyOrders={readyOrders}
        availableVehicles={availableVehicles}
        planId={planId}
        onPlanIdChange={onPlanIdChange}
        planVehicleId={planVehicleId}
        onPlanVehicleIdChange={onPlanVehicleIdChange}
        planDriverId={planDriverId}
        onPlanDriverIdChange={onPlanDriverIdChange}
        planOrderIds={planOrderIds}
        onPlanOrderIdsChange={onPlanOrderIdsChange}
        creatingPlan={creatingPlan}
        onCreatePlan={onCreatePlan}
      />

      <div className="card grid">
        <h3>Rutas</h3>
        <table>
          <thead>
            <tr>
              <th>route_id</th>
              <th>plan_id</th>
              <th>vehicle_id</th>
              <th>driver_id</th>
              <th>status</th>
              <th>version</th>
              <th>stops</th>
              <th>acciones</th>
            </tr>
          </thead>
          <tbody>
            {routes.length === 0 && (
              <tr>
                <td colSpan={8} style={{ color: "var(--muted)" }}>
                  Sin rutas para los filtros actuales.
                </td>
              </tr>
            )}
            {routes.map((route) => (
              <tr key={route.id}>
                <td>{route.id.slice(0, 8)}</td>
                <td>{route.plan_id ? route.plan_id.slice(0, 8) : "—"}</td>
                <td>{route.vehicle_id.slice(0, 8)}</td>
                <td>{route.driver_id ? route.driver_id.slice(0, 8) : "—"}</td>
                <td>
                  <span className={routeStatusBadgeClass(route.status)}>{route.status}</span>
                </td>
                <td>{route.version}</td>
                <td>{route.stops.length}</td>
                <td className="row">
                  <button className="secondary" onClick={() => onSelectedRouteIdChange(route.id)}>
                    Detalle
                  </button>
                  {canManage && route.status === "draft" && (
                    <button
                      className="secondary"
                      onClick={() => onOptimizeRoute(route.id)}
                      disabled={optimizingRouteId === route.id}
                    >
                      {optimizingRouteId === route.id ? "Optimizando..." : "Optimize"}
                    </button>
                  )}
                  {canManage && route.status === "planned" && (
                    <button onClick={() => onDispatchRoute(route.id)} disabled={dispatchingRouteId === route.id}>
                      {dispatchingRouteId === route.id ? "Despachando..." : "Dispatch"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <RouteDetailCard
        routes={routes}
        selectedRouteId={selectedRouteId}
        onSelectedRouteIdChange={onSelectedRouteIdChange}
        routeDetailLoading={routeDetailLoading}
        selectedRoute={selectedRoute}
        routeEvents={routeEvents}
        driverPosition={driverPosition}
      />

      <div className="card grid">
        <h3>Move Stop</h3>
        {!canManage && <p style={{ margin: 0, color: "var(--muted)" }}>Solo `logistics/admin` pueden mover paradas.</p>}
        {canManage && (
          <>
            <div className="row">
              <select value={moveSourceRouteId} onChange={(e) => onMoveSourceRouteIdChange(e.target.value)} style={{ minWidth: 320 }}>
                <option value="">source_route_id</option>
                {routes.map((route) => (
                  <option key={route.id} value={route.id}>
                    {route.id.slice(0, 8)} · {route.status}
                  </option>
                ))}
              </select>
              <input placeholder="stop_id" value={moveStopId} onChange={(e) => onMoveStopIdChange(e.target.value)} style={{ minWidth: 280 }} />
              <select value={moveTargetRouteId} onChange={(e) => onMoveTargetRouteIdChange(e.target.value)} style={{ minWidth: 320 }}>
                <option value="">target_route_id</option>
                {routes.map((route) => (
                  <option key={route.id} value={route.id}>
                    {route.id.slice(0, 8)} · {route.status}
                  </option>
                ))}
              </select>
              <button className="secondary" onClick={onMoveStop} disabled={movingStop}>
                {movingStop ? "Moviendo..." : "Mover parada"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
