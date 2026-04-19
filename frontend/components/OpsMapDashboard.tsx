"use client";

import React, { useState, useEffect } from "react";
import type {
  AvailableVehicleItem,
  DashboardSummary,
  DelayAlertOut,
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
import { ChatFloating } from "./ChatFloating";

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
  token?: string;
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
  delayAlerts?: DelayAlertOut[];
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

function StopExpandContent({ stop }: { stop: { estimated_service_minutes: number; failure_reason: string | null; arrived_at: string | null; completed_at: string | null; customer_lat: number | null; customer_lng: number | null } }) {
  const items: React.ReactNode[] = [];
  if (stop.estimated_service_minutes > 0)
    items.push(<span key="svc">⏱ {stop.estimated_service_minutes} min de servicio estimado</span>);
  if (stop.arrived_at)
    items.push(<span key="arr">📍 Llegada registrada {stop.arrived_at.slice(11, 16)}</span>);
  if (stop.completed_at)
    items.push(<span key="cmp" style={{ color: "#16a34a" }}>✓ Entregado a las {stop.completed_at.slice(11, 16)}</span>);
  if (stop.failure_reason)
    items.push(<span key="fail" style={{ color: "#dc2626" }}>✗ {stop.failure_reason}</span>);
  if (stop.customer_lat && stop.customer_lng)
    items.push(<span key="geo" style={{ color: "#6b7280" }}>🗺 {stop.customer_lat.toFixed(4)}, {stop.customer_lng.toFixed(4)}</span>);
  if (items.length === 0)
    items.push(<span key="none" style={{ color: "#9ca3af" }}>Sin actividad registrada aún</span>);
  return (
    <div className="mf-stop-expand">
      {items.map((item, i) => <div key={i} className="mf-stop-expand-row">{item}</div>)}
    </div>
  );
}

const TruckSvg = () => (
  <svg width="20" height="16" viewBox="0 0 32 22" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ display: "block" }}>
    <rect x="0" y="3" width="20" height="14" rx="2" fill="#2563eb"/>
    <rect x="1.5" y="4.5" width="7" height="5" rx="1" fill="#bfdbfe"/>
    <path d="M20 7h6.5L30 12.5V18H20V7z" fill="#1d4ed8"/>
    <rect x="20.5" y="8" width="5" height="4" rx="0.5" fill="#bfdbfe"/>
    <circle cx="6.5" cy="19" r="3" fill="#0f172a"/>
    <circle cx="6.5" cy="19" r="1.2" fill="#cbd5e1"/>
    <circle cx="24" cy="19" r="3" fill="#0f172a"/>
    <circle cx="24" cy="19" r="1.2" fill="#cbd5e1"/>
  </svg>
);

const DriverAvatarSm = ({ name, selected }: { name: string; selected?: boolean }) => {
  const colors = ["#2563eb","#7c3aed","#059669","#d97706","#dc2626","#0891b2"];
  const idx = (name.charCodeAt(0) || 0) % colors.length;
  return (
    <span className="mf-driver-avatar-sm" style={{ background: selected ? "#1d4ed8" : colors[idx] }}>
      {name[0]?.toUpperCase() ?? "?"}
    </span>
  );
};

// ─── NextActionCard ───────────────────────────────────────────────────────────

