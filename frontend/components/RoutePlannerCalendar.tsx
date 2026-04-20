"use client";

/**
 * ROUTE-PLANNER-CAL-001 v2
 * Vista de calendario semanal para planificación de rutas.
 * - Semana navegable (lun–dom), columna por día
 * - Sidebar: pedidos listos para asignar + buscador
 * - KPI strip: rutas, paradas, sin asignar
 * - Toggle semana/día
 * - Gantt timeline: stop bubbles posicionados por estimated_arrival_at
 * - Drawer: tabla de paradas + edición inline de hora prevista (TW-001-UI)
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

// ── constants ────────────────────────────────────────────────────────────────

const DAY_LABELS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

const GANTT_START = 8;
const GANTT_END   = 20;
const GANTT_HOURS = [8, 10, 12, 14, 16, 18, 20];

const STATUS_COLOR: Record<string, string> = {
  draft:       "var(--muted)",
  planned:     "var(--accent)",
  dispatched:  "var(--warn)",
  in_progress: "var(--success)",
  completed:   "var(--subtle)",
  cancelled:   "var(--danger)",
};

const STATUS_LABEL: Record<string, string> = {
  draft:       "Borrador",
  planned:     "Planificado",
  dispatched:  "Despachado",
  in_progress: "En ruta",
  completed:   "Completado",
  cancelled:   "Cancelado",
};

const STOP_COLOR: Record<string, string> = {
  pending:    "#9ca3af",
  en_route:   "#2563eb",
  arrived:    "#d97706",
  completed:  "#16a34a",
  failed:     "#dc2626",
  skipped:    "#9ca3af",
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

function fmtDate(d: Date, opts: Intl.DateTimeFormatOptions): string {
  return d.toLocaleDateString("es-ES", opts);
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

/** Returns 0-100 percentage position along gantt axis, or null if no eta */
function ganttPct(eta: string | null): number | null {
  if (!eta) return null;
  try {
    const d = new Date(eta);
    const h = d.getHours() + d.getMinutes() / 60;
    const pct = ((h - GANTT_START) / (GANTT_END - GANTT_START)) * 100;
    return Math.max(0, Math.min(100, pct));
  } catch {
    return null;
  }
}

function canEditRoute(r: RoutingRoute): boolean {
  return r.status === "draft" || r.status === "planned" || r.status === "dispatched";
}

// ── component ────────────────────────────────────────────────────────────────

type Props = { token: string };
type Toast = { kind: "ok" | "err"; msg: string };
type ViewType = "week" | "day";

