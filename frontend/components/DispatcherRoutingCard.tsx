import React, { useEffect, useMemo, useRef, useState } from "react";
import type {
  AvailableVehicleItem,
  ReadyToDispatchItem,
  RouteEventItem,
  RoutingRoute,
  RouteStopStatus,
  RoutingRouteStatus,
} from "../lib/api";

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

type RouteMapPoint = {
  stopId: string;
  sequenceNumber: number;
  status: RouteStopStatus;
  lat: number;
  lng: number;
};

type GoogleMapsWindow = Window & {
  google?: {
    maps?: any;
  };
  __corteCeroGoogleMapsPromise?: Promise<void>;
};

function parseCoordinate(value: number | null | undefined): number | null {
  if (typeof value !== "number") return null;
  if (!Number.isFinite(value)) return null;
  return value;
}

function stopStatusColor(status: RouteStopStatus): string {
  if (status === "completed") return "#16a34a";
  if (status === "arrived" || status === "en_route") return "#2563eb";
  if (status === "failed") return "#dc2626";
  if (status === "skipped") return "#6b7280";
  return "#f59e0b";
}

async function loadGoogleMapsScript(apiKey: string): Promise<void> {
  if (typeof window === "undefined") return;
  if (!apiKey) throw new Error("MISSING_MAPS_API_KEY");

  const mapsWindow = window as GoogleMapsWindow;
  if (mapsWindow.google?.maps) return;
  if (mapsWindow.__corteCeroGoogleMapsPromise) {
    await mapsWindow.__corteCeroGoogleMapsPromise;
    return;
  }

  mapsWindow.__corteCeroGoogleMapsPromise = new Promise<void>((resolve, reject) => {
    const existingScript = document.querySelector<HTMLScriptElement>('script[data-cortecero-google-maps="1"]');
    if (existingScript) {
      existingScript.addEventListener("load", () => resolve(), { once: true });
      existingScript.addEventListener("error", () => reject(new Error("GOOGLE_MAPS_LOAD_ERROR")), { once: true });
      return;
    }

    const script = document.createElement("script");
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}`;
    script.async = true;
    script.defer = true;
    script.dataset.corteceroGoogleMaps = "1";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("GOOGLE_MAPS_LOAD_ERROR"));
    document.head.appendChild(script);
  });

  await mapsWindow.__corteCeroGoogleMapsPromise;
}

function DispatcherRouteMap({ route }: { route: RoutingRoute }) {
  const mapRef = useRef<HTMLDivElement | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);
  const [mapsLoaded, setMapsLoaded] = useState(false);

  const mapApiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY ?? "";
  const depotLat = parseCoordinate(process.env.NEXT_PUBLIC_DEPOT_LAT ? Number(process.env.NEXT_PUBLIC_DEPOT_LAT) : null);
  const depotLng = parseCoordinate(process.env.NEXT_PUBLIC_DEPOT_LNG ? Number(process.env.NEXT_PUBLIC_DEPOT_LNG) : null);

  const stopPoints = useMemo<RouteMapPoint[]>(
    () =>
      route.stops
        .map((stop) => {
          const lat = parseCoordinate(stop.customer_lat);
          const lng = parseCoordinate(stop.customer_lng);
          if (lat == null || lng == null) return null;
          return {
            stopId: stop.id,
            sequenceNumber: stop.sequence_number,
            status: stop.status,
            lat,
            lng,
          } satisfies RouteMapPoint;
        })
        .filter((point): point is RouteMapPoint => point != null)
        .sort((a, b) => a.sequenceNumber - b.sequenceNumber),
    [route.stops],
  );

  useEffect(() => {
    let cancelled = false;

    if (!mapApiKey) {
      setMapError("Configura NEXT_PUBLIC_GOOGLE_MAPS_API_KEY para ver el mapa.");
      setMapsLoaded(false);
      return;
    }

    loadGoogleMapsScript(mapApiKey)
      .then(() => {
        if (cancelled) return;
        setMapError(null);
        setMapsLoaded(true);
      })
      .catch(() => {
        if (cancelled) return;
        setMapError("No se pudo cargar Google Maps JavaScript API.");
        setMapsLoaded(false);
      });

    return () => {
      cancelled = true;
    };
  }, [mapApiKey]);

  useEffect(() => {
    if (!mapsLoaded || !mapRef.current) return;

    const mapsWindow = window as GoogleMapsWindow;
    const maps = mapsWindow.google?.maps;
    if (!maps) return;

    const map = new maps.Map(mapRef.current, {
      mapTypeControl: false,
      streetViewControl: false,
      fullscreenControl: false,
      center: { lat: 40.4168, lng: -3.7038 },
      zoom: 10,
    });

    const bounds = new maps.LatLngBounds();
    const markers: Array<{ setMap: (map: any) => void }> = [];

    const pathPoints: Array<{ lat: number; lng: number }> = [];
    if (depotLat != null && depotLng != null) {
      markers.push(
        new maps.Marker({
          map,
          position: { lat: depotLat, lng: depotLng },
          title: "Depot",
          label: "D",
        }),
      );
      bounds.extend({ lat: depotLat, lng: depotLng });
      pathPoints.push({ lat: depotLat, lng: depotLng });
    }

    for (const stop of stopPoints) {
      const marker = new maps.Marker({
        map,
        position: { lat: stop.lat, lng: stop.lng },
        title: `Stop #${stop.sequenceNumber}`,
        label: String(stop.sequenceNumber),
        icon: {
          path: maps.SymbolPath.CIRCLE,
          scale: 8,
          fillColor: stopStatusColor(stop.status),
          fillOpacity: 1,
          strokeColor: "#ffffff",
          strokeWeight: 2,
        },
      });
      markers.push(marker);
      bounds.extend({ lat: stop.lat, lng: stop.lng });
      pathPoints.push({ lat: stop.lat, lng: stop.lng });
    }

    const polyline =
      pathPoints.length >= 2
        ? new maps.Polyline({
            path: pathPoints,
            map,
            geodesic: true,
            strokeColor: "#2563eb",
            strokeOpacity: 0.8,
            strokeWeight: 4,
          })
        : null;

    if (!bounds.isEmpty()) {
      map.fitBounds(bounds);
      if (pathPoints.length <= 1) {
        map.setZoom(13);
      }
    }

    return () => {
      for (const marker of markers) marker.setMap(null);
      if (polyline) polyline.setMap(null);
    };
  }, [mapsLoaded, stopPoints, depotLat, depotLng, route.id]);

  return (
    <div className="card grid">
      <h4 style={{ margin: 0 }}>Mapa de Ruta</h4>
      <div className="row" style={{ gap: 6 }}>
        <span className="pill">paradas geo-ready: {stopPoints.length}</span>
        {depotLat != null && depotLng != null && <span className="pill">depot: disponible</span>}
      </div>
      {mapError && <p style={{ margin: 0, color: "#6b7280" }}>{mapError}</p>}
      {!mapError && stopPoints.length === 0 && (
        <p style={{ margin: 0, color: "#6b7280" }}>
          Esta ruta no tiene coordenadas de cliente; no se puede dibujar recorrido.
        </p>
      )}
      <div
        ref={mapRef}
        style={{
          width: "100%",
          minHeight: 320,
          border: "1px solid #e5e7eb",
          borderRadius: 10,
          background: "#f8fafc",
        }}
      />
    </div>
  );
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

      <div className="card grid">
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
            <DispatcherRouteMap route={selectedRoute} />
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
