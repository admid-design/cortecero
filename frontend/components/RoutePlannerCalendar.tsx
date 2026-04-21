"use client";

/**
 * ROUTE-PLANNER-CAL-001 v3
 * Layout exacto del prototipo R10-route-planner-prototype.html
 * - Header con tabs (Gestión | Planificador | Seguimiento | Monitor)
 * - Sidebar 230px: pedidos por asignar
 * - KPI strip: rutas hoy, paradas, semana, sin asignar
 * - Map section (flex:1): mapa Mallorca con leyenda de rutas activas
 * - Timeline header + body (height:210px): gantt por ruta
 * - Drawer slide-in (position:absolute): tabla de paradas + edición ETA inline
 * - Toggle Vista día / Vista semana para ver calendario semanal
 */

import { useState, useEffect, useCallback } from "react";
import {
  listRoutes,
  listReadyToDispatchOrders,
  includeOrderInPlan,
  patchStopScheduledArrival,
  type RoutingRoute,
  type RoutingRouteStop,
  type ReadyToDispatchItem,
} from "../lib/api";
import { RouteMapCard } from "./RouteMapCard";

// ── constants ────────────────────────────────────────────────────────────────

const DAY_LABELS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

const GANTT_HOURS = [
  "07:00","08:00","09:00","10:00","11:00","12:00","13:00","14:00","15:00","16:00",
];

const ROUTE_COLORS = [
  "#2563eb","#7c3aed","#059669","#d97706","#dc2626","#0891b2","#be185d","#b45309",
];

const STATUS_CSS: Record<string, string> = {
  in_progress: "rpc-st-ip",
  dispatched:  "rpc-st-di",
  planned:     "rpc-st-pl",
  completed:   "rpc-st-co",
  draft:       "rpc-st-dr",
  cancelled:   "rpc-st-co",
};

const STATUS_LABEL: Record<string, string> = {
  draft:       "Borrador",
  planned:     "Planificada",
  dispatched:  "Despachada",
  in_progress: "En ruta",
  completed:   "Completada",
  cancelled:   "Cancelada",
};

const STOP_COLOR: Record<string, string> = {
  pending:   "#9ca3af",
  en_route:  "#2563eb",
  arrived:   "#d97706",
  completed: "#16a34a",
  failed:    "#dc2626",
  skipped:   "#9ca3af",
};

const STOP_LABEL: Record<string, string> = {
  pending:   "Pendiente",
  en_route:  "En camino",
  arrived:   "Llegó",
  completed: "Completada",
  failed:    "Fallida",
  skipped:   "Omitida",
};

// ── helpers ──────────────────────────────────────────────────────────────────

function getWeekDays(anchor: Date): Date[] {
  const day = anchor.getDay();
  const monday = new Date(anchor);
  monday.setDate(anchor.getDate() - ((day + 6) % 7));
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    return d;
  });
}

function toIso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function isoToHHMM(iso: string | null): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  } catch {
    return "";
  }
}

function hhmmToIso(hhmm: string, serviceDate: string): string {
  return new Date(`${serviceDate}T${hhmm}:00`).toISOString();
}

function stopPctFromHHMM(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return (((h ?? 7) - 7) * 60 + (m ?? 0)) / (9 * 60) * 100;
}

function ganttPct(eta: string | null): number | null {
  const hhmm = isoToHHMM(eta);
  if (!hhmm) return null;
  return Math.max(0, Math.min(100, stopPctFromHHMM(hhmm)));
}

function canEditRoute(r: RoutingRoute): boolean {
  return ["draft", "planned", "dispatched"].includes(r.status);
}

// ── component ────────────────────────────────────────────────────────────────

type Props = { token: string; onBack?: () => void; onNewRoute?: () => void };
type Toast = { kind: "ok" | "err"; msg: string };
type ViewType = "dia" | "semana";