function NextActionCard({
  unassigned,
  activeRoutes,
  routes,
  onGoToGestion,
  onSelectFirstPlanned,
}: {
  unassigned: number;
  activeRoutes: number;
  routes: RoutingRoute[];
  onGoToGestion: () => void;
  onSelectFirstPlanned: (id: string) => void;
}) {
  const plannedOrDraftRoutes = routes.filter(
    (r) => r.status === "planned" || r.status === "draft",
  );
  const plannedOrDraft = plannedOrDraftRoutes.length;

  if (unassigned > 0 && routes.length === 0) {
    return (
      <div className="mf-next-action mf-next-action-warn" onClick={onGoToGestion} style={{ cursor: "pointer" }}>
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
      <div
        className="mf-next-action mf-next-action-blue"
        style={{ cursor: "pointer" }}
        onClick={() => plannedOrDraftRoutes[0] && onSelectFirstPlanned(plannedOrDraftRoutes[0].id)}
      >
        <div className="mf-next-action-icon">⚡</div>
        <div className="mf-next-action-body">
          <div className="mf-next-action-title">
            {plannedOrDraft} ruta{plannedOrDraft !== 1 ? "s" : ""} lista{plannedOrDraft !== 1 ? "s" : ""} para operar
          </div>
          <div className="mf-next-action-sub">
            Toca para seleccionar · optimiza · despacha al conductor
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
  token,
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
  delayAlerts = [],
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
  // Monitor mode
  const [drawerRouteId, setDrawerRouteId] = useState<string | null>(null);
  const [showFullPanel, setShowFullPanel] = useState(false);
  const [expandedStopId, setExpandedStopId] = useState<string | null>(null);

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

  // Monitor mode — auto-entra cuando hay rutas activas en vista Rutas
  const activeRoutesList = React.useMemo(
    () => routes.filter((r) => r.status === "in_progress" || r.status === "dispatched"),
    [routes],
  );
  const monitorMode = sidebarView === "rutas" && activeRoutesList.length > 0 && !showFullPanel;
  const drawerOpen = drawerRouteId !== null;
  // drawerRoute usa selectedRoute (ya cargado por el padre) cuando coincide
  const drawerRoute = drawerRouteId === selectedRouteId ? selectedRoute : null;

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

  // Delay alerts del selectedRouteId — para mostrar en chip y drawer
  const delayAlertCount = delayAlerts.length;

  const emailDisplay = role ? `Rol: ${role}` : "—";

  // ── render ──────────────────────────────────────────────────────────────────
  return (
    <div className={`map-first-shell${monitorMode ? " monitor-mode" : ""}`}>
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
            {activeRoutesList.length > 0 && (
              <button
                className={`mf-filter-pill${!showFullPanel ? " mf-monitor-toggle-active" : ""}`}
                onClick={() => setShowFullPanel((v) => !v)}
                title={showFullPanel ? "Cambiar a modo monitoreo (mapa completo)" : "Mostrar panel lateral completo"}
              >
                {showFullPanel ? "🗺 Monitoreo" : "📊 Panel"}
              </button>
            )}
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
            driverNameMap={driverNameMap}
          />
          {/* Monitor mode — chips de rutas activas flotando en la parte inferior */}
          {monitorMode && (
            <div className="mf-monitor-chips">
              {activeRoutesList.map((r) => {
                const vName = r.vehicle_id
                  ? (vehicleNameMap[r.vehicle_id] ?? shortId(r.vehicle_id))
                  : shortId(r.id);
                const dName = r.driver_id
                  ? (driverNameMap[r.driver_id] ?? null)
                  : null;
                const isChipActive = drawerRouteId === r.id;
                const hasGps = !!r.driver_id && activeDriverIdSet.has(r.driver_id);
                return (
                  <button
                    key={r.id}
                    className={`mf-monitor-chip${isChipActive ? " active" : ""}`}
                    onClick={() => {
                      if (isChipActive) {
                        setDrawerRouteId(null);
                      } else {
                        setDrawerRouteId(r.id);
                        onSelectedRouteIdChange(r.id);
                      }
                    }}
                  >
                    <span className={`mf-chip-status-dot ${r.status}`} />
                    <span>🚚 {vName}</span>
                    {dName && (
                      <span className="mf-chip-driver">
                        · {dName.split(" ")[0]}
                      </span>
                    )}
                    <span className="mf-chip-stops">{r.stops.length} par.</span>
                    {hasGps && <span title="GPS activo">📍</span>}
                    {isChipActive && delayAlertCount > 0 && (
                      <span className="mf-chip-delay-badge" title={`${delayAlertCount} alerta(s) de retraso`}>
                        ⚠️ {delayAlertCount}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          )}

          {/* Empty state overlay — solo en modo normal sin rutas activas */}
          {!selectedRoute && !monitorMode && !showFullPanel && (
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

      {/* ── DRAWER — modo monitoreo, desliza sobre el mapa desde la derecha ── */}
      {monitorMode && (
        <div className={`mf-route-drawer${drawerOpen ? " open" : ""}`}>
          <div className="mf-drawer-header">
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="mf-drawer-title">
                {drawerRoute?.vehicle_id
                  ? (vehicleNameMap[drawerRoute.vehicle_id] ?? shortId(drawerRoute.vehicle_id))
                  : drawerRouteId
                  ? shortId(drawerRouteId)
                  : "Ruta"}
              </div>
              {drawerRoute && (
                <span className={routeStatusBadgeClass(drawerRoute.status)} style={{ fontSize: 11 }}>
                  {routeStatusLabel(drawerRoute.status)}
                </span>
              )}
            </div>
            <button
              className="mf-drawer-close"
              onClick={() => setDrawerRouteId(null)}
              title="Cerrar"
            >×</button>
          </div>

          <div className="mf-drawer-body">
            {routeDetailLoading && (
              <div style={{ color: "#9ca3af", fontSize: 13, padding: "20px 0" }}>
                Cargando ruta...
              </div>
            )}
            {!routeDetailLoading && drawerRoute && (
              <>
                {/* Conductor */}
                {drawerRoute.driver_id && (
                  <div className="mf-driver-card" style={{ marginBottom: 14 }}>
                    <div className="mf-driver-avatar-lg">
                      {(driverNameMap[drawerRoute.driver_id] ?? shortId(drawerRoute.driver_id))[0].toUpperCase()}
                    </div>
                    <div className="mf-driver-card-info">
                      <div className="mf-driver-card-name">
                        {driverNameMap[drawerRoute.driver_id] ?? shortId(drawerRoute.driver_id)}
                      </div>
                      <div className="mf-driver-card-role">Conductor</div>
                    </div>
                    {activeDriverIdSet.has(drawerRoute.driver_id) && (
                      <span title="GPS activo" style={{ fontSize: 16 }}>📍</span>
                    )}
                  </div>
                )}

                {/* Stats */}
                <div className="mf-drawer-stats">
                  <div className="mf-drawer-stat">
                    <span className="mf-drawer-stat-value">{drawerRoute.stops.length}</span>
                    <span className="mf-drawer-stat-label">Paradas</span>
                  </div>
                  <div className="mf-drawer-stat">
                    <span className="mf-drawer-stat-value" style={{ color: "#16a34a" }}>
                      {drawerRoute.stops.filter((s) => s.status === "completed").length}
                    </span>
                    <span className="mf-drawer-stat-label">Entregadas</span>
                  </div>
                  <div className="mf-drawer-stat">
                    <span className="mf-drawer-stat-value" style={{ color: "#dc2626" }}>
                      {drawerRoute.stops.filter((s) => s.status === "failed").length}
                    </span>
                    <span className="mf-drawer-stat-label">Fallidas</span>
                  </div>
                  <div className="mf-drawer-stat">
                    <span className="mf-drawer-stat-value" style={{ color: "#f59e0b" }}>
                      {drawerRoute.stops.filter((s) => s.status === "pending" || s.status === "en_route").length}
                    </span>
                    <span className="mf-drawer-stat-label">Pendientes</span>
                  </div>
                </div>

                {/* Delay alerts — B2 (ETA-001) */}
                {delayAlertCount > 0 && (
                  <div className="mf-delay-alerts-section">
                    <div className="mf-drawer-section-label" style={{ color: "#b45309" }}>
                      ⚠️ Alertas de retraso ({delayAlertCount})
                    </div>
                    {delayAlerts.slice(0, 5).map((a) => (
                      <div key={a.event_id} className="mf-delay-alert-row">
                        <span className="mf-delay-alert-min">
                          +{a.delay_minutes != null ? Math.round(a.delay_minutes) : "?"} min
                        </span>
                        <span className="mf-delay-alert-ts">
                          {a.ts.slice(11, 16)}
                        </span>
                        {a.recalculated_eta && (
                          <span className="mf-delay-alert-eta">
                            ETA {a.recalculated_eta.slice(11, 16)}
                          </span>
                        )}
                      </div>
                    ))}
                    {delayAlertCount > 5 && (
                      <div style={{ fontSize: 11, color: "#9ca3af", padding: "2px 0 6px" }}>
                        +{delayAlertCount - 5} más
                      </div>
                    )}
                  </div>
                )}

                {/* Acciones */}
                {canManage && (drawerRoute.status === "planned" || drawerRoute.status === "draft") && (
                  <div className="mf-action-row" style={{ marginBottom: 14 }}>
                    <button
                      className="mf-btn primary"
                      disabled={optimizingRouteId === drawerRoute.id}
                      onClick={() => onOptimizeRoute(drawerRoute.id)}
                    >
                      {optimizingRouteId === drawerRoute.id ? "Optimizando..." : "⚡ Optimizar"}
                    </button>
                    {drawerRoute.status === "planned" && (
                      <button
                        className="mf-btn secondary"
                        disabled={dispatchingRouteId === drawerRoute.id}
                        onClick={() => onDispatchRoute(drawerRoute.id)}
                      >
                        {dispatchingRouteId === drawerRoute.id ? "Despachando..." : "📤 Despachar"}
                      </button>
                    )}
                  </div>
                )}

                {/* Lista de paradas */}
                <div className="mf-drawer-section-label">Paradas</div>
                {drawerRoute.stops
                  .slice()
                  .sort((a, b) => a.sequence_number - b.sequence_number)
                  .map((stop) => {
                    const isExp = expandedStopId === stop.id;
                    return (
                      <div
                        key={stop.id}
                        className={`mf-stop-row${isExp ? " expanded" : ""}`}
                        style={{ display: "block", cursor: "pointer" }}
                        onClick={() => setExpandedStopId(isExp ? null : stop.id)}
                      >
                        <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                          <div className={stopSeqClass(stop.status)}>{stop.sequence_number}</div>
                          <div className="mf-stop-body">
                            <div className="mf-stop-name">Pedido {shortId(stop.order_id)}</div>
                            <div className="mf-stop-meta">
                              {stop.status === "completed" && "✓ Entregado"}
                              {stop.status === "failed" && "✗ Fallo"}
                              {stop.status === "skipped" && "— Omitida"}
                              {stop.status === "arrived" && "📍 En destino"}
                              {stop.status === "en_route" && "🚛 En camino"}
                              {stop.status === "pending" && "⏳ Pendiente"}
                              {stop.estimated_arrival_at
                                ? ` · ETA ${stop.estimated_arrival_at.slice(11, 16)}`
                                : ""}
                            </div>
                          </div>
                          <span className="mf-stop-chevron">{isExp ? "▲" : "▾"}</span>
                        </div>
                        {isExp && <StopExpandContent stop={stop} />}
                      </div>
                    );
                  })}
              </>
            )}
            {!routeDetailLoading && !drawerRoute && drawerRouteId && (
              <div style={{ color: "#9ca3af", fontSize: 13 }}>
                Cargando detalle de ruta...
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── RIGHT PANEL — oculto en monitor mode ── */}
      {!monitorMode && <div className="mf-right-panel">
        {/* Error banner */}
        {error && <div className="mf-error-banner">⚠️ {error}</div>}

        {/* KPIs */}
        <div className="mf-kpi-grid">
          <div
            className="mf-kpi-card mf-kpi-blue clickable"
            title="Ver todas las rutas de hoy"
            onClick={() => { onRouteStatusChange("all"); setSidebarView("rutas"); }}
          >
            <span className="mf-kpi-icon">📋</span>
            <div className="mf-kpi-data">
              <span className="mf-kpi-value">{totalRoutes}</span>
              <span className="mf-kpi-label">Rutas hoy</span>
            </div>
          </div>
          <div
            className="mf-kpi-card mf-kpi-orange clickable"
            title="Ver rutas en curso"
            onClick={() => { onRouteStatusChange("in_progress"); setSidebarView("rutas"); }}
          >
            <span className="mf-kpi-icon">🚚</span>
            <div className="mf-kpi-data">
              <span className="mf-kpi-value">{activeRoutes}</span>
              <span className="mf-kpi-label">En curso</span>
            </div>
          </div>
          <div
            className="mf-kpi-card mf-kpi-green clickable"
            title="Ver rutas completadas"
            onClick={() => { onRouteStatusChange("completed"); setSidebarView("rutas"); }}
          >
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
          onSelectFirstPlanned={(id) => {
            setSidebarView("rutas");
            onSelectedRouteIdChange(id);
          }}
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
                  {(driverNameMap[selectedRoute.driver_id] ?? shortId(selectedRoute.driver_id))[0].toUpperCase()}
                </div>
                <div className="mf-driver-card-info">
                  <div className="mf-driver-card-name">
                    {driverNameMap[selectedRoute.driver_id] ?? shortId(selectedRoute.driver_id)}
                  </div>
                  <div className="mf-driver-card-role">Conductor</div>
                </div>
                <span className="badge ok">Activo</span>
              </div>
            )}

            {/* Delay alerts — panel derecho */}
            {delayAlertCount > 0 && (
              <div className="mf-delay-alerts-section" style={{ marginBottom: 10 }}>
                <div style={{ fontWeight: 600, fontSize: 12, color: "#b45309", marginBottom: 4 }}>
                  ⚠️ {delayAlertCount} alerta{delayAlertCount !== 1 ? "s" : ""} de retraso
                </div>
                {delayAlerts.slice(0, 3).map((a) => (
                  <div key={a.event_id} className="mf-delay-alert-row">
                    <span className="mf-delay-alert-min">
                      +{a.delay_minutes != null ? Math.round(a.delay_minutes) : "?"} min
                    </span>
                    <span className="mf-delay-alert-ts">{a.ts.slice(11, 16)}</span>
                    {a.recalculated_eta && (
                      <span className="mf-delay-alert-eta">ETA {a.recalculated_eta.slice(11, 16)}</span>
                    )}
                  </div>
                ))}
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
                  .map((stop) => {
                    const isExp = expandedStopId === stop.id;
                    return (
                      <div
                        key={stop.id}
                        className={`mf-stop-row${isExp ? " expanded" : ""}`}
                        style={{ display: "block", cursor: "pointer" }}
                        onClick={() => setExpandedStopId(isExp ? null : stop.id)}
                      >
                        <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
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
                              {stop.status === "en_route" && "🚛 En camino"}
                              {stop.status === "pending" && "⏳ Pendiente"}
                              {stop.estimated_arrival_at
                                ? ` · ETA ${stop.estimated_arrival_at.slice(11, 16)}`
                                : ""}
                            </div>
                          </div>
                          <span className="mf-stop-chevron">{isExp ? "▲" : "▾"}</span>
                        </div>
                        {isExp && <StopExpandContent stop={stop} />}
                      </div>
                    );
                  })}
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
                {/* Move stop — única acción avanzada en vista Rutas */}
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
                      <DriverAvatarSm name={d.name} selected={isSelected} />
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
                    if (sidebarView === "gestion") {
                      // Gestión: toggle selección para el formulario
                      if (planVehicleId === v.id) {
                        onPlanVehicleIdChange("");
                        if (linkedRouteId) onSelectedRouteIdChange("");
                      } else {
                        onPlanVehicleIdChange(v.id);
                        if (linkedRouteId) onSelectedRouteIdChange(linkedRouteId);
                      }
                    } else {
                      // Rutas: siempre navegar a la ruta vinculada (sin toggle confuso)
                      setSelectedFleetVehicleId(v.id);
                      setSelectedFleetVehicleName(v.name);
                      if (linkedRouteId) onSelectedRouteIdChange(linkedRouteId);
                    }
                  }}
                  title={sidebarView === "gestion" ? "Seleccionar para crear ruta" : linkedRouteId ? "Ver ruta en mapa" : "Ver vehículo en mapa"}
                >
                  <span className="mf-fleet-icon mf-vehicle-icon"><TruckSvg /></span>
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
      </div>}

      {/* Floating chat — visible whenever there are active routes */}
      {activeRoutesList.length > 0 && token && (
        <ChatFloating
          token={token}
          activeRoutes={activeRoutesList}
          vehicleNameMap={vehicleNameMap}
          driverNameMap={driverNameMap}
        />
      )}
    </div>
  );
}
