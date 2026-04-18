"use client";

import React, { useState, useEffect } from "react";
import type {
  AvailableVehicleItem,
  DashboardSummary,
  DriverOut,
  DriverPositionOut,
  Plan,
  ReadyToDispatchItem,
  RouteEventItem,
  RoutingRoute,
  RoutingRouteStatus,
  UserRole,
} from "../lib/api";
import { RouteMapCard } from "./RouteMapCard";

type LocalDriverPosition = {
  lat?: number | null;
  lng?: number | null;
  updated_at?: string | null;
};

type OpsMapDashboardProps = {
  // Auth / app
  role: UserRole | null;
  onLogout: () => void;
  onSwitchToAdmin?: () => void;
  isAdmin: boolean;
  error: string;

  // Summary KPIs
  summary: DashboardSummary | null;

  // Routes
  serviceDate: string;
  onServiceDateChange: (v: string) => void;
  routeStatus: "all" | RoutingRouteStatus;
  onRouteStatusChange: (v: "all" | RoutingRouteStatus) => void;
  loading: boolean;
  routes: RoutingRoute[];
  selectedRouteId: string;
  onSelectedRouteIdChange: (id: string) => void;
  selectedRoute: RoutingRoute | null;
  routeEvents: RouteEventItem[];
  routeDetailLoading: boolean;
  canManage: boolean;
  driverPosition?: LocalDriverPosition | null;
  /** Posiciones GPS de toda la flota activa — polling desde el padre */
  activePositions?: DriverPositionOut[] | null;

  // Route actions
  optimizingRouteId: string | null;
  dispatchingRouteId: string | null;
  onOptimizeRoute: (id: string) => void;
  onDispatchRoute: (id: string) => void;
  onRefresh: () => void;

  // Plan creation (advanced)
  readyOrders: ReadyToDispatchItem[];
  availableVehicles: AvailableVehicleItem[];
  availableDrivers: DriverOut[];
  availablePlans: Plan[];
  planId: string;
  onPlanIdChange: (v: string) => void;
  planVehicleId: string;
  onPlanVehicleIdChange: (v: string) => void;
  planDriverId: string;
  onPlanDriverIdChange: (v: string) => void;
  planOrderIds: string;
  onPlanOrderIdsChange: (v: string) => void;
  creatingPlan: boolean;
  onCreatePlan: () => void;

  // Move stop (advanced)
  moveSourceRouteId: string;
  onMoveSourceRouteIdChange: (v: string) => void;
  moveStopId: string;
  onMoveStopIdChange: (v: string) => void;
  moveTargetRouteId: string;
  onMoveTargetRouteIdChange: (v: string) => void;
  movingStop: boolean;
  onMoveStop: () => void;
};

// ─── helpers ──────────────────────────────────────────────────────────────────

function shortId(id: string) {
  return id.slice(0, 8);
}

/** Añade o quita un orderId del string CSV de planOrderIds */
function toggleOrderId(currentIds: string, orderId: string): string {
  const ids = currentIds
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  if (ids.includes(orderId)) {
    return ids.filter((id) => id !== orderId).join(", ");
  }
  return [...ids, orderId].join(", ");
}

/** Devuelve true si orderId está en el string CSV de planOrderIds */
function isOrderSelected(currentIds: string, orderId: string): boolean {
  return currentIds.split(",").map((s) => s.trim()).includes(orderId);
}

function routeStatusLabel(status: RoutingRouteStatus): string {
  const map: Record<RoutingRouteStatus, string> = {
    draft: "Borrador",
    planned: "Planificada",
    dispatched: "Despachada",
    in_progress: "En curso",
    completed: "Completada",
    cancelled: "Cancelada",
  };
  return map[status] ?? status;
}

function routeStatusBadgeClass(status: RoutingRouteStatus): string {
  if (status === "completed") return "badge ok";
  if (status === "in_progress" || status === "dispatched") return "badge late";
  if (status === "cancelled") return "badge rejected";
  return "badge intake-unknown";
}

function routeIcon(status: RoutingRouteStatus): string {
  if (status === "in_progress") return "🚚";
  if (status === "dispatched") return "📤";
  if (status === "completed") return "✅";
  if (status === "cancelled") return "❌";
  return "📋";
}

function stopSeqClass(status: string): string {
  if (status === "completed") return "mf-stop-seq completed";
  if (status === "arrived") return "mf-stop-seq arrived";
  if (status === "failed") return "mf-stop-seq failed";
  if (status === "skipped") return "mf-stop-seq skipped";
  return "mf-stop-seq";
}

// ─── NextActionCard ───────────────────────────────────────────────────────────