export function RoutePlannerCalendar({ token }: Props) {
  // week nav
  const [weekAnchor, setWeekAnchor] = useState<Date>(() => new Date());
  // view toggle
  const [viewType, setViewType] = useState<ViewType>("week");
  const [activeDayIso, setActiveDayIso] = useState<string>(() => new Date().toISOString().slice(0, 10));
  // data
  const [routes, setRoutes] = useState<RoutingRoute[]>([]);
  const [readyOrders, setReadyOrders] = useState<ReadyToDispatchItem[]>([]);
  const [loading, setLoading] = useState(false);
  // assign flow
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);
  const [assigningRouteId, setAssigningRouteId] = useState<string | null>(null);
  // sidebar search
  const [search, setSearch] = useState("");
  // drawer
  const [drawerRoute, setDrawerRoute] = useState<RoutingRoute | null>(null);
  // inline ETA edit
  const [editingStopId, setEditingStopId] = useState<string | null>(null);
  const [editingEta, setEditingEta] = useState("");
  const [savingStopId, setSavingStopId] = useState<string | null>(null);
  // toast
  const [toast, setToast] = useState<Toast | null>(null);

  const weekDays = getWeekDays(weekAnchor);
  const todayIso = new Date().toISOString().slice(0, 10);

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

  // Auto-dismiss toast
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  // Sync drawer when routes reload
  useEffect(() => {
    if (!drawerRoute) return;
    const updated = routes.find((r) => r.id === drawerRoute.id);
    if (updated) setDrawerRoute(updated);
  }, [routes]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── helpers ────────────────────────────────────────────────────────────────

  function showToast(kind: "ok" | "err", msg: string) {
    setToast({ kind, msg });
  }

  // Group routes by ISO date
  const routesByDay: Record<string, RoutingRoute[]> = {};
  for (const d of weekDays) {
    const iso = toIso(d);
    routesByDay[iso] = routes.filter((r) => r.service_date === iso);
  }

  // KPI
  const weekRoutes = weekDays.flatMap((d) => routesByDay[toIso(d)] ?? []);
  const totalStops = weekRoutes.reduce((n, r) => n + r.stops.length, 0);

  // Filtered sidebar orders
  const filteredOrders = search.trim()
    ? readyOrders.filter((o) =>
        o.id.toLowerCase().includes(search.toLowerCase()) ||
        o.service_date.includes(search),
      )
    : readyOrders;

  // Active-day routes (gantt source)
  const activeDayRoutes = routes.filter((r) => r.service_date === activeDayIso);

  // ── assign flow ────────────────────────────────────────────────────────────

  function toggleOrder(id: string) {
    setSelectedOrderId((prev) => (prev === id ? null : id));
  }

  async function assignToRoute(route: RoutingRoute) {
    if (!selectedOrderId) return;
    setAssigningRouteId(route.id);
    try {
      await includeOrderInPlan(token, route.plan_id, selectedOrderId);
      showToast("ok", "Pedido incluido en el plan");
      setSelectedOrderId(null);
      void loadData();
    } catch (e: unknown) {
      showToast("err", e instanceof Error ? e.message : String(e));
    } finally {
      setAssigningRouteId(null);
    }
  }

  // ── ETA inline edit ────────────────────────────────────────────────────────

  function startEditEta(stop: RoutingRouteStop) {
    setEditingStopId(stop.id);
    setEditingEta(isoToHHMM(stop.estimated_arrival_at));
  }

  async function saveEta(stop: RoutingRouteStop, serviceDate: string) {
    if (!editingEta) { setEditingStopId(null); return; }
    setSavingStopId(stop.id);
    try {
      const iso = hhmmToIso(editingEta, serviceDate);
      await patchStopScheduledArrival(token, stop.id, iso);
      showToast("ok", `Hora prevista actualizada: ${editingEta}`);
      setEditingStopId(null);
      void loadData();
    } catch (e: unknown) {
      showToast("err", e instanceof Error ? e.message : String(e));
    } finally {
      setSavingStopId(null);
    }
  }

  // ── week nav ───────────────────────────────────────────────────────────────

  function prevWeek() {
    setWeekAnchor((d) => { const n = new Date(d); n.setDate(d.getDate() - 7); return n; });
  }
  function nextWeek() {
    setWeekAnchor((d) => { const n = new Date(d); n.setDate(d.getDate() + 7); return n; });
  }

  const selectedOrder = readyOrders.find((o) => o.id === selectedOrderId);

  // ── render ─────────────────────────────────────────────────────────────────

  return (
    <section className="rpc-root">

      {/* ── top nav ── */}
      <div className="rpc-nav card">
        <div className="rpc-nav-left">
          <button className="secondary rpc-btn-sm" onClick={prevWeek}>‹</button>
          <span className="rpc-week-label">
            {fmtDate(weekDays[0]!, { day: "2-digit", month: "short" })}
            {" — "}
            {fmtDate(weekDays[6]!, { day: "2-digit", month: "short", year: "numeric" })}
          </span>
          <button className="secondary rpc-btn-sm" onClick={nextWeek}>›</button>
          <button className="secondary rpc-btn-sm" onClick={() => setWeekAnchor(new Date())}>Hoy</button>
        </div>
        <div className="rpc-nav-right">
          <div className="rpc-view-toggle">
            <button
              className={`rpc-toggle-btn${viewType === "week" ? " active" : ""}`}
              onClick={() => setViewType("week")}
            >Semana</button>
            <button
              className={`rpc-toggle-btn${viewType === "day" ? " active" : ""}`}
              onClick={() => setViewType("day")}
            >Día</button>
          </div>
          <button
            className="secondary rpc-btn-sm"
            onClick={() => void loadData()}
            disabled={loading}
          >
            {loading ? "Cargando…" : "↻"}
          </button>
        </div>
      </div>

      {/* ── KPI strip ── */}
      <div className="rpc-kpi-strip card">
        <div className="rpc-kpi">
          <span className="rpc-kpi-val">{weekRoutes.length}</span>
          <span className="rpc-kpi-lbl">Rutas esta semana</span>
        </div>
        <div className="rpc-kpi">
          <span className="rpc-kpi-val">{totalStops}</span>
          <span className="rpc-kpi-lbl">Paradas totales</span>
        </div>
        <div className="rpc-kpi">
          <span className="rpc-kpi-val">{readyOrders.length}</span>
          <span className="rpc-kpi-lbl">Sin asignar</span>
        </div>
        <div className="rpc-kpi">
          <span className="rpc-kpi-val">{activeDayRoutes.length}</span>
          <span className="rpc-kpi-lbl">
            Rutas{" "}
            {fmtDate(
              weekDays.find((d) => toIso(d) === activeDayIso) ?? new Date(activeDayIso),
              { weekday: "short", day: "numeric" },
            )}
          </span>
        </div>
      </div>

      {/* ── toast ── */}
      {toast && (
        <div
          className={`rpc-toast rpc-toast-${toast.kind}`}
          onClick={() => setToast(null)}
        >
          {toast.kind === "ok" ? "✓" : "⚠"} {toast.msg}
        </div>
      )}

      {/* ── assign banner ── */}
      {selectedOrder && (
        <div className="rpc-assign-banner">
          <span>
            📦 Asignando{" "}
            <strong>{selectedOrder.id.slice(0, 8)}</strong>
            {selectedOrder.total_weight_kg != null
              ? ` · ${selectedOrder.total_weight_kg} kg`
              : ""}
            {" — haz click en una ruta"}
          </span>
          <button className="rpc-btn-cancel" onClick={() => setSelectedOrderId(null)}>
            ✕ Cancelar
          </button>
        </div>
      )}

      {/* ── main layout ── */}
      <div className="rpc-body">

        {/* ── Sidebar ── */}
        <aside className="rpc-sidebar card">
          <div className="rpc-sidebar-hdr">
            Sin asignar
            <span className="rpc-count">{filteredOrders.length}</span>
          </div>
          <input
            className="rpc-search"
            placeholder="Buscar pedido…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />

          {filteredOrders.length === 0 && !loading && (
            <p className="rpc-empty">
              {search ? "Sin resultados" : "Todos los pedidos están planificados"}
            </p>
          )}

          <div className="rpc-order-list">
            {filteredOrders.map((o) => {
              const isSel = selectedOrderId === o.id;
              return (
                <div
                  key={o.id}
                  className={`rpc-order-card${isSel ? " rpc-order-sel" : ""}`}
                  onClick={() => toggleOrder(o.id)}
                  title={isSel ? "Click para deseleccionar" : "Click para seleccionar"}
                >
                  <div className="rpc-order-ref">{o.id.slice(0, 8)}</div>
                  <div className="rpc-order-date">{o.service_date}</div>
                  {o.total_weight_kg != null && (
                    <div className="rpc-order-meta">{o.total_weight_kg} kg</div>
                  )}
                  {isSel && <div className="rpc-order-sel-badge">Seleccionado →</div>}
                </div>
              );
            })}
          </div>
        </aside>

        {/* ── Right panel ── */}
        <div className="rpc-main">

          {/* ── Calendar area ── */}
          <div className="rpc-cal-area">
            {viewType === "week" ? (
              <div className="rpc-grid">
                {weekDays.map((day, i) => {
                  const iso = toIso(day);
                  const dayRoutes = routesByDay[iso] ?? [];
                  const isToday = iso === todayIso;
                  const isActive = iso === activeDayIso;
                  return (
                    <div key={iso} className={`rpc-col${isToday ? " rpc-col-today" : ""}`}>
                      <div
                        className={`rpc-col-hdr${isActive ? " rpc-col-hdr-active" : ""}`}
                        onClick={() => setActiveDayIso(iso)}
                        style={{ cursor: "pointer" }}
                        title="Click para ver en gantt"
                      >
                        <span className="rpc-day-name">{DAY_LABELS[i]}</span>
                        <span className={`rpc-day-num${isToday ? " rpc-day-num-today" : ""}`}>
                          {day.getDate()}
                        </span>
                        <span className="rpc-col-routes">
                          {dayRoutes.length > 0 ? `${dayRoutes.length} rutas` : "—"}
                        </span>
                      </div>

                      <div className="rpc-col-body">
                        {dayRoutes.length === 0 ? (
                          <div className="rpc-no-routes">Sin rutas</div>
                        ) : (
                          dayRoutes.map((r) => {
                            const isAssigning = assigningRouteId === r.id;
                            const canAssign = !!selectedOrderId && !isAssigning;
                            const doneStops = r.stops.filter(
                              (s) => s.status === "completed" || s.status === "arrived",
                            ).length;
                            return (
                              <div
                                key={r.id}
                                className={`rpc-route-card${canAssign ? " rpc-route-assignable" : ""}`}
                                onClick={() => {
                                  if (canAssign) { void assignToRoute(r); }
                                  else { setDrawerRoute(r); setActiveDayIso(iso); }
                                }}
                                title={canAssign ? "Click para asignar pedido" : "Click para ver detalle"}
                              >
                                <div className="rpc-route-top">
                                  <span className="rpc-route-id">{r.id.slice(0, 8)}</span>
                                  <span
                                    className="rpc-route-status"
                                    style={{ color: STATUS_COLOR[r.status] ?? "var(--muted)" }}
                                  >
                                    {STATUS_LABEL[r.status] ?? r.status}
                                  </span>
                                </div>
                                <div className="rpc-route-stops">
                                  {r.stops.length} paradas
                                  {r.stops.length > 0 && (
                                    <span className="rpc-stop-progress"> · {doneStops}/{r.stops.length}</span>
                                  )}
                                </div>
                                {r.status === "in_progress" && r.stops.length > 0 && (
                                  <div className="rpc-progress-bar">
                                    <div
                                      className="rpc-progress-fill"
                                      style={{ width: `${Math.round((doneStops / r.stops.length) * 100)}%` }}
                                    />
                                  </div>
                                )}
                                {isAssigning && <div className="rpc-route-spinner">Asignando…</div>}
                                {canAssign && !isAssigning && (
                                  <div className="rpc-assign-hint">+ Asignar aquí</div>
                                )}
                              </div>
                            );
                          })
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              /* Day view */
              <div className="rpc-day-view">
                <div className="rpc-day-view-hdr">
                  {fmtDate(
                    weekDays.find((d) => toIso(d) === activeDayIso) ?? new Date(activeDayIso),
                    { weekday: "long", day: "numeric", month: "long" },
                  )}
                  <span className="rpc-count" style={{ marginLeft: 8 }}>{activeDayRoutes.length} rutas</span>
                </div>
                {activeDayRoutes.length === 0 ? (
                  <div className="rpc-no-routes" style={{ padding: "24px 0" }}>Sin rutas este día</div>
                ) : (
                  activeDayRoutes.map((r) => {
                    const doneStops = r.stops.filter(
                      (s) => s.status === "completed" || s.status === "arrived",
                    ).length;
                    return (
                      <div
                        key={r.id}
                        className="rpc-route-card"
                        style={{ marginBottom: 8, cursor: "pointer" }}
                        onClick={() => setDrawerRoute(r)}
                      >
                        <div className="rpc-route-top">
                          <span className="rpc-route-id">{r.id.slice(0, 8)}</span>
                          <span className="rpc-route-status" style={{ color: STATUS_COLOR[r.status] }}>
                            {STATUS_LABEL[r.status] ?? r.status}
                          </span>
                        </div>
                        <div className="rpc-route-stops">{r.stops.length} paradas · {doneStops}/{r.stops.length} completadas</div>
                        {r.status === "in_progress" && r.stops.length > 0 && (
                          <div className="rpc-progress-bar">
                            <div className="rpc-progress-fill" style={{ width: `${Math.round((doneStops / r.stops.length) * 100)}%` }} />
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            )}
          </div>

          {/* ── Gantt timeline ── */}
          <div className="rpc-tl card">
            <div className="rpc-tl-hdr">
              <div className="rpc-tl-label-col">
                <span style={{ fontSize: 11, fontWeight: 600, color: "var(--ink-muted)" }}>
                  {fmtDate(
                    weekDays.find((d) => toIso(d) === activeDayIso) ?? new Date(activeDayIso),
                    { weekday: "short", day: "numeric" },
                  )}
                </span>
              </div>
              <div className="rpc-tl-hours">
                {GANTT_HOURS.map((h) => (
                  <div key={h} className="rpc-tl-hour">
                    {String(h).padStart(2, "0")}:00
                  </div>
                ))}
              </div>
            </div>
            <div className="rpc-tl-body">
              {activeDayRoutes.length === 0 ? (
                <div className="rpc-tl-empty">Sin rutas el día seleccionado — click en una columna para cambiarlo</div>
              ) : (
                activeDayRoutes.map((r) => (
                  <div key={r.id} className="rpc-tl-row" onClick={() => setDrawerRoute(r)} style={{ cursor: "pointer" }}>
                    <div className="rpc-tl-label-col">
                      <span className="rpc-tl-route-id">{r.id.slice(0, 8)}</span>
                      <span
                        className="rpc-tl-route-st"
                        style={{ color: STATUS_COLOR[r.status] ?? "var(--muted)" }}
                      >
                        {STATUS_LABEL[r.status] ?? r.status}
                      </span>
                    </div>
                    <div className="rpc-gantt-cell">
                      {/* hour grid columns */}
                      {GANTT_HOURS.slice(0, -1).map((h) => (
                        <div key={h} className="rpc-gcol" />
                      ))}
                      {/* stop bubbles */}
                      {r.stops.map((s, idx) => {
                        const pct = ganttPct(s.estimated_arrival_at);
                        if (pct === null) return null;
                        return (
                          <div
                            key={s.id}
                            className="rpc-sbubble"
                            style={{
                              left: `${pct}%`,
                              backgroundColor: STOP_COLOR[s.status] ?? "#9ca3af",
                            }}
                            title={`Parada ${idx + 1} · ${STOP_LABEL[s.status] ?? s.status} · ${isoToHHMM(s.estimated_arrival_at)}`}
                          >
                            {idx + 1}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

        </div>
      </div>

      {/* ── Drawer backdrop ── */}
      <div
        className={`rpc-drawer-backdrop${drawerRoute ? " open" : ""}`}
        onClick={() => { setDrawerRoute(null); setEditingStopId(null); }}
      />

      {/* ── Drawer ── */}
      <div className={`rpc-drawer${drawerRoute ? " open" : ""}`}>
        {drawerRoute && (
          <>
            <div className="rpc-drawer-hdr">
              <div>
                <div className="rpc-drawer-title">{drawerRoute.id.slice(0, 8)}</div>
                <div className="rpc-drawer-sub">
                  <span style={{ color: STATUS_COLOR[drawerRoute.status] ?? "var(--muted)" }}>
                    {STATUS_LABEL[drawerRoute.status] ?? drawerRoute.status}
                  </span>
                  {" · "}
                  {drawerRoute.service_date}
                  {" · "}
                  {drawerRoute.stops.length} paradas
                </div>
              </div>
              <button
                className="rpc-drawer-close"
                onClick={() => { setDrawerRoute(null); setEditingStopId(null); }}
              >
                ✕
              </button>
            </div>

            <div className="rpc-drawer-body">
              {drawerRoute.stops.length === 0 ? (
                <p className="rpc-empty">Sin paradas en esta ruta</p>
              ) : (
                <table className="rpc-stbl">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Pedido</th>
                      <th>Estado</th>
                      <th>Hora prevista</th>
                    </tr>
                  </thead>
                  <tbody>
                    {drawerRoute.stops
                      .slice()
                      .sort((a, b) => a.sequence_number - b.sequence_number)
                      .map((s) => {
                        const isEditing = editingStopId === s.id;
                        const isSaving = savingStopId === s.id;
                        const editable = canEditRoute(drawerRoute);
                        const hhmm = isoToHHMM(s.estimated_arrival_at);
                        return (
                          <tr key={s.id}>
                            <td>
                              <span className="rpc-snum">{s.sequence_number}</span>
                            </td>
                            <td style={{ fontSize: 12, fontFamily: "monospace" }}>
                              {s.order_id.slice(0, 8)}
                            </td>
                            <td>
                              <span
                                className="rpc-sbadge"
                                style={{ background: STOP_COLOR[s.status] ?? "#9ca3af" }}
                              >
                                {STOP_LABEL[s.status] ?? s.status}
                              </span>
                            </td>
                            <td>
                              {isSaving ? (
                                <span style={{ fontSize: 11, color: "var(--ink-muted)" }}>Guardando…</span>
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
                                <span className="rpc-eta">
                                  {hhmm || "—"}
                                </span>
                              )}
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

    </section>
  );
}
