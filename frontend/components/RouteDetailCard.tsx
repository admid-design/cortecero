import React from "react";
import type { RouteEventItem, RoutingRoute } from "../lib/api";
import { RouteMapCard } from "./RouteMapCard";

type RouteDetailCardProps = {
  routes: RoutingRoute[];
  selectedRouteId: string;
  onSelectedRouteIdChange: (value: string) => void;
  routeDetailLoading: boolean;
  selectedRoute: RoutingRoute | null;
  routeEvents: RouteEventItem[];
};

function shortId(value: string): string {
  return value.slice(0, 8);
}

export function RouteDetailCard({
  routes,
  selectedRouteId,
  onSelectedRouteIdChange,
  routeDetailLoading,
  selectedRoute,
  routeEvents,
}: RouteDetailCardProps) {
  return (
    <div className="card grid route-detail-card">
      <h3>Detalle de Ruta Seleccionada</h3>
      <div className="row">
        <select value={selectedRouteId} onChange={(e) => onSelectedRouteIdChange(e.target.value)} style={{ minWidth: 320 }}>
          <option value="">Selecciona route_id</option>
          {routes.map((route) => (
            <option key={route.id} value={route.id}>
              {route.service_date} · {shortId(route.id)} · {route.status}
            </option>
          ))}
        </select>
      </div>

      {routeDetailLoading && <p style={{ margin: 0, color: "#6b7280" }}>Cargando detalle de ruta...</p>}
      {!routeDetailLoading && !selectedRoute && (
        <p style={{ margin: 0, color: "#6b7280" }}>Selecciona una ruta para ver paradas y eventos.</p>
      )}

      {selectedRoute && (
        <>
          <div className="row" style={{ gap: 6 }}>
            <span className="pill">route_id: {shortId(selectedRoute.id)}</span>
            <span className="pill">status: {selectedRoute.status}</span>
            <span className="pill">stops: {selectedRoute.stops.length}</span>
          </div>
          <RouteMapCard route={selectedRoute} />
          <table>
            <thead>
              <tr>
                <th>seq</th>
                <th>stop_id</th>
                <th>order_id</th>
                <th>status</th>
                <th>eta</th>
              </tr>
            </thead>
            <tbody>
              {selectedRoute.stops.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ color: "#6b7280" }}>
                    Ruta sin paradas.
                  </td>
                </tr>
              )}
              {selectedRoute.stops.map((stop) => (
                <tr key={stop.id}>
                  <td>{stop.sequence_number}</td>
                  <td>{shortId(stop.id)}</td>
                  <td>{shortId(stop.order_id)}</td>
                  <td>{stop.status}</td>
                  <td>{stop.estimated_arrival_at ? new Date(stop.estimated_arrival_at).toLocaleString("es-ES") : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h4 style={{ margin: 0 }}>Eventos</h4>
          <table>
            <thead>
              <tr>
                <th>event_type</th>
                <th>actor</th>
                <th>ts</th>
              </tr>
            </thead>
            <tbody>
              {routeEvents.length === 0 && (
                <tr>
                  <td colSpan={3} style={{ color: "#6b7280" }}>
                    Sin eventos para esta ruta.
                  </td>
                </tr>
              )}
              {routeEvents.map((event) => (
                <tr key={event.id}>
                  <td>{event.event_type}</td>
                  <td>{event.actor_type}</td>
                  <td>{new Date(event.ts).toLocaleString("es-ES")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
