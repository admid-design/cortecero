"use client";

/**
 * DriverMobileView — shell móvil-first para conductores (DRIVER-MOBILE-001)
 *
 * Estructura:
 *   ┌─────────────────────────────────┐ ← drv-header (44px)
 *   │  CorteCero        GPS ●  Salir  │
 *   ├─────────────────────────────────┤
 *   │                                 │
 *   │         Google Maps             │ ← drv-map-zone (flex-1)
 *   │    (ruta activa + marcadores)   │
 *   │                                 │
 *   │  ╔══════════════════════════╗  │
 *   │  ║  ▬  (drag handle)        ║  │ ← drv-sheet (position:fixed, bottom:0)
 *   │  ║  Siguiente: #3 · Pending ║  │   collapse=26vh / mid=56vh / expanded=91vh
 *   │  ║  [ Llegar ] [ Completar ]║  │
 *   │  ║  [ Falla ] [Incidencia]  ║  │
 *   │  ╚══════════════════════════╝  │
 *   └─────────────────────────────────┘
 */

import React, { useEffect, useRef, useState } from "react";
import type { IncidentCreateRequest, RouteNextStopResponse, RoutingRoute, RoutingRouteStop } from "../lib/api";
import { RouteMapCard } from "./RouteMapCard";
import {
  FailModal,
  IncidentModal,
  ProofModal,
  StopStatusBadge,
  buildNavUrl,
  useGpsTracking,
} from "./DriverRoutingCard";

// ── Types ─────────────────────────────────────────────────────────────────────

type SheetSnap = "collapsed" | "mid" | "expanded";

const SHEET_SNAP_VH: Record<SheetSnap, number> = {
  collapsed: 26,
  mid: 56,
  expanded: 91,
};

// ── Props ─────────────────────────────────────────────────────────────────────

