"use client";

/**
 * ROUTE-PLANNER-CAL-001
 * Vista de calendario semanal para planificación de rutas.
 * - Semana navegable (lun–dom), columna por día
 * - Sidebar: pedidos en estado "planned" / ready_for_planning listos para asignar
 * - Click pedido → selecciona; click en ruta → includeOrderInPlan(plan_id, order_id)
 */

import { useState, useEffect, useCallback } from "react";
import {
  listRoutes,
  listReadyToDispatchOrders,
  includeOrderInPlan,
  type RoutingRoute,
  type ReadyToDispatchItem,
} from "../lib/api";

// ── helpers ─────────────────────────────────────────────────────────────────

function getWeekDays(anchor: Date): Date[] {
  const day = anchor.getDay(); // 0=Sun
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

const DAY_LABELS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

const STATUS_COLOR: Record<string, string> = {
  draft: "var(--muted)",
  planned: "var(--accent)",
  dispatched: "var(--warn)",
  in_progress: "var(--success)",
  completed: "var(--subtle)",
  cancelled: "var(--danger)",
};

const STATUS_LABEL: Record<string, string> = {
  draft: "Borrador",
  planned: "Planificado",
  dispatched: "Despachado",
  in_progress: "En ruta",
  completed: "Completado",
  cancelled: "Cancelado",
};

// ── component ────────────────────────────────────────────────────────────────

type Props = { token: string };

type Toast = { kind: "ok" | "err"; msg: string };

export function RoutePlannerCalendar({ token }: Props) {
  const [weekAnchor, setWeekAnchor] = useState<Date>(() => new Date());
  const [routes, setRoutes] = useState<RoutingRoute[]>([]);
  const [readyOrders, setReadyOrders] = useState<ReadyToDispatchItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);
  const [assigningRouteId, setAssigningRouteId] = useState<string | null>(null);
  const [toast, setToast] = useState<Toast | null>(null);

  const weekDays = getWeekDays(weekAnchor);
  const todayIso = new Date().toISOString().slice(0, 10);

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
      setToast({ kind: "err", msg: e instanceof Error ? e.message : String(e) });
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { void loadData(); }, [loadData]);

  // Auto-dismiss toast after 4s
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  // Group routes by ISO date
  const routesByDay: Record<string, RoutingRoute[]> = {};
  for (const d of weekDays) {
    const iso = toIso(d);
    routesByDay[iso] = routes.filter((r) => r.service_date === iso);
  }

  function toggleOrder(id: string) {
    setSelectedOrderId((prev) => (prev === id ? null : id));
  }

  async function assignToRoute(route: RoutingRoute) {
    if (!selectedOrderId) return;
    setAssigningRouteId(route.id);
    try {
      await includeOrderInPlan(token, route.plan_id, selectedOrderId);
      setToast({ kind: "ok", msg: "Pedido incluido en el plan" });
      setSelectedOrderId(null);
      void loadData();
    } catch (e: unknown) {
      setToast({ kind: "err", msg: e instanceof Error ? e.message : String(e) });
    } finally {
      setAssigningRouteId(null);
    }
  }

  function prevWeek() {
    setWeekAnchor((d) => { const n = new Date(d); n.setDate(d.getDate() - 7); return n; });
  }
  function nextWeek() {
    setWeekAnchor((d) => { const n = new Date(d); n.setDate(d.getDate() + 7); return n; });
  }

  const selectedOrder = readyOrders.find((o) => o.id === selectedOrderId);

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
        <button
          className="secondary rpc-btn-sm"
          onClick={() => void loadData()}
          disabled={loading}
        >
          {loading ? "Cargando…" : "↻ Refrescar"}
        </button>
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
            📦 Asignando pedido{" "}
            <strong>{selectedOrder.id.slice(0, 8)}</strong>
            {selectedOrder.total_weight_kg != null
              ? ` · ${selectedOrder.total_weight_kg} kg`
              : ""}
            {" — haz click en una ruta"}
          </span>
          <button
            className="rpc-btn-cancel"
            onClick={() => setSelectedOrderId(null)}
          >
            ✕ Cancelar
          </button>
        </div>
      )}

      {/* ── main layout ── */}
      <div className="rpc-body">

        {/* Sidebar */}
        <aside className="rpc-sidebar card">
          <div className="rpc-sidebar-hdr">
            Sin asignar
            <span className="rpc-count">{readyOrders.length}</span>
          </div>

          {readyOrders.length === 0 && !loading && (
            <p className="rpc-empty">Todos los pedidos están planificados</p>
          )}

          <div className="rpc-order-list">
            {readyOrders.map((o) => {
              const isSel = selectedOrderId === o.id;
              return (
                <div
                  key={o.id}
                  className={`rpc-order-card${isSel ? " rpc-order-sel" : ""}`}
                  onClick={() => toggleOrder(o.id)}
                  title={isSel ? "Click para deseleccionar" : "Click para seleccionar y asignar"}
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

        {/* Calendar grid */}
        <div className="rpc-grid">
          {weekDays.map((day, i) => {
            const iso = toIso(day);
            const dayRoutes = routesByDay[iso] ?? [];
            const isToday = iso === todayIso;
            return (
              <div key={iso} className={`rpc-col${isToday ? " rpc-col-today" : ""}`}>

                {/* Column header */}
                <div className="rpc-col-hdr">
                  <span className="rpc-day-name">{DAY_LABELS[i]}</span>
                  <span className={`rpc-day-num${isToday ? " rpc-day-num-today" : ""}`}>
                    {day.getDate()}
                  </span>
                  <span className="rpc-col-routes">
                    {dayRoutes.length > 0 ? `${dayRoutes.length} rutas` : "—"}
                  </span>
                </div>

                {/* Route cards */}
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
                          onClick={() => { if (canAssign) void assignToRoute(r); }}
                          title={canAssign ? "Click para asignar pedido a esta ruta" : ""}
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
                              <span className="rpc-stop-progress">
                                {" "}· {doneStops}/{r.stops.length}
                              </span>
                            )}
                          </div>
                          {r.status === "in_progress" && r.stops.length > 0 && (
                            <div
                              className="rpc-progress-bar"
                              title={`${doneStops} de ${r.stops.length} paradas completadas`}
                            >
                              <div
                                className="rpc-progress-fill"
                                style={{ width: `${Math.round((doneStops / r.stops.length) * 100)}%` }}
                              />
                            </div>
                          )}
                          {isAssigning && (
                            <div className="rpc-route-spinner">Asignando…</div>
                          )}
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

      </div>
    </section>
  );
}