function NextActionCard({
  unassigned,
  activeRoutes,
  routes,
  onGoToGestion,
}: {
  unassigned: number;
  activeRoutes: number;
  routes: RoutingRoute[];
  onGoToGestion: () => void;
}) {
  const plannedOrDraft = routes.filter(
    (r) => r.status === "planned" || r.status === "draft",
  ).length;

  if (unassigned > 0 && routes.length === 0) {
    return (
      <div className="mf-next-action mf-next-action-warn" onClick={onGoToGestion}>
        <div className="mf-next-action-icon">📦</div>
        <div className="mf-next-action-body">
          <div className="mf-next-action-title">
            {unassigned} pedido{unassigned !== 1 ? "s" : ""} sin ruta
          </div>
          <div className="mf-next-action-sub">
            Ve a <strong>Gestión</strong> para crear rutas y asignar pedidos →
          </div>
        </div>
      </div>
    );
  }

  if (plannedOrDraft > 0) {
    return (
      <div className="mf-next-action mf-next-action-blue">
        <div className="mf-next-action-icon">⚡</div>
        <div className="mf-next-action-body">
          <div className="mf-next-action-title">
            {plannedOrDraft} ruta{plannedOrDraft !== 1 ? "s" : ""} lista{plannedOrDraft !== 1 ? "s" : ""} para operar
          </div>
          <div className="mf-next-action-sub">
            Selecciona una ruta · optimiza · despacha al conductor
          </div>
        </div>
      </div>
    );
  }

  if (activeRoutes > 0) {
    return (
      <div className="mf-next-action mf-next-action-ok">
        <div className="mf-next-action-icon">🚚</div>
        <div className="mf-next-action-body">
          <div className="mf-next-action-title">
            {activeRoutes} ruta{activeRoutes !== 1 ? "s" : ""} en curso
          </div>
          <div className="mf-next-action-sub">
            Selecciona una ruta para ver su recorrido en el mapa
          </div>
        </div>
      </div>
    );
  }

  if (routes.length > 0) {
    return (
      <div className="mf-next-action mf-next-action-ok">
        <div className="mf-next-action-icon">✅</div>
        <div className="mf-next-action-body">
          <div className="mf-next-action-title">Operación completada</div>
          <div className="mf-next-action-sub">Todas las rutas del día están finalizadas</div>
        </div>
      </div>
    );
  }

  return null;
}

// ─── component ────────────────────────────────────────────────────────────────