export type DriverMobileViewProps = {
  loading: boolean;
  routes: RoutingRoute[];
  selectedRouteId: string;
  onSelectedRouteIdChange: (id: string) => void;
  selectedRoute: RoutingRoute | null;
  nextStopResponse: RouteNextStopResponse | null;
  nextStopLoading: boolean;
  actionLoadingStopId: string | null;
  incidentLoading: boolean;
  proofLoading: boolean;
  errorMessage: string | null;
  successMessage: string | null;
  token?: string | null;
  apiBaseUrl?: string;
  onRefresh: () => void;
  onArrive: (stopId: string) => void;
  onComplete: (stopId: string) => void;
  onCompleteWithProof: (stopId: string, signatureData: string, signedBy: string) => void;
  onFail: (stopId: string, reason: string) => void;
  onSkip: (stopId: string) => void;
  onReportIncident: (payload: IncidentCreateRequest) => void;
  onLogout: () => void;
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatEta(isoString: string | null): string {
  if (!isoString) return "";
  try {
    const d = new Date(isoString);
    return d.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function stopBorderColor(status: RoutingRouteStop["status"]): string {
  if (status === "completed") return "#16a34a";
  if (status === "arrived" || status === "en_route") return "#2563eb";
  if (status === "failed") return "#dc2626";
  if (status === "skipped") return "#9ca3af";
  return "#f59e0b";
}

const TERMINAL: RoutingRouteStop["status"][] = ["completed", "failed", "skipped"];

// ── Component ─────────────────────────────────────────────────────────────────

export function DriverMobileView({
  loading,
  routes,
  selectedRouteId,
  onSelectedRouteIdChange,
  selectedRoute,
  nextStopResponse,
  nextStopLoading,
  actionLoadingStopId,
  incidentLoading,
  proofLoading,
  errorMessage,
  successMessage,
  token = null,
  apiBaseUrl = "",
  onRefresh,
  onArrive,
  onComplete,
  onCompleteWithProof,
  onFail,
  onSkip,
  onReportIncident,
  onLogout,
}: DriverMobileViewProps) {
  // ── Auto-select route (in_progress > dispatched > first) ─────────────────
  useEffect(() => {
    if (selectedRouteId || routes.length === 0) return;
    const auto =
      routes.find((r) => r.status === "in_progress") ??
      routes.find((r) => r.status === "dispatched") ??
      routes[0];
    if (auto) onSelectedRouteIdChange(auto.id);
  }, [routes, selectedRouteId, onSelectedRouteIdChange]);

  // ── GPS ───────────────────────────────────────────────────────────────────
  const gpsRouteId =
    selectedRoute?.status === "in_progress" ? selectedRoute.id : null;
  const { active: gpsActive, position: gpsPosition } = useGpsTracking(
    gpsRouteId,
    token,
    apiBaseUrl,
  );

  // ── Modal state ───────────────────────────────────────────────────────────
  const [failStopId, setFailStopId] = useState<string | null>(null);
  const [incidentOpenStopId, setIncidentOpenStopId] = useState<string | null | "none">(null);
  const incidentModalOpen = incidentOpenStopId !== null;
  const [proofStopId, setProofStopId] = useState<string | null>(null);

  // ── Bottom sheet ──────────────────────────────────────────────────────────
  const [sheetSnap, setSheetSnap] = useState<SheetSnap>("mid");
  const touchStartY = useRef<number | null>(null);
  const [dragDelta, setDragDelta] = useState(0);
  const [isDragging, setIsDragging] = useState(false);

  function onSheetTouchStart(e: React.TouchEvent) {
    touchStartY.current = e.touches[0].clientY;
    setIsDragging(true);
  }
  function onSheetTouchMove(e: React.TouchEvent) {
    if (touchStartY.current == null) return;
    setDragDelta(e.touches[0].clientY - touchStartY.current);
  }
  function onSheetTouchEnd() {
    const delta = dragDelta;
    setIsDragging(false);
    setDragDelta(0);
    touchStartY.current = null;
    const THRESHOLD = 50;
    if (delta < -THRESHOLD) {
      setSheetSnap((s) => (s === "collapsed" ? "mid" : "expanded"));
    } else if (delta > THRESHOLD) {
      setSheetSnap((s) => (s === "expanded" ? "mid" : "collapsed"));
    }
  }

  const sheetBaseVh = SHEET_SNAP_VH[sheetSnap];
  const sheetStyle: React.CSSProperties = isDragging
    ? { height: `calc(${sheetBaseVh}vh - ${dragDelta}px)`, transition: "none" }
    : { height: `${sheetBaseVh}vh` };

  // ── Derived ───────────────────────────────────────────────────────────────
  const nextStop: RoutingRouteStop | null = nextStopResponse?.next_stop ?? null;
  const navUrl = buildNavUrl(nextStop?.customer_lat, nextStop?.customer_lng);
  const failLoadingThisStop =
    failStopId !== null && actionLoadingStopId === failStopId;
  const sigLoadingThisStop = proofStopId !== null && proofLoading;
  const driverPosition = gpsPosition
    ? {
        lat: gpsPosition.lat,
        lng: gpsPosition.lng,
        heading: gpsPosition.heading,
        updated_at: new Date().toISOString(),
      }
    : null;

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="drv-shell">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <header className="drv-header">
        <span className="drv-header-logo">CorteCero</span>
        <span className="drv-header-spacer" />
        {loading && <span className="drv-header-pill">Cargando…</span>}
        {gpsActive && !loading && (
          <span className="drv-header-pill drv-gps-pill">
            <span className="drv-gps-dot" />
            GPS
          </span>
        )}
        <button
          className="drv-header-btn"
          onClick={onRefresh}
          disabled={loading}
          aria-label="Actualizar"
        >
          ↺
        </button>
        <button
          className="drv-header-btn drv-header-btn-logout"
          onClick={onLogout}
          aria-label="Cerrar sesión"
        >
          ✕
        </button>
      </header>

      {/* ── Map zone ─────────────────────────────────────────────────────── */}
      <div className="drv-map-zone">
        <RouteMapCard
          route={selectedRoute ?? null}
          driverPosition={driverPosition}
        />
      </div>

      {/* ── Bottom sheet ─────────────────────────────────────────────────── */}
      <div className="drv-sheet" style={sheetStyle}>
        {/* Drag handle */}
        <div
          className="drv-handle"
          onTouchStart={onSheetTouchStart}
          onTouchMove={onSheetTouchMove}
          onTouchEnd={onSheetTouchEnd}
          role="presentation"
          aria-hidden="true"
        >
          <div className="drv-handle-bar" />
        </div>

        {/* Scrollable content */}
        <div className="drv-sheet-content">
          {errorMessage && (
            <div className="drv-banner drv-banner-error">{errorMessage}</div>
          )}
          {successMessage && (
            <div className="drv-banner drv-banner-ok">{successMessage}</div>
          )}

          {routes.length === 0 ? (
            <p className="drv-empty">
              {loading ? "Cargando rutas…" : "Sin rutas asignadas para hoy."}
            </p>
          ) : (
            <>
              {/* Route pills */}
              <div className="drv-route-pills">
                {routes.map((r) => (
                  <button
                    key={r.id}
                    className={`drv-route-pill${r.id === selectedRouteId ? " active" : ""}`}
                    onClick={() => onSelectedRouteIdChange(r.id)}
                  >
                    {r.service_date} · {r.status} · {r.stops.length}p
                  </button>
                ))}
              </div>

              {/* Next stop card */}
              {selectedRoute && (
                <div className="drv-next-card">
                  <p className="drv-next-label">Siguiente parada</p>

                  {nextStopLoading ? (
                    <p className="drv-next-loading">Cargando…</p>
                  ) : nextStop ? (
                    <>
                      <div className="drv-next-meta">
                        <span className="drv-next-seq">#{nextStop.sequence_number}</span>
                        <StopStatusBadge status={nextStop.status} />
                        {nextStop.estimated_arrival_at && (
                          <span className="drv-next-eta">
                            ETA {formatEta(nextStop.estimated_arrival_at)}
                          </span>
                        )}
                        {nextStopResponse && nextStopResponse.remaining_stops > 0 && (
                          <span className="drv-next-remaining">
                            {nextStopResponse.remaining_stops} restante
                            {nextStopResponse.remaining_stops !== 1 ? "s" : ""}
                          </span>
                        )}
                      </div>

                      {navUrl && (
                        <a
                          href={navUrl}
                          className="drv-nav-link"
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          🗺 Navegar
                        </a>
                      )}

                      {!TERMINAL.includes(nextStop.status) && (
                        <div className="drv-actions">
                          {(nextStop.status === "pending" || nextStop.status === "en_route") && (
                            <button
                              className="drv-btn drv-btn-primary"
                              disabled={actionLoadingStopId === nextStop.id}
                              onClick={() => onArrive(nextStop.id)}
                            >
                              {actionLoadingStopId === nextStop.id ? "…" : "Llegar"}
                            </button>
                          )}
                          {nextStop.status === "arrived" && (
                            <button
                              className="drv-btn drv-btn-primary"
                              disabled={actionLoadingStopId === nextStop.id}
                              onClick={() => setProofStopId(nextStop.id)}
                            >
                              Completar
                            </button>
                          )}
                          <button
                            className="drv-btn drv-btn-danger"
                            disabled={actionLoadingStopId === nextStop.id}
                            onClick={() => setFailStopId(nextStop.id)}
                          >
                            Falla
                          </button>
                          <button
                            className="drv-btn drv-btn-muted"
                            disabled={actionLoadingStopId === nextStop.id}
                            onClick={() => onSkip(nextStop.id)}
                          >
                            Omitir
                          </button>
                        </div>
                      )}
                    </>
                  ) : (
                    <p className="drv-next-loading">
                      No hay paradas pendientes. ¡Ruta completada!
                    </p>
                  )}
                </div>
              )}

              {/* Full stop list — only in expanded state */}
              {sheetSnap === "expanded" && selectedRoute && selectedRoute.stops.length > 0 && (
                <div className="drv-stop-list">
                  <p className="drv-stop-list-title">
                    Todas las paradas ({selectedRoute.stops.length})
                  </p>
                  {selectedRoute.stops.map((stop) => {
                    const sNavUrl = buildNavUrl(stop.customer_lat, stop.customer_lng);
                    const isActive = actionLoadingStopId === stop.id;
                    const terminal = TERMINAL.includes(stop.status);
                    return (
                      <div
                        key={stop.id}
                        className={`drv-stop-row${stop.id === nextStop?.id ? " drv-stop-row-next" : ""}`}
                        style={{ borderLeftColor: stopBorderColor(stop.status) }}
                      >
                        <div className="drv-stop-head">
                          <span className="drv-stop-seq">#{stop.sequence_number}</span>
                          <StopStatusBadge status={stop.status} />
                          {stop.estimated_arrival_at && (
                            <span className="drv-stop-eta">
                              {formatEta(stop.estimated_arrival_at)}
                            </span>
                          )}
                          {sNavUrl && (
                            <a
                              href={sNavUrl}
                              className="drv-nav-link-sm"
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              🗺
                            </a>
                          )}
                        </div>
                        {!terminal && (
                          <div className="drv-stop-actions">
                            {(stop.status === "pending" || stop.status === "en_route") && (
                              <button
                                className="drv-btn-sm drv-btn-primary"
                                disabled={isActive}
                                onClick={() => onArrive(stop.id)}
                              >
                                Llegar
                              </button>
                            )}
                            {stop.status === "arrived" && (
                              <button
                                className="drv-btn-sm drv-btn-primary"
                                disabled={isActive}
                                onClick={() => setProofStopId(stop.id)}
                              >
                                Completar
                              </button>
                            )}
                            <button
                              className="drv-btn-sm drv-btn-danger"
                              disabled={isActive}
                              onClick={() => setFailStopId(stop.id)}
                            >
                              Falla
                            </button>
                            <button
                              className="drv-btn-sm drv-btn-muted"
                              disabled={isActive}
                              onClick={() => onSkip(stop.id)}
                            >
                              Omitir
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Incident button */}
              {selectedRoute && (
                <div className="drv-incident-row">
                  <button
                    className="drv-btn drv-btn-incident"
                    disabled={incidentLoading}
                    onClick={() =>
                      setIncidentOpenStopId(nextStop?.id ?? "none")
                    }
                  >
                    {incidentLoading ? "Enviando…" : "⚠ Reportar incidencia"}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* ── Modals ───────────────────────────────────────────────────────── */}
      {proofStopId && (
        <ProofModal
          stopId={proofStopId}
          token={token}
          apiBaseUrl={apiBaseUrl}
          proofLoading={sigLoadingThisStop}
          onConfirmSignature={(stopId, dataUrl, signedBy) => {
            onCompleteWithProof(stopId, dataUrl, signedBy);
            setProofStopId(null);
          }}
          onComplete={(stopId) => {
            onComplete(stopId);
            setProofStopId(null);
          }}
          onCancel={() => setProofStopId(null)}
        />
      )}

      {failStopId && (
        <FailModal
          stopId={failStopId}
          loading={failLoadingThisStop}
          onConfirm={(stopId, reason) => {
            onFail(stopId, reason);
            setFailStopId(null);
          }}
          onCancel={() => setFailStopId(null)}
        />
      )}

      {incidentModalOpen && selectedRoute && (
        <IncidentModal
          routeId={selectedRoute.id}
          stopId={
            incidentOpenStopId === "none" ? null : (incidentOpenStopId as string)
          }
          loading={incidentLoading}
          onConfirm={(payload) => {
            onReportIncident(payload);
            setIncidentOpenStopId(null);
          }}
          onCancel={() => setIncidentOpenStopId(null)}
        />
      )}
    </div>
  );
}