export function RoutePlannerCalendar({ token, onBack, onNewRoute }: Props) {
  const [weekAnchor, setWeekAnchor]     = useState<Date>(() => new Date());
  const [viewType, setViewType]         = useState<ViewType>("dia");
  const [activeDayIso, setActiveDayIso] = useState<string>(() => new Date().toISOString().slice(0, 10));

  const [routes, setRoutes]           = useState<RoutingRoute[]>([]);
  const [readyOrders, setReadyOrders] = useState<ReadyToDispatchItem[]>([]);
  const [loading, setLoading]         = useState(false);

  const [selectedOrderId, setSelectedOrderId]   = useState<string | null>(null);
  const [assigningRouteId, setAssigningRouteId] = useState<string | null>(null);
  const [search, setSearch]                     = useState("");

  const [drawerRoute, setDrawerRoute]   = useState<RoutingRoute | null>(null);
  const [activeRouteId, setActiveRouteId] = useState<string | null>(null);
  const [editingStopId, setEditingStopId] = useState<string | null>(null);
  const [editingEta, setEditingEta]       = useState("");
  const [savingStopId, setSavingStopId]   = useState<string | null>(null);

  const [toast, setToast] = useState<Toast | null>(null);

  const weekDays  = getWeekDays(weekAnchor);
  const todayIso  = new Date().toISOString().slice(0, 10);

  // ── data loading ───────────────────────────────────────────────────────────

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [routesRes, ordersRes] = await Promise.all([
        listRoutes(token),
        listReadyToDispatchOrders(token),
      ]);
      setRoutes(routesRes.items);
      setReadyOrders(ordersRes.items ?? []);
    } catch (e: unknown) {
      showToast("err", e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { void loadData(); }, [loadData]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  useEffect(() => {
    if (!drawerRoute) return;
    const updated = routes.find((r) => r.id === drawerRoute.id);
    if (updated) setDrawerRoute(updated);
  }, [routes]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── helpers ────────────────────────────────────────────────────────────────

  function showToast(kind: "ok" | "err", msg: string) { setToast({ kind, msg }); }

  // Derived data
  const routesByDay: Record<string, RoutingRoute[]> = {};
  for (const d of weekDays) {
    const iso = toIso(d);
    routesByDay[iso] = routes.filter((r) => r.service_date === iso);
  }
  const weekRoutes    = weekDays.flatMap((d) => routesByDay[toIso(d)] ?? []);
  const totalStops    = weekRoutes.reduce((n, r) => n + r.stops.length, 0);
  const activeDayRoutes = routes.filter((r) => r.service_date === activeDayIso);

  const filteredOrders = search.trim()
    ? readyOrders.filter(
        (o) => o.id.toLowerCase().includes(search.toLowerCase()) || o.service_date.includes(search),
      )
    : readyOrders;

  const selectedOrder = readyOrders.find((o) => o.id === selectedOrderId);

  const activeDayDate  = weekDays.find((d) => toIso(d) === activeDayIso) ?? new Date(activeDayIso);
  const activeDayLabel = activeDayDate.toLocaleDateString("es-ES", { weekday: "long", day: "numeric", month: "long" });
  const weekLabel = `${weekDays[0]!.toLocaleDateString("es-ES", { day: "2-digit", month: "short" })} — ${weekDays[6]!.toLocaleDateString("es-ES", { day: "2-digit", month: "short", year: "numeric" })}`;

  // ── actions ────────────────────────────────────────────────────────────────

  function toggleOrder(id: string) { setSelectedOrderId((prev) => (prev === id ? null : id)); }

  async function assignToRoute(route: RoutingRoute) {
    if (!selectedOrderId) return;
    setAssigningRouteId(route.id);
    try {
      await includeOrderInPlan(token, route.plan_id ?? "", selectedOrderId);
      showToast("ok", "Pedido incluido en el plan");
      setSelectedOrderId(null);
      void loadData();
    } catch (e: unknown) {
      showToast("err", e instanceof Error ? e.message : String(e));
    } finally { setAssigningRouteId(null); }
  }

  function startEditEta(stop: RoutingRouteStop) {
    setEditingStopId(stop.id);
    setEditingEta(isoToHHMM(stop.estimated_arrival_at));
  }

  async function saveEta(stop: RoutingRouteStop, serviceDate: string) {
    if (!editingEta) { setEditingStopId(null); return; }
    setSavingStopId(stop.id);
    try {
      await patchStopScheduledArrival(token, stop.id, hhmmToIso(editingEta, serviceDate));
      showToast("ok", `Hora prevista actualizada: ${editingEta}`);
      setEditingStopId(null);
      void loadData();
    } catch (e: unknown) {
      showToast("err", e instanceof Error ? e.message : String(e));
    } finally { setSavingStopId(null); }
  }

  function openDrawer(r: RoutingRoute) { setActiveRouteId(r.id); setDrawerRoute(r); }
  function closeDrawer() { setDrawerRoute(null); setActiveRouteId(null); setEditingStopId(null); }

  function prevWeek() { setWeekAnchor((d) => { const n = new Date(d); n.setDate(d.getDate() - 7); return n; }); }
  function nextWeek() { setWeekAnchor((d) => { const n = new Date(d); n.setDate(d.getDate() + 7); return n; }); }

  // ── render ─────────────────────────────────────────────────────────────────

  return (
    <div className="rpc-root">

      {/* ── HEADER ── */}
      <div className="rpc-hdr">
        <div className="rpc-hdr-left">
          <span className="rpc-hdr-title">Planificador</span>
          <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <button className="rpc-wbtn" onClick={prevWeek}>‹</button>
            <span className="rpc-wlabel">{weekLabel}</span>
            <button className="rpc-wbtn" onClick={nextWeek}>›</button>
            <button className="rpc-wbtn" onClick={() => setWeekAnchor(new Date())}>Hoy</button>
          </div>
        </div>
        <div className="rpc-hdr-right">
          <select
            className="rpc-select"
            value={viewType}
            onChange={(e) => setViewType(e.target.value as ViewType)}
          >
            <option value="dia">Vista día</option>
            <option value="semana">Vista semana</option>
          </select>
          <button className="rpc-btn-o" onClick={() => void loadData()} disabled={loading}>
            {loading ? "Cargando…" : "↻ Actualizar"}
          </button>
          <button className="rpc-btn-p" onClick={onNewRoute}>+ Nueva ruta</button>
        </div>
      </div>

      {/* ── BODY ── */}
      <div className="rpc-body">

        {/* ── SIDEBAR ── */}
        <aside className="rpc-sidebar">
          <div className="rpc-sb-hdr">
            <div className="rpc-sb-title">
              Pedidos por asignar
              <span className="rpc-sb-count">{filteredOrders.length}</span>
            </div>
            <input
              className="rpc-sb-search"
              type="text"
              placeholder="Buscar pedido..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="rpc-sb-list">
            {!selectedOrder && (
              <div className="rpc-hint-text">
                Selecciona un pedido y haz click en una ruta para asignarlo
              </div>
            )}
            {filteredOrders.map((o) => {
              const isSel = selectedOrderId === o.id;
              return (
                <div
                  key={o.id}
                  className={`rpc-pcard${isSel ? " rpc-pcard-sel" : ""}`}
                  onClick={() => toggleOrder(o.id)}
                >
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <div className="rpc-pref">#{o.id.slice(0, 8).toUpperCase()}</div>
                    <span className="rpc-pbadge rpc-pbadge-ok">Normal</span>
                  </div>
                  <div className="rpc-pcli">{o.service_date}</div>
                  <div className="rpc-pmeta">
                    <span>📅 {o.service_date}</span>
                    {o.total_weight_kg != null && <span>{o.total_weight_kg} kg</span>}
                  </div>
                </div>
              );
            })}
            {filteredOrders.length === 0 && !loading && (
              <div className="rpc-hint-text" style={{ fontStyle: "normal" }}>
                {search ? "Sin resultados" : "Sin pedidos pendientes"}
              </div>
            )}
          </div>
        </aside>

        {/* ── PLANNER ── */}
        <div className="rpc-planner">

          {/* KPI strip */}
          <div className="rpc-kpi-strip">
            <div className="rpc-kpi">
              <div className="rpc-kpi-lbl">Rutas hoy</div>
              <div className="rpc-kpi-val">{activeDayRoutes.length}</div>
              <div className="rpc-kpi-sub">
                {activeDayRoutes.filter((r) => r.status === "in_progress").length} activas
                {" · "}
                {activeDayRoutes.filter((r) => r.status === "completed").length} completadas
              </div>
            </div>
            <div className="rpc-kpi">
              <div className="rpc-kpi-lbl">Paradas</div>
              <div className="rpc-kpi-val">{activeDayRoutes.reduce((n, r) => n + r.stops.length, 0)}</div>
              <div className="rpc-kpi-sub">
                {activeDayRoutes.reduce((n, r) => n + r.stops.filter((s) => s.status === "completed").length, 0)} comp
                {" · "}
                {activeDayRoutes.reduce((n, r) => n + r.stops.filter((s) => s.status === "pending").length, 0)} pend
              </div>
            </div>
            <div className="rpc-kpi">
              <div className="rpc-kpi-lbl">Esta semana</div>
              <div className="rpc-kpi-val">{weekRoutes.length}</div>
              <div className="rpc-kpi-sub">{totalStops} paradas</div>
            </div>
            <div className="rpc-kpi">
              <div className="rpc-kpi-lbl">Sin asignar</div>
              <div className="rpc-kpi-val" style={{ color: "#d97706" }}>{readyOrders.length}</div>
              <div className="rpc-kpi-sub">pedidos</div>
            </div>
            {toast && (
              <div
                className={`rpc-kpi-toast rpc-toast-${toast.kind}`}
                onClick={() => setToast(null)}
              >
                {toast.kind === "ok" ? "✓" : "⚠"} {toast.msg}
              </div>
            )}
          </div>

          {/* ── MAP SECTION (día) / CALENDAR (semana) ── */}
          {viewType === "dia" ? (
            <div className="rpc-map-section">
              {/* Mapa Google Maps real — muestra la ruta seleccionada en el gantt */}
              <RouteMapCard route={drawerRoute} />

              <div className="rpc-live-badge">
                <div className="rpc-live-dot" />
                <span>EN VIVO · {new Date().toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}</span>
              </div>

              {selectedOrder && (
                <div className="rpc-map-alert">
                  📦 Asignando #{selectedOrder.id.slice(0, 8).toUpperCase()} — haz click en una ruta del gantt
                </div>
              )}

              {!drawerRoute && (
                <div className="rpc-map-hint">
                  Haz click en una ruta del gantt para verla en el mapa
                </div>
              )}
            </div>
          ) : (
            /* ── WEEK CALENDAR ── */
            <div className="rpc-cal-section">
              <div className="rpc-cal-grid">
                {weekDays.map((day, i) => {
                  const iso       = toIso(day);
                  const dayRoutes = routesByDay[iso] ?? [];
                  const isToday   = iso === todayIso;
                  const isActive  = iso === activeDayIso;
                  return (
                    <div key={iso} className={`rpc-ccol${isToday ? " rpc-ccol-today" : ""}`}>
                      <div
                        className={`rpc-ccol-hdr${isActive ? " rpc-ccol-hdr-active" : ""}`}
                        onClick={() => { setActiveDayIso(iso); setViewType("dia"); }}
                      >
                        <span className="rpc-cday-name">{DAY_LABELS[i]}</span>
                        <span className={`rpc-cday-num${isToday ? " rpc-cday-num-today" : ""}`}>{day.getDate()}</span>
                        <span className="rpc-ccol-routes">{dayRoutes.length > 0 ? `${dayRoutes.length} rutas` : "—"}</span>
                      </div>
                      <div className="rpc-ccol-body">
                        {dayRoutes.length === 0 ? (
                          <div className="rpc-cno-routes">Sin rutas</div>
                        ) : (
                          dayRoutes.map((r, ri) => {
                            const color      = ROUTE_COLORS[ri % ROUTE_COLORS.length]!;
                            const isAssigning = assigningRouteId === r.id;
                            const canAssign   = !!selectedOrderId && !isAssigning;
                            const done        = r.stops.filter((s) => s.status === "completed" || s.status === "arrived").length;
                            return (
                              <div
                                key={r.id}
                                className={`rpc-ccard${canAssign ? " rpc-ccard-assign" : ""}`}
                                style={{ borderLeftColor: color }}
                                onClick={() => {
                                  if (canAssign) { void assignToRoute(r); }
                                  else { openDrawer(r); setActiveDayIso(iso); }
                                }}
                              >
                                <div className="rpc-ccard-top">
                                  <div className="rpc-rdot" style={{ background: color }} />
                                  <span className="rpc-ccard-id">{r.id.slice(0, 8)}</span>
                                  <span className={`rpc-rstatus ${STATUS_CSS[r.status] ?? ""}`}>
                                    {STATUS_LABEL[r.status] ?? r.status}
                                  </span>
                                </div>
                                <div className="rpc-ccard-stops">{r.stops.length} paradas · {done}/{r.stops.length}</div>
                                {r.status === "in_progress" && r.stops.length > 0 && (
                                  <div className="rpc-pbar">
                                    <div className="rpc-pbar-fill" style={{ width: `${Math.round(done / r.stops.length * 100)}%`, background: color }} />
                                  </div>
                                )}
                                {canAssign && !isAssigning && <div className="rpc-assign-hint-cal">+ Asignar aquí</div>}
                              </div>
                            );
                          })
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ── TIMELINE HEADER ── */}
          <div className="rpc-tl-header">
            <div className="rpc-tl-driver-col">Conductor / Ruta</div>
            <div className="rpc-tl-times">
              {GANTT_HOURS.map((h) => (
                <div key={h} className="rpc-tl-hour">{h}</div>
              ))}
            </div>
          </div>

          {/* ── TIMELINE BODY ── */}
          <div className="rpc-tl-body">
            {activeDayRoutes.length === 0 ? (
              <div className="rpc-tl-empty">
                Sin rutas para {activeDayLabel}
                {viewType === "semana" && " — click en una columna para cambiar el día"}
              </div>
            ) : (
              activeDayRoutes.map((r, ri) => {
                const color   = ROUTE_COLORS[ri % ROUTE_COLORS.length]!;
                const done    = r.stops.filter((s) => s.status === "completed" || s.status === "arrived").length;
                const total   = r.stops.length;
                const pct     = total > 0 ? Math.round((done / total) * 100) : 0;
                const isActive = activeRouteId === r.id;

                // stops line bounds
                const pcts = r.stops
                  .map((s) => ganttPct(s.estimated_arrival_at))
                  .filter((p): p is number => p !== null);
                const lineLeft  = pcts.length > 0 ? Math.min(...pcts) : null;
                const lineRight = pcts.length > 0 ? Math.max(...pcts) : null;

                return (
                  <div
                    key={r.id}
                    className={`rpc-rrow${isActive ? " rpc-rrow-active" : ""}`}
                    onClick={() => openDrawer(r)}
                  >
                    <div className="rpc-driver-cell">
                      <div className="rpc-driver-name">
                        <div className="rpc-rdot" style={{ background: color }} />
                        <span>{r.id.slice(0, 8)}</span>
                        {r.status === "in_progress" && (
                          <span style={{ color: "#dc2626", fontSize: 10, marginLeft: 2 }}>⚡</span>
                        )}
                      </div>
                      <div className="rpc-driver-meta">
                        <span>{done}/{total} paradas</span>
                      </div>
                      <div className="rpc-pbar">
                        <div className="rpc-pbar-fill" style={{ width: `${pct}%`, background: color }} />
                      </div>
                      <span className={`rpc-rstatus ${STATUS_CSS[r.status] ?? ""}`}>
                        {STATUS_LABEL[r.status] ?? r.status}
                      </span>
                    </div>

                    <div className="rpc-gantt-cell">
                      {/* assign hint shown on hover when order selected */}
                      {selectedOrder && (
                        <div
                          className="rpc-assign-hint"
                          onClick={(e) => { e.stopPropagation(); void assignToRoute(r); }}
                        />
                      )}
                      <div className="rpc-gantt-track">
                        <div className="rpc-gantt-grid">
                          {GANTT_HOURS.map((h) => <div key={h} className="rpc-gcol" />)}
                        </div>
                        {/* stops connector line */}
                        {lineLeft !== null && lineRight !== null && lineRight > lineLeft && (
                          <div
                            className="rpc-stops-line"
                            style={{ left: `${lineLeft}%`, width: `${lineRight - lineLeft}%` }}
                          />
                        )}
                        {/* stop bubbles */}
                        {r.stops.map((s, idx) => {
                          const p = ganttPct(s.estimated_arrival_at);
                          if (p === null) return null;
                          return (
                            <div
                              key={s.id}
                              className="rpc-sbubble"
                              style={{
                                left: `${p}%`,
                                background: s.status === "completed" ? color
                                          : s.status === "failed"    ? "#dc2626"
                                          : "#9ca3af",
                              }}
                              title={`Parada ${idx + 1} · ${STOP_LABEL[s.status] ?? s.status} · ${isoToHHMM(s.estimated_arrival_at)}`}
                              onClick={(e) => { e.stopPropagation(); openDrawer(r); }}
                            >
                              {idx + 1}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* ── DRAWER BACKDROP ── */}
          <div
            className={`rpc-drawer-backdrop${drawerRoute ? " open" : ""}`}
            onClick={closeDrawer}
          />

          {/* ── DRAWER ── */}
          <div className={`rpc-drawer${drawerRoute ? " open" : ""}`}>
            {drawerRoute && (
              <>
                <div className="rpc-drawer-hdr">
                  <div>
                    <div className="rpc-drawer-title">
                      {drawerRoute.id.slice(0, 8).toUpperCase()} · {STATUS_LABEL[drawerRoute.status] ?? drawerRoute.status}
                    </div>
                    <div className="rpc-drawer-sub">
                      {drawerRoute.stops.length} paradas · {drawerRoute.service_date}
                    </div>
                  </div>
                  <button className="rpc-drawer-close" onClick={closeDrawer}>✕</button>
                </div>

                <div className="rpc-drawer-body">
                  <p style={{ fontSize: 11, color: "#6b7280", marginBottom: 10 }}>
                    Edita la hora de llegada esperada de cada parada. Las paradas completadas no son editables.
                  </p>
                  {drawerRoute.stops.length === 0 ? (
                    <p style={{ fontSize: 12, color: "#6b7280" }}>Sin paradas en esta ruta</p>
                  ) : (
                    <table className="rpc-stbl">
                      <thead>
                        <tr>
                          <th>#</th>
                          <th>Pedido</th>
                          <th>Hora prevista</th>
                          <th>Estado</th>
                        </tr>
                      </thead>
                      <tbody>
                        {drawerRoute.stops
                          .slice()
                          .sort((a, b) => a.sequence_number - b.sequence_number)
                          .map((s) => {
                            const isEditing = editingStopId === s.id;
                            const isSaving  = savingStopId  === s.id;
                            const editable  = canEditRoute(drawerRoute);
                            const hhmm      = isoToHHMM(s.estimated_arrival_at);
                            const stopColor = STOP_COLOR[s.status] ?? "#9ca3af";
                            return (
                              <tr key={s.id}>
                                <td>
                                  <span className="rpc-snum" style={{ background: stopColor }}>
                                    {s.sequence_number}
                                  </span>
                                </td>
                                <td style={{ fontFamily: "monospace", fontSize: 11 }}>
                                  {s.order_id ? s.order_id.slice(0, 8) : "—"}
                                </td>
                                <td>
                                  {isSaving ? (
                                    <span style={{ fontSize: 11, color: "#6b7280" }}>Guardando…</span>
                                  ) : isEditing ? (
                                    <input
                                      className="rpc-ti"
                                      type="time"
                                      value={editingEta}
                                      autoFocus
                                      onChange={(e) => setEditingEta(e.target.value)}
                                      onBlur={() => void saveEta(s, drawerRoute.service_date)}
                                      onKeyDown={(e) => {
                                        if (e.key === "Enter") void saveEta(s, drawerRoute.service_date);
                                        if (e.key === "Escape") setEditingStopId(null);
                                      }}
                                    />
                                  ) : editable ? (
                                    <span
                                      className="rpc-eta rpc-eta-editable"
                                      onClick={() => startEditEta(s)}
                                      title="Click para editar hora prevista"
                                    >
                                      {hhmm || "—"}
                                    </span>
                                  ) : (
                                    <span className="rpc-eta">{hhmm || "—"}</span>
                                  )}
                                </td>
                                <td>
                                  <span
                                    className={`rpc-sbadge ${
                                      s.status === "completed" ? "rpc-sbadge-ok"
                                    : s.status === "failed"    ? "rpc-sbadge-fa"
                                    : "rpc-sbadge-pe"
                                    }`}
                                  >
                                    {STOP_LABEL[s.status] ?? s.status}
                                  </span>
                                </td>
                              </tr>
                            );
                          })}
                      </tbody>
                    </table>
                  )}
                </div>
              </>
            )}
          </div>

        </div>{/* /planner */}
      </div>{/* /body */}
    </div>
  );
}