export function OpsMapDashboard({
  role,
  onLogout,
  onSwitchToAdmin,
  isAdmin,
  error,
  summary,
  serviceDate,
  onServiceDateChange,
  routeStatus,
  onRouteStatusChange,
  loading,
  routes,
  selectedRouteId,
  onSelectedRouteIdChange,
  selectedRoute,
  routeDetailLoading,
  canManage,
  driverPosition,
  activePositions,
  optimizingRouteId,
  dispatchingRouteId,
  onOptimizeRoute,
  onDispatchRoute,
  onRefresh,
  readyOrders,
  availableVehicles,
  availableDrivers,
  availablePlans,
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
  moveSourceRouteId,
  onMoveSourceRouteIdChange,
  moveStopId,
  onMoveStopIdChange,
  moveTargetRouteId,
  onMoveTargetRouteIdChange,
  movingStop,
  onMoveStop,
}: OpsMapDashboardProps) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [sidebarView, setSidebarView] = useState<"rutas" | "gestion">("rutas");
  const [routesSectionOpen, setRoutesSectionOpen] = useState(true);
  const [fleetSectionOpen, setFleetSectionOpen] = useState(true);
  const [unassignedGestionOpen, setUnassignedGestionOpen] = useState(true);
  const [driverSectionOpen, setDriverSectionOpen] = useState(true);
  const [selectedFleetVehicleId, setSelectedFleetVehicleId] = useState<string | null>(null);
  const [selectedFleetVehicleName, setSelectedFleetVehicleName] = useState<string | null>(null);

  // Auto-select plan when only one is available
  useEffect(() => {
    if (availablePlans.length === 1 && !planId) {
      onPlanIdChange(availablePlans[0].id);
    }
  }, [availablePlans, planId, onPlanIdChange]);

  // Derived KPIs
  const totalRoutes = routes.length;
  const activeRoutes = routes.filter(
    (r) => r.status === "in_progress" || r.status === "dispatched",
  ).length;
  const completedRoutes = routes.filter((r) => r.status === "completed").length;
  const unassigned = readyOrders.length;

  // Filtered routes
  const filteredRoutes =
    routeStatus === "all" ? routes : routes.filter((r) => r.status === routeStatus);

  // Lookup maps: vehicle_id → name, driver_id → name, vehicle_id → route_id
  const vehicleNameMap = React.useMemo(() => {
    const m: Record<string, string> = {};
    for (const v of availableVehicles) m[v.id] = v.name;
    return m;
  }, [availableVehicles]);

  const driverNameMap = React.useMemo(() => {
    const m: Record<string, string> = {};
    for (const v of availableVehicles) if (v.driver) m[v.driver.id] = v.driver.name;
    return m;
  }, [availableVehicles]);

  const vehicleRouteMap = React.useMemo(() => {
    const m: Record<string, string> = {};
    for (const r of routes) if (r.vehicle_id) m[r.vehicle_id] = r.id;
    return m;
  }, [routes]);

  // Set de driver_ids con posición GPS activa
  const activeDriverIdSet = React.useMemo(() => {
    const s = new Set<string>();
    for (const p of activePositions ?? []) s.add(p.driver_id);
    return s;
  }, [activePositions]);

  const emailDisplay = role ? `Rol: ${role}` : "—";

  // ── render ──────────────────────────────────────────────────────────────────
  return (
    <div className="map-first-shell">
      {/* ── SIDEBAR ── */}
      <aside className="mf-sidebar">
        <div className="mf-sidebar-logo">
          <div className="mf-sidebar-logo-icon">C</div>
          <div>
            <div className="mf-sidebar-logo-text">CorteCero</div>
            <div className="mf-sidebar-logo-sub">Panel operativo</div>
          </div>
        </div>

        <div className="mf-sidebar-section">
          <div className="mf-sidebar-section-label">Operación</div>
          <button
            className={`mf-nav-item${sidebarView === "rutas" ? " active" : ""}`}
            onClick={() => setSidebarView("rutas")}
          >
            <span className="mf-nav-icon">🗺</span>
            <span className="mf-nav-item-text">
              <span className="mf-nav-item-label">Rutas</span>
              <span className="mf-nav-item-sub">Ver mapa · optimizar · despachar</span>
            </span>
            {activeRoutes > 0 && (
              <span className="mf-badge-dot">{activeRoutes}</span>
            )}
          </button>
          <button
            className={`mf-nav-item${sidebarView === "gestion" ? " active" : ""}`}
            onClick={() => setSidebarView("gestion")}
          >
            <span className="mf-nav-icon">📋</span>
            <span className="mf-nav-item-text">
              <span className="mf-nav-item-label">Gestión</span>
              <span className="mf-nav-item-sub">Crear rutas · asignar pedidos</span>
            </span>
            {unassigned > 0 && (
              <span className="mf-badge-dot">{unassigned}</span>
            )}
          </button>
        </div>

        {isAdmin && (
          <div className="mf-sidebar-section">
            <div className="mf-sidebar-section-label">Sistema</div>
            <button className="mf-nav-item" onClick={onSwitchToAdmin}>
              <span className="mf-nav-icon">⚙️</span>
              Admin
            </button>
          </div>
        )}

        <div className="mf-sidebar-footer">
          <div className="mf-user-pill">
            <div className="mf-user-pill-dot" />
            <span className="mf-user-pill-text">{emailDisplay}</span>
          </div>
          <button className="mf-nav-item" onClick={onLogout}>
            <span className="mf-nav-icon">🚪</span>
            Cerrar sesión
          </button>
        </div>
      </aside>

      {/* ── CENTER COLUMN (map o gestión) ── */}
      <div className="mf-center-col">
      {sidebarView === "gestion" && (
        <div className="mf-gestion-area">
          <div className="mf-gestion-header">
            <h2 className="mf-gestion-title">Gestión operativa</h2>
            <span style={{ fontSize: 13, color: "#6b7280" }}>{serviceDate}</span>
          </div>

          {/* Pedidos sin asignar — colapsable */}
          <div className="mf-gestion-section">
            <div
              className="mf-gestion-section-toggle"
              onClick={() => setUnassignedGestionOpen((v) => !v)}
            >
              <h3>
                Pedidos sin asignar
                {readyOrders.length > 0 && (
                  <span className="mf-gestion-count-badge">{readyOrders.length}</span>
                )}
              </h3>
              <span className="mf-collapse-icon">{unassignedGestionOpen ? "▲" : "▼"}</span>
            </div>
            {unassignedGestionOpen && (
              readyOrders.length === 0 ? (
                <div className="mf-gestion-empty">Sin pedidos pendientes de asignación</div>
              ) : (
                <>
                  <div className="mf-orders-table-head">
                    <span>Pedido</span>
                    <span>Zona</span>
                    <span>Estado</span>
                  </div>
                  {readyOrders.map((order) => {
                    const selected = isOrderSelected(planOrderIds, order.id);
                    return (
                      <div
                        key={order.id}
                        className={`mf-orders-table-row clickable${selected ? " mf-order-selected" : ""}`}
                        onClick={() => onPlanOrderIdsChange(toggleOrderId(planOrderIds, order.id))}
                        title={selected ? "Clic para deseleccionar" : "Clic para añadir a la ruta"}
                      >
                        <span className="mf-orders-id">
                          {selected && <span style={{ color: "#2563eb", marginRight: 4 }}>✓</span>}
                          {shortId(order.id)}
                        </span>
                        <span className="mf-orders-zone">{order.zone_id || "—"}</span>
                        <span className={selected ? "badge ok" : "badge warn"}>
                          {selected ? "Seleccionado" : "Pendiente"}
                        </span>
                      </div>
                    );
                  })}
                </>
              )
            )}
          </div>

          {/* Crear ruta — formulario simplificado */}
          {canManage && (
            <div className="mf-gestion-section">
              <div className="mf-section-head" style={{ padding: "0 0 14px" }}>
                <h3>Crear ruta</h3>
              </div>

              {/* Paso 1: Plan */}
              <div className="mf-create-step">
                <div className="mf-create-step-label">
                  <span className="mf-step-num">1</span> Plan de servicio
                </div>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <select
                    className="mf-input"
                    style={{ flex: 1 }}
                    value={planId}
                    onChange={(e) => onPlanIdChange(e.target.value)}
                  >
                    <option value="">— Selecciona plan —</option>
                    {availablePlans.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.service_date} · Zona {p.zone_id.slice(0, 8)} · {p.status === "open" ? "Abierto" : p.status === "locked" ? "Bloqueado" : "Despachado"}
                      </option>
                    ))}
                  </select>
                  {planId && (
                    <button
                      className="mf-clear-btn"
                      onClick={() => onPlanIdChange("")}
                      title="Quitar plan"
                    >×</button>
                  )}
                </div>
                {availablePlans.length === 0 && (
                  <div className="mf-create-hint">No hay planes para {serviceDate}</div>
                )}
              </div>

              {/* Paso 2: Pedidos — ya seleccionados arriba */}
              <div className="mf-create-step">
                <div className="mf-create-step-label">
                  <span className="mf-step-num">2</span> Pedidos a incluir
                  {planOrderIds.trim() && (
                    <span className="mf-step-count">
                      {planOrderIds.split(",").filter(s => s.trim()).length} seleccionado{planOrderIds.split(",").filter(s => s.trim()).length !== 1 ? "s" : ""}
                    </span>
                  )}
                </div>
                {planOrderIds.trim() ? (
                  <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    <div className="mf-selected-summary">
                      {planOrderIds.split(",").filter(s => s.trim()).map(id => (
                        <span key={id} className="mf-order-chip">
                          {id.trim().slice(0, 8)}
                          <button
                            className="mf-chip-x"
                            onClick={() => onPlanOrderIdsChange(
                              planOrderIds.split(",").filter(s => s.trim() && s.trim() !== id.trim()).join(", ")
                            )}
                          >×</button>
                        </span>
                      ))}
                    </div>
                    <button
                      className="mf-clear-btn"
                      onClick={() => onPlanOrderIdsChange("")}
                      title="Quitar todos"
                    >×</button>
                  </div>
                ) : (
                  <div className="mf-create-hint">
                    ↑ Selecciona pedidos de la lista de arriba
                  </div>
                )}
              </div>

              {/* Paso 3: Vehículo */}
              <div className="mf-create-step">
                <div className="mf-create-step-label">
                  <span className="mf-step-num">3</span> Vehículo
                </div>
                {planVehicleId ? (
                  <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    <div className="mf-selected-chip-row">
                      🚚 {availableVehicles.find(v => v.id === planVehicleId)?.name ?? shortId(planVehicleId)}
                    </div>
                    <button
                      className="mf-clear-btn"
                      onClick={() => onPlanVehicleIdChange("")}
                      title="Quitar vehículo"
                    >×</button>
                  </div>
                ) : (
                  <div className="mf-create-hint">↙ Selecciona un vehículo del panel Flota</div>
                )}
              </div>

              {/* Paso 4: Conductor */}
              <div className="mf-create-step">
                <div className="mf-create-step-label">
                  <span className="mf-step-num">4</span> Conductor <span style={{ fontWeight: 400, color: "#9ca3af" }}>(opcional)</span>
                </div>
                {planDriverId ? (
                  <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    <div className="mf-selected-chip-row">
                      👤 {availableDrivers.find(d => d.id === planDriverId)?.name ?? shortId(planDriverId)}
                    </div>
                    <button
                      className="mf-clear-btn"
                      onClick={() => onPlanDriverIdChange("")}
                      title="Quitar conductor"
                    >×</button>
                  </div>
                ) : (
                  <div className="mf-create-hint">↙ Selecciona un conductor del panel Conductores</div>
                )}
              </div>

              <button
                className="mf-btn primary"
                disabled={creatingPlan || !planId || !planVehicleId || planOrderIds.trim().split(",").filter(s => s.trim()).length === 0}
                onClick={onCreatePlan}
                style={{ width: "100%", marginTop: 8 }}
              >
                {creatingPlan ? "Creando..." : "✓ Crear ruta"}
              </button>

              {(!planId || !planVehicleId || planOrderIds.trim().split(",").filter(s => s.trim()).length === 0) && (
                <div className="mf-create-hint" style={{ marginTop: 6, textAlign: "center" }}>
                  {!planId ? "Falta: plan · " : ""}
                  {planOrderIds.trim().split(",").filter(s => s.trim()).length === 0 ? "Falta: pedidos · " : ""}
                  {!planVehicleId ? "Falta: vehículo" : ""}
                </div>
              )}
            </div>
          )}

          {/* Mover parada — solo si la ruta tiene paradas */}
          {canManage && selectedRoute && selectedRoute.stops.length > 0 && (
            <div className="mf-gestion-section">
              <div className="mf-section-head" style={{ padding: "0 0 14px" }}>
                <h3>Mover parada</h3>
              </div>
              <div className="mf-gestion-form">
                <div className="mf-form-row">
                  <span className="mf-form-label">Parada</span>
                  <select className="mf-input" value={moveStopId} onChange={(e) => onMoveStopIdChange(e.target.value)}>
                    <option value="">— Selecciona parada —</option>
                    {selectedRoute.stops.map((s) => (
                      <option key={s.id} value={s.id}>#{s.sequence_number} {shortId(s.order_id)}</option>
                    ))}
                  </select>
                </div>
                <div className="mf-form-row">
                  <span className="mf-form-label">Ruta destino</span>
                  <select className="mf-input" value={moveTargetRouteId} onChange={(e) => onMoveTargetRouteIdChange(e.target.value)}>
                    <option value="">— Selecciona ruta —</option>
                    {routes.filter((r) => r.id !== selectedRouteId).map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.vehicle_id ? `Vehículo ${shortId(r.vehicle_id)}` : shortId(r.id)} · {routeStatusLabel(r.status)}
                      </option>
                    ))}
                  </select>
                </div>
                <button className="mf-btn secondary" disabled={movingStop || !moveStopId || !moveTargetRouteId} onClick={onMoveStop} style={{ width: "100%", marginTop: 4 }}>
                  {movingStop ? "Moviendo..." : "Mover parada"}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── MAP CENTER ── */}
      {sidebarView === "rutas" && <div className="mf-map-area">
        {/* Filter bar */}
        <div className="mf-map-filter-bar">
          <div className="mf-status-pills">
            {(
              [
                { value: "all", label: "Todas" },
                { value: "in_progress", label: "En curso" },
                { value: "dispatched", label: "Despachada" },
                { value: "planned", label: "Planificada" },
                { value: "completed", label: "Completada" },
                { value: "draft", label: "Borrador" },
                { value: "cancelled", label: "Cancelada" },
              ] as { value: "all" | RoutingRouteStatus; label: string }[]
            ).map((opt) => (
              <button
                key={opt.value}
                className={`mf-status-pill${routeStatus === opt.value ? " active" : ""}`}
                onClick={() => onRouteStatusChange(opt.value)}
              >
                {opt.label}
              </button>
            ))}
          </div>

          <div className="mf-filter-right">
            <input
              type="date"
              className="mf-filter-pill"
              value={serviceDate}
              onChange={(e) => onServiceDateChange(e.target.value)}
              title="Fecha de servicio"
            />
            <button
              className="mf-filter-pill mf-refresh-btn"
              onClick={onRefresh}
              disabled={loading}
            >
              {loading ? "⏳" : "↻"} {loading ? "Actualizando..." : "Actualizar"}
            </button>
          </div>
        </div>

        {/* Map — always visible; markers appear when a route is selected */}
        <div style={{ position: "relative", flex: 1, minHeight: 0 }}>
          <RouteMapCard
            route={selectedRoute}
            driverPosition={driverPosition}
            selectedVehicleId={selectedFleetVehicleId}
            selectedVehicleName={selectedFleetVehicleName}
            activePositions={activePositions}
          />
          {/* Empty state overlay */}
          {!selectedRoute && (
            <div className="mf-map-empty-state">
              <div className="mf-map-empty-icon">📍</div>
              <div className="mf-map-empty-title">Ninguna ruta seleccionada</div>
              <div className="mf-map-empty-sub">
                Selecciona una ruta del panel derecho para ver su recorrido aquí
              </div>
            </div>
          )}
          {selectedRoute && selectedRoute.stops.length === 0 && !selectedRoute.route_geometry && (
            <div className="mf-map-empty-state">
              <div className="mf-map-empty-icon">🗺️</div>
              <div className="mf-map-empty-title">Ruta sin paradas aún</div>
              <div className="mf-map-empty-sub">
                Esta ruta está en borrador. Ve a <strong>Gestión</strong> para asignar pedidos,
                luego optimiza para ver el recorrido.
              </div>
            </div>
          )}

          {/* Floating overlay stats */}
          <div className="mf-map-overlay-stats">
            <div className="mf-overlay-stat">
              <span className="mf-overlay-stat-value">{totalRoutes}</span>
              <span className="mf-overlay-stat-label">Total rutas</span>
            </div>
            <div className="mf-overlay-stat-sep" />
            <div className="mf-overlay-stat">
              <span
                className="mf-overlay-stat-value"
                style={{ color: activeRoutes > 0 ? "#2563eb" : "#6b7280" }}
              >
                {activeRoutes}
              </span>
              <span className="mf-overlay-stat-label">En curso</span>
            </div>
            {completedRoutes > 0 && (
              <>
                <div className="mf-overlay-stat-sep" />
                <div className="mf-overlay-stat">
                  <span className="mf-overlay-stat-value" style={{ color: "#16a34a" }}>
                    {completedRoutes}
                  </span>
                  <span className="mf-overlay-stat-label">Completadas</span>
                </div>
              </>
            )}
          </div>
        </div>
      </div>}
      </div>{/* end mf-center-col */}

      {/* ── RIGHT PANEL ── */}
      <div className="mf-right-panel">
        {/* Error banner */}
        {error && <div className="mf-error-banner">⚠️ {error}</div>}

        {/* KPIs */}
        <div className="mf-kpi-grid">
          <div className="mf-kpi-card mf-kpi-blue">
            <span className="mf-kpi-icon">📋</span>
            <div className="mf-kpi-data">
              <span className="mf-kpi-value">{totalRoutes}</span>
              <span className="mf-kpi-label">Rutas hoy</span>
            </div>
          </div>
          <div className="mf-kpi-card mf-kpi-orange">
            <span className="mf-kpi-icon">🚚</span>
            <div className="mf-kpi-data">
              <span className="mf-kpi-value">{activeRoutes}</span>
              <span className="mf-kpi-label">En curso</span>
            </div>
          </div>
          <div className="mf-kpi-card mf-kpi-green">
            <span className="mf-kpi-icon">✅</span>
            <div className="mf-kpi-data">
              <span className="mf-kpi-value">{completedRoutes}</span>
              <span className="mf-kpi-label">Completadas</span>
            </div>
          </div>
          <div
            className={`mf-kpi-card mf-kpi-amber${unassigned > 0 ? " clickable" : ""}`}
            onClick={unassigned > 0 ? () => setSidebarView("gestion") : undefined}
            title={unassigned > 0 ? "Ir a Gestión para asignar pedidos" : undefined}
          >
            <span className="mf-kpi-icon">📦</span>
            <div className="mf-kpi-data">
              <span className="mf-kpi-value">{unassigned}</span>
              <span className="mf-kpi-label">Sin asignar{unassigned > 0 ? " →" : ""}</span>
            </div>
          </div>
        </div>

        {/* Próxima acción contextual */}
        <NextActionCard
          unassigned={unassigned}
          activeRoutes={activeRoutes}
          routes={filteredRoutes}
          onGoToGestion={() => setSidebarView("gestion")}
        />

        {/* Routes list */}
        <div className="mf-section">
          <div
            className="mf-section-head mf-section-head-toggle"
            onClick={() => setRoutesSectionOpen((v) => !v)}
          >
            <h3>Rutas</h3>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              {filteredRoutes.length > 0 && (
                <span className="mf-section-head-count">{filteredRoutes.length}</span>
              )}
              <span className="mf-collapse-icon">{routesSectionOpen ? "▲" : "▼"}</span>
            </div>
          </div>

          {routesSectionOpen && filteredRoutes.length === 0 && (
            <div style={{ padding: "10px 16px 14px", color: "#9ca3af", fontSize: 13 }}>
              Sin rutas para los filtros actuales.
            </div>
          )}

          {routesSectionOpen && filteredRoutes.length > 0 && (
            <div className="mf-route-table-head">
              <span>Vehículo</span>
              <span>Conductor</span>
              <span>Paradas</span>
              <span>Estado</span>
            </div>
          )}

          {routesSectionOpen && filteredRoutes.map((route) => (
            <div
              key={route.id}
              className={`mf-route-row${route.id === selectedRouteId ? " selected" : ""}`}
              onClick={() =>
                onSelectedRouteIdChange(route.id === selectedRouteId ? "" : route.id)
              }
            >
              <div className="mf-route-col-vehicle">
                <span className="mf-route-row-icon">{routeIcon(route.status)}</span>
                <span className="mf-route-row-title">
                  {route.vehicle_id
                    ? (vehicleNameMap[route.vehicle_id] ?? shortId(route.vehicle_id))
                    : shortId(route.id)}
                </span>
              </div>
              <div className="mf-route-col-driver">
                {route.driver_id ? (
                  <span className="mf-driver-chip">
                    <span className="mf-driver-chip-avatar">
                      {(driverNameMap[route.driver_id] ?? shortId(route.driver_id))[0].toUpperCase()}
                    </span>
                    {driverNameMap[route.driver_id] ?? shortId(route.driver_id)}
                  </span>
                ) : (
                  <span style={{ color: "#9ca3af", fontSize: 11 }}>—</span>
                )}
              </div>
              <div className="mf-route-col-stops">
                <span className="mf-stop-count">{route.stops.length}</span>
              </div>
              <span className={routeStatusBadgeClass(route.status)}>
                {routeStatusLabel(route.status)}
              </span>
            </div>
          ))}
        </div>

        <div className="mf-divider" />

        {/* Route detail */}
        {selectedRoute && (
          <div className="mf-detail-section">
            <div className="mf-detail-title">Ruta seleccionada</div>

            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
              <span className={routeStatusBadgeClass(selectedRoute.status)}>
                {routeStatusLabel(selectedRoute.status)}
              </span>
              <span className="badge intake-unknown">
                {selectedRoute.stops.length} paradas
              </span>
              {selectedRoute.route_geometry && (
                <span className="badge ok">geometría real</span>
              )}
            </div>

            {/* Driver Details card */}
            {selectedRoute.driver_id && (
              <div className="mf-driver-card">
                <div className="mf-driver-avatar-lg">
                  {shortId(selectedRoute.driver_id)[0].toUpperCase()}
                </div>
                <div className="mf-driver-card-info">
                  <div className="mf-driver-card-name">
                    Cond. {shortId(selectedRoute.driver_id)}
                  </div>
                  <div className="mf-driver-card-role">Conductor</div>
                </div>
                <span className="badge ok">Activo</span>
              </div>
            )}

            {/* Primary actions */}
            {canManage && (
              <div className="mf-action-row">
                {(selectedRoute.status === "planned" ||
                  selectedRoute.status === "draft") && (
                  <button
                    className="mf-btn primary"
                    disabled={optimizingRouteId === selectedRoute.id}
                    onClick={() => onOptimizeRoute(selectedRoute.id)}
                  >
                    {optimizingRouteId === selectedRoute.id
                      ? "Optimizando..."
                      : "⚡ Optimizar"}
                  </button>
                )}
                {selectedRoute.status === "planned" && (
                  <button
                    className="mf-btn secondary"
                    disabled={dispatchingRouteId === selectedRoute.id}
                    onClick={() => onDispatchRoute(selectedRoute.id)}
                  >
                    {dispatchingRouteId === selectedRoute.id
                      ? "Despachando..."
                      : "📤 Despachar"}
                  </button>
                )}
              </div>
            )}

            {/* Stops list */}
            {routeDetailLoading ? (
              <div style={{ color: "#9ca3af", fontSize: 13 }}>Cargando paradas...</div>
            ) : (
              <div>
                {selectedRoute.stops
                  .slice()
                  .sort((a, b) => a.sequence_number - b.sequence_number)
                  .map((stop) => (
                    <div key={stop.id} className="mf-stop-row">
                      <div className={stopSeqClass(stop.status)}>
                        {stop.sequence_number}
                      </div>
                      <div className="mf-stop-body">
                        <div className="mf-stop-name">
                          Pedido {shortId(stop.order_id)}
                        </div>
                        <div className="mf-stop-meta">
                          {stop.status === "completed" && "✓ Entregado"}
                          {stop.status === "failed" && "✗ Fallo"}
                          {stop.status === "skipped" && "— Omitida"}
                          {stop.status === "arrived" && "📍 En destino"}
                          {stop.status === "en_route" && "🚚 En camino"}
                          {stop.status === "pending" && "⏳ Pendiente"}
                          {stop.estimated_arrival_at
                            ? ` · ETA ${stop.estimated_arrival_at.slice(11, 16)}`
                            : ""}
                        </div>
                      </div>
                    </div>
                  ))}
              </div>
            )}
          </div>
        )}

        {/* Unassigned orders section */}
        {canManage && readyOrders.length > 0 && (
          <>
            <div className="mf-divider" />
            <div className="mf-section">
              <div className="mf-section-head">
                <h3>Pedidos sin asignar</h3>
                <span className="mf-section-head-count mf-count-warn">{readyOrders.length}</span>
              </div>
              <div className="mf-orders-table-head">
                <span>Pedido</span>
                <span>Zona</span>
                <span>Estado</span>
              </div>
              {readyOrders.slice(0, 6).map((order) => (
                <div key={order.id} className="mf-orders-table-row">
                  <span className="mf-orders-id">{shortId(order.id)}</span>
                  <span className="mf-orders-zone">{order.zone_id || "—"}</span>
                  <span className="badge warn">Pendiente</span>
                </div>
              ))}
              {readyOrders.length > 6 && (
                <div style={{ color: "#9ca3af", fontSize: 12, padding: "6px 16px" }}>
                  +{readyOrders.length - 6} más
                </div>
              )}
            </div>
          </>
        )}

        {/* Advanced: plan creation + move stop — solo en vista Rutas */}
        {canManage && sidebarView === "rutas" && (
          <>
            <button
              className="mf-advanced-toggle"
              onClick={() => setAdvancedOpen((v) => !v)}
            >
              {advancedOpen ? "▲" : "▼"} Acciones avanzadas
            </button>

            {advancedOpen && (
              <div className="mf-advanced-body">
                {/* Plan creation */}
                <div style={{ fontWeight: 600, fontSize: 12, color: "#374151" }}>
                  Crear ruta
                </div>
                <div className="mf-form-row">
                  <span className="mf-form-label">Nombre del plan</span>
                  <input
                    className="mf-input"
                    placeholder="Ej: Ruta mañana Palma"
                    value={planId}
                    onChange={(e) => onPlanIdChange(e.target.value)}
                  />
                </div>
                <div className="mf-form-row">
                  <span className="mf-form-label">Vehículo</span>
                  <select
                    className="mf-input"
                    value={planVehicleId}
                    onChange={(e) => onPlanVehicleIdChange(e.target.value)}
                  >
                    <option value="">— Selecciona vehículo —</option>
                    {availableVehicles.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.name} · {v.code}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="mf-form-row">
                  <span className="mf-form-label">Conductor (opcional)</span>
                  <input
                    className="mf-input"
                    placeholder="Nombre o ID del conductor"
                    value={planDriverId}
                    onChange={(e) => onPlanDriverIdChange(e.target.value)}
                  />
                </div>
                <div className="mf-form-row">
                  <span className="mf-form-label">Pedidos a incluir</span>
                  <textarea
                    className="mf-input"
                    placeholder="Pega aquí los IDs de pedido separados por coma"
                    rows={3}
                    value={planOrderIds}
                    onChange={(e) => onPlanOrderIdsChange(e.target.value)}
                  />
                </div>
                <button
                  className="mf-btn primary"
                  disabled={creatingPlan || !planId || !planVehicleId}
                  onClick={onCreatePlan}
                  style={{ width: "100%" }}
                >
                  {creatingPlan ? "Creando..." : "Crear ruta"}
                </button>

                {/* Move stop */}
                {selectedRoute && (
                  <>
                    <div
                      style={{
                        fontWeight: 600,
                        fontSize: 12,
                        color: "#374151",
                        marginTop: 8,
                      }}
                    >
                      Mover parada
                    </div>
                    <div className="mf-form-row">
                      <span className="mf-form-label">Parada ID</span>
                      <select
                        className="mf-input"
                        value={moveStopId}
                        onChange={(e) => onMoveStopIdChange(e.target.value)}
                      >
                        <option value="">— Selecciona parada —</option>
                        {selectedRoute.stops.map((s) => (
                          <option key={s.id} value={s.id}>
                            #{s.sequence_number}{" "}
                            {shortId(s.order_id)}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="mf-form-row">
                      <span className="mf-form-label">Ruta destino</span>
                      <select
                        className="mf-input"
                        value={moveTargetRouteId}
                        onChange={(e) => onMoveTargetRouteIdChange(e.target.value)}
                      >
                        <option value="">— Selecciona ruta —</option>
                        {routes
                          .filter((r) => r.id !== selectedRouteId)
                          .map((r) => (
                            <option key={r.id} value={r.id}>
                              {r.vehicle_id
                                ? `Vehículo ${shortId(r.vehicle_id)}`
                                : shortId(r.id)}{" "}
                              · {routeStatusLabel(r.status)}
                            </option>
                          ))}
                      </select>
                    </div>
                    <button
                      className="mf-btn secondary"
                      disabled={movingStop || !moveStopId || !moveTargetRouteId}
                      onClick={onMoveStop}
                      style={{ width: "100%" }}
                    >
                      {movingStop ? "Moviendo..." : "Mover parada"}
                    </button>
                  </>
                )}
              </div>
            )}
          </>
        )}

        {/* ── CONDUCTORES — solo en modo Gestión ── */}
        {sidebarView === "gestion" && availableDrivers.length > 0 && (
          <div className="mf-section">
            <div
              className="mf-section-head mf-section-head-toggle"
              onClick={() => setDriverSectionOpen((v) => !v)}
            >
              <div>
                <h3 style={{ margin: 0 }}>Conductores</h3>
                {driverSectionOpen && (
                  <div style={{ fontSize: 10, color: "#9ca3af", marginTop: 1 }}>
                    Clic para asignar a la ruta
                  </div>
                )}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span className="mf-section-head-count">{availableDrivers.length}</span>
                <span className="mf-collapse-icon">{driverSectionOpen ? "▲" : "▼"}</span>
              </div>
            </div>
            {driverSectionOpen && (
              <div className="mf-fleet-list">
                {availableDrivers.map((d) => {
                  const isSelected = planDriverId === d.id;
                  return (
                    <div
                      key={d.id}
                      className={`mf-fleet-row clickable${isSelected ? " selected" : ""}`}
                      onClick={() => onPlanDriverIdChange(isSelected ? "" : d.id)}
                      title={isSelected ? "Clic para deseleccionar" : "Asignar a la ruta"}
                    >
                      <span className="mf-fleet-icon">👤</span>
                      <div className="mf-fleet-info">
                        <span className="mf-fleet-name">{d.name}</span>
                        <span className="mf-fleet-meta">{d.phone || "Sin teléfono"}</span>
                      </div>
                      {isSelected && (
                        <span className="badge ok" style={{ fontSize: 10 }}>Seleccionado</span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ── FLOTA: camiones y conductores ── */}
        {availableVehicles.length > 0 && (
          <div className="mf-section">
            <div
              className="mf-section-head mf-section-head-toggle"
              onClick={() => setFleetSectionOpen((v) => !v)}
            >
              <div>
                <h3 style={{ margin: 0 }}>Flota disponible</h3>
                {fleetSectionOpen && (
                  <div style={{ fontSize: 10, color: "#9ca3af", marginTop: 1 }}>
                    {sidebarView === "gestion" ? "Clic para asignar a la ruta" : "Clic para ver en mapa"}
                  </div>
                )}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span className="mf-section-head-count">{availableVehicles.length}</span>
                <span className="mf-collapse-icon">{fleetSectionOpen ? "▲" : "▼"}</span>
              </div>
            </div>
            {fleetSectionOpen && <div className="mf-fleet-list">
              {availableVehicles.map((v) => {
                const linkedRouteId = vehicleRouteMap[v.id];
                const isSelected = sidebarView === "gestion"
                  ? planVehicleId === v.id
                  : !!linkedRouteId && linkedRouteId === selectedRouteId;
                return (
                <div
                  key={v.id}
                  className={`mf-fleet-row clickable${isSelected ? " selected" : ""}`}
                  onClick={() => {
                    const toggling = isSelected || selectedFleetVehicleId === v.id;
                    if (sidebarView === "gestion") {
                      // En modo Gestión: rellenar selector del formulario
                      // Y también seleccionar la ruta vinculada para que el mapa la refleje
                      if (planVehicleId === v.id) {
                        onPlanVehicleIdChange("");
                        if (linkedRouteId) onSelectedRouteIdChange("");
                      } else {
                        onPlanVehicleIdChange(v.id);
                        if (linkedRouteId) onSelectedRouteIdChange(linkedRouteId);
                      }
                    } else {
                      // En modo Rutas: mostrar ruta/vehículo en el mapa
                      if (toggling) {
                        setSelectedFleetVehicleId(null);
                        setSelectedFleetVehicleName(null);
                        if (linkedRouteId) onSelectedRouteIdChange("");
                      } else {
                        setSelectedFleetVehicleId(v.id);
                        setSelectedFleetVehicleName(v.name);
                        if (linkedRouteId) onSelectedRouteIdChange(linkedRouteId);
                      }
                    }
                  }}
                  title={sidebarView === "gestion" ? "Seleccionar para crear ruta" : linkedRouteId ? "Ver ruta en mapa" : "Ver vehículo en mapa"}
                >
                  <span className="mf-fleet-icon">🚚</span>
                  <div className="mf-fleet-info">
                    <span className="mf-fleet-name">{v.name}</span>
                    <span className="mf-fleet-meta">{v.code}{v.capacity_kg ? ` · ${v.capacity_kg} kg` : ""}</span>
                  </div>
                  {v.driver && activeDriverIdSet.has(v.driver.id) && (
                    <span title="GPS activo" style={{ fontSize: 14, lineHeight: 1 }}>📍</span>
                  )}
                  {v.driver ? (
                    <div className="mf-fleet-driver">
                      <span className="mf-fleet-driver-avatar">{v.driver.name[0].toUpperCase()}</span>
                      <div className="mf-fleet-driver-info">
                        <span className="mf-fleet-driver-name">{v.driver.name}</span>
                        {v.driver.phone && <span className="mf-fleet-driver-phone">{v.driver.phone}</span>}
                      </div>
                    </div>
                  ) : (
                    <span className="mf-fleet-no-driver">Sin conductor</span>
                  )}
                </div>
                );
              })}
            </div>}
          </div>
        )}
      </div>
    </div>
  );
}
