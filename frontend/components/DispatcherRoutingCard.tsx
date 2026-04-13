import React from "react";
import type {
  AvailableVehicleItem,
  ReadyToDispatchItem,
  RouteEventItem,
  RoutingRoute,
  RoutingRouteStatus,
} from "../lib/api";
import { RouteDetailCard } from "./RouteDetailCard";

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
  onMoveStop: () => void;
};

function shortId(value: string): string {
  return value.slice(0, 8);
}

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
  onMoveStop,
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

      <div className="grid cols-2">
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

      <div className="card grid">
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
                <td colSpan={8} style={{ color: "#6b7280" }}>
                  Sin rutas para los filtros actuales.
                </td>
              </tr>
            )}
            {routes.map((route) => (
              <tr key={route.id}>
                <td>{shortId(route.id)}</td>
                <td>{shortId(route.plan_id)}</td>
                <td>{shortId(route.vehicle_id)}</td>
                <td>{route.driver_id ? shortId(route.driver_id) : "—"}</td>
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
      />

      <div className="card grid">
        <h3>Move Stop</h3>
        {!canManage && <p style={{ margin: 0, color: "#6b7280" }}>Solo `logistics/admin` pueden mover paradas.</p>}
        {canManage && (
          <>
            <div className="row">
              <select value={moveSourceRouteId} onChange={(e) => onMoveSourceRouteIdChange(e.target.value)} style={{ minWidth: 320 }}>
                <option value="">source_route_id</option>
                {routes.map((route) => (
                  <option key={route.id} value={route.id}>
                    {shortId(route.id)} · {route.status}
                  </option>
                ))}
              </select>
              <input placeholder="stop_id" value={moveStopId} onChange={(e) => onMoveStopIdChange(e.target.value)} style={{ minWidth: 280 }} />
              <select value={moveTargetRouteId} onChange={(e) => onMoveTargetRouteIdChange(e.target.value)} style={{ minWidth: 320 }}>
                <option value="">target_route_id</option>
                {routes.map((route) => (
                  <option key={route.id} value={route.id}>
                    {shortId(route.id)} · {route.status}
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
