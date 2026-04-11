"use client";

import React, { useState } from "react";

import type {
  IncidentCreateRequest,
  IncidentSeverity,
  IncidentType,
  RouteStopStatus,
  RoutingRoute,
  RoutingRouteStop,
  RouteNextStopResponse,
} from "../lib/api";

// ── Helpers ──────────────────────────────────────────────────────────────────

const STOP_STATUS_LABELS: Record<RouteStopStatus, string> = {
  pending: "Pendiente",
  en_route: "En ruta",
  arrived: "Llegó",
  completed: "Completada",
  failed: "Fallida",
  skipped: "Omitida",
};

const INCIDENT_TYPE_LABELS: Record<IncidentType, string> = {
  access_blocked: "Acceso bloqueado",
  customer_absent: "Cliente ausente",
  customer_rejected: "Cliente rechazó",
  vehicle_issue: "Problema vehículo",
  wrong_address: "Dirección incorrecta",
  damaged_goods: "Mercancía dañada",
  other: "Otro",
};

const INCIDENT_SEVERITY_LABELS: Record<IncidentSeverity, string> = {
  low: "Baja",
  medium: "Media",
  high: "Alta",
  critical: "Crítica",
};

const TERMINAL_STATUSES: RouteStopStatus[] = ["completed", "failed", "skipped"];

function isTerminal(status: RouteStopStatus): boolean {
  return TERMINAL_STATUSES.includes(status);
}

/** Builds a Maps/Waze deep-link from coordinates if available.
 *  Stops in the current API schema do not embed lat/lng — this function
 *  receives them as optional so future enrichment can wire them in. */
function buildNavUrl(lat?: number | null, lng?: number | null): string | null {
  if (lat == null || lng == null) return null;
  // Universal Waze deep link; falls back gracefully on desktop to Maps web.
  return `https://waze.com/ul?ll=${lat},${lng}&navigate=yes`;
}

// ── Sub-components ───────────────────────────────────────────────────────────

type StopStatusBadgeProps = { status: RouteStopStatus };
function StopStatusBadge({ status }: StopStatusBadgeProps) {
  const colors: Record<RouteStopStatus, string> = {
    pending: "bg-gray-100 text-gray-700",
    en_route: "bg-blue-100 text-blue-700",
    arrived: "bg-yellow-100 text-yellow-800",
    completed: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-700",
    skipped: "bg-orange-100 text-orange-700",
  };
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${colors[status]}`}>
      {STOP_STATUS_LABELS[status]}
    </span>
  );
}

// ── Fail modal ───────────────────────────────────────────────────────────────

type FailModalProps = {
  stopId: string;
  onConfirm: (stopId: string, reason: string) => void;
  onCancel: () => void;
  loading: boolean;
};
function FailModal({ stopId, onConfirm, onCancel, loading }: FailModalProps) {
  const [reason, setReason] = useState("");
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-sm rounded-lg bg-white p-6 shadow-xl">
        <h3 className="mb-3 text-base font-semibold text-gray-900">Reportar entrega fallida</h3>
        <label className="mb-1 block text-sm text-gray-700">
          Motivo <span className="text-red-500">*</span>
        </label>
        <textarea
          className="w-full rounded border border-gray-300 p-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
          rows={3}
          maxLength={500}
          placeholder="Describe el motivo de la falla…"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
        <p className="mb-4 text-right text-xs text-gray-400">{reason.length}/500</p>
        <div className="flex gap-2">
          <button
            className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            onClick={onCancel}
            disabled={loading}
          >
            Cancelar
          </button>
          <button
            className="flex-1 rounded bg-red-600 px-3 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50"
            onClick={() => reason.trim() && onConfirm(stopId, reason.trim())}
            disabled={!reason.trim() || loading}
          >
            {loading ? "Guardando…" : "Confirmar falla"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Incident modal ───────────────────────────────────────────────────────────

type IncidentModalProps = {
  routeId: string;
  stopId?: string | null;
  onConfirm: (payload: IncidentCreateRequest) => void;
  onCancel: () => void;
  loading: boolean;
};
function IncidentModal({ routeId, stopId, onConfirm, onCancel, loading }: IncidentModalProps) {
  const [type, setType] = useState<IncidentType>("other");
  const [severity, setSeverity] = useState<IncidentSeverity>("medium");
  const [description, setDescription] = useState("");

  const INCIDENT_TYPES: IncidentType[] = [
    "access_blocked",
    "customer_absent",
    "customer_rejected",
    "vehicle_issue",
    "wrong_address",
    "damaged_goods",
    "other",
  ];
  const SEVERITIES: IncidentSeverity[] = ["low", "medium", "high", "critical"];

  function handleConfirm() {
    if (!description.trim()) return;
    onConfirm({
      route_id: routeId,
      route_stop_id: stopId ?? null,
      type,
      severity,
      description: description.trim(),
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-sm rounded-lg bg-white p-6 shadow-xl">
        <h3 className="mb-4 text-base font-semibold text-gray-900">Reportar incidencia</h3>

        <label className="mb-1 block text-sm text-gray-700">Tipo</label>
        <select
          className="mb-3 w-full rounded border border-gray-300 p-2 text-sm"
          value={type}
          onChange={(e) => setType(e.target.value as IncidentType)}
        >
          {INCIDENT_TYPES.map((t) => (
            <option key={t} value={t}>
              {INCIDENT_TYPE_LABELS[t]}
            </option>
          ))}
        </select>

        <label className="mb-1 block text-sm text-gray-700">Severidad</label>
        <select
          className="mb-3 w-full rounded border border-gray-300 p-2 text-sm"
          value={severity}
          onChange={(e) => setSeverity(e.target.value as IncidentSeverity)}
        >
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>
              {INCIDENT_SEVERITY_LABELS[s]}
            </option>
          ))}
        </select>

        <label className="mb-1 block text-sm text-gray-700">
          Descripción <span className="text-red-500">*</span>
        </label>
        <textarea
          className="w-full rounded border border-gray-300 p-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400"
          rows={3}
          maxLength={500}
          placeholder="Describe la incidencia…"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <p className="mb-4 text-right text-xs text-gray-400">{description.length}/500</p>

        <div className="flex gap-2">
          <button
            className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            onClick={onCancel}
            disabled={loading}
          >
            Cancelar
          </button>
          <button
            className="flex-1 rounded bg-orange-600 px-3 py-2 text-sm font-semibold text-white hover:bg-orange-700 disabled:opacity-50"
            onClick={handleConfirm}
            disabled={!description.trim() || loading}
          >
            {loading ? "Enviando…" : "Reportar"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Stop detail panel ─────────────────────────────────────────────────────────

type StopDetailProps = {
  stop: RoutingRouteStop;
  routeId: string;
  actionLoadingStopId: string | null;
  onArrive: (stopId: string) => void;
  onComplete: (stopId: string) => void;
  onFail: (stopId: string) => void;
  onSkip: (stopId: string) => void;
  onReportIncident: (stopId: string) => void;
};
function StopDetail({
  stop,
  routeId: _routeId,
  actionLoadingStopId,
  onArrive,
  onComplete,
  onFail,
  onSkip,
  onReportIncident,
}: StopDetailProps) {
  const loading = actionLoadingStopId === stop.id;
  const terminal = isTerminal(stop.status);

  // Navigation: stops don't carry lat/lng in the current schema.
  // Button is shown but disabled with a clear explanation.
  const navUrl = buildNavUrl(null, null);
  const navDisabled = navUrl === null;

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-sm font-semibold text-gray-800">Parada #{stop.sequence_number}</span>
        <StopStatusBadge status={stop.status} />
      </div>

      <dl className="mb-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-600">
        <dt className="font-medium">Pedido</dt>
        <dd className="truncate font-mono">{stop.order_id.slice(0, 8)}…</dd>
        {stop.estimated_arrival_at && (
          <>
            <dt className="font-medium">Llegada estimada</dt>
            <dd>{new Date(stop.estimated_arrival_at).toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit" })}</dd>
          </>
        )}
        {stop.arrived_at && (
          <>
            <dt className="font-medium">Llegó</dt>
            <dd>{new Date(stop.arrived_at).toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit" })}</dd>
          </>
        )}
        {stop.failure_reason && (
          <>
            <dt className="font-medium text-red-600">Motivo falla</dt>
            <dd className="text-red-700">{stop.failure_reason}</dd>
          </>
        )}
      </dl>

      {/* Navigation */}
      <div className="mb-3">
        {navDisabled ? (
          <p className="rounded bg-gray-50 px-3 py-2 text-center text-xs text-gray-500">
            Navegación no disponible — coordenadas no incluidas en la respuesta API
          </p>
        ) : (
          <a
            href={navUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="block w-full rounded bg-blue-600 px-3 py-2 text-center text-sm font-semibold text-white hover:bg-blue-700"
          >
            Abrir navegación
          </a>
        )}
      </div>

      {/* Action buttons — only shown for non-terminal stops */}
      {!terminal && (
        <div className="flex flex-wrap gap-2">
          {stop.status !== "arrived" && (
            <button
              className="flex-1 rounded bg-blue-100 px-3 py-2 text-sm font-semibold text-blue-800 hover:bg-blue-200 disabled:opacity-50"
              onClick={() => onArrive(stop.id)}
              disabled={loading}
            >
              {loading ? "…" : "Llegar"}
            </button>
          )}
          {stop.status === "arrived" && (
            <button
              className="flex-1 rounded bg-green-600 px-3 py-2 text-sm font-semibold text-white hover:bg-green-700 disabled:opacity-50"
              onClick={() => onComplete(stop.id)}
              disabled={loading}
            >
              {loading ? "…" : "Completar"}
            </button>
          )}
          {stop.status === "arrived" && (
            <button
              className="flex-1 rounded bg-red-100 px-3 py-2 text-sm font-semibold text-red-800 hover:bg-red-200 disabled:opacity-50"
              onClick={() => onFail(stop.id)}
              disabled={loading}
            >
              {loading ? "…" : "Fallar"}
            </button>
          )}
          {stop.status !== "arrived" && (
            <button
              className="rounded border border-gray-300 px-3 py-2 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-50"
              onClick={() => onSkip(stop.id)}
              disabled={loading}
            >
              {loading ? "…" : "Omitir"}
            </button>
          )}
        </div>
      )}

      {/* Incident report — always available on non-cancelled routes */}
      <button
        className="mt-2 w-full rounded border border-orange-300 px-3 py-2 text-sm text-orange-700 hover:bg-orange-50 disabled:opacity-50"
        onClick={() => onReportIncident(stop.id)}
        disabled={loading}
      >
        Reportar incidencia
      </button>
    </div>
  );
}

// ── Main card props ──────────────────────────────────────────────────────────

export type DriverRoutingCardProps = {
  loading: boolean;
  routes: RoutingRoute[];
  selectedRouteId: string;
  onSelectedRouteIdChange: (id: string) => void;
  selectedRoute: RoutingRoute | null;
  nextStopResponse: RouteNextStopResponse | null;
  nextStopLoading: boolean;
  actionLoadingStopId: string | null;
  incidentLoading: boolean;
  errorMessage: string | null;
  successMessage: string | null;
  onRefresh: () => void;
  onArrive: (stopId: string) => void;
  onComplete: (stopId: string) => void;
  onFail: (stopId: string, reason: string) => void;
  onSkip: (stopId: string) => void;
  onReportIncident: (payload: IncidentCreateRequest) => void;
};

// ── Main card ─────────────────────────────────────────────────────────────────

export function DriverRoutingCard({
  loading,
  routes,
  selectedRouteId,
  onSelectedRouteIdChange,
  selectedRoute,
  nextStopResponse,
  nextStopLoading,
  actionLoadingStopId,
  incidentLoading,
  errorMessage,
  successMessage,
  onRefresh,
  onArrive,
  onComplete,
  onFail,
  onSkip,
  onReportIncident,
}: DriverRoutingCardProps) {
  const [failStopId, setFailStopId] = useState<string | null>(null);
  const [incidentStopId, setIncidentStopId] = useState<string | null>(null);

  // Modal guards
  const failLoadingThisStop = failStopId !== null && actionLoadingStopId === failStopId;

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-base font-bold text-gray-900">Driver — Mis Rutas</h2>
        <button
          className="rounded border border-gray-300 px-3 py-1 text-xs text-gray-600 hover:bg-gray-50 disabled:opacity-50"
          onClick={onRefresh}
          disabled={loading}
        >
          {loading ? "Cargando…" : "Actualizar"}
        </button>
      </div>

      {/* Status messages */}
      {errorMessage && (
        <div className="mb-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">{errorMessage}</div>
      )}
      {successMessage && (
        <div className="mb-3 rounded bg-green-50 px-3 py-2 text-sm text-green-700">{successMessage}</div>
      )}

      {/* Route list */}
      {routes.length === 0 ? (
        <p className="py-6 text-center text-sm text-gray-500">
          {loading ? "Cargando rutas…" : "Sin rutas asignadas para hoy."}
        </p>
      ) : (
        <div className="mb-4">
          <label className="mb-1 block text-xs font-medium text-gray-600">Ruta activa</label>
          <select
            className="w-full rounded border border-gray-300 p-2 text-sm"
            value={selectedRouteId}
            onChange={(e) => onSelectedRouteIdChange(e.target.value)}
          >
            <option value="">— Selecciona una ruta —</option>
            {routes.map((r) => (
              <option key={r.id} value={r.id}>
                {r.service_date} · {r.status} · {r.stops.length} parada{r.stops.length !== 1 ? "s" : ""}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Selected route detail */}
      {selectedRoute && (
        <>
          {/* Next stop banner */}
          <div className="mb-4 rounded-lg bg-blue-50 p-3">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-blue-600">
              Siguiente parada
            </p>
            {nextStopLoading ? (
              <p className="text-sm text-blue-700">Cargando…</p>
            ) : nextStopResponse?.next_stop ? (
              <p className="text-sm text-blue-900">
                #{nextStopResponse.next_stop.sequence_number} ·{" "}
                <StopStatusBadge status={nextStopResponse.next_stop.status} /> ·{" "}
                {nextStopResponse.remaining_stops} restante
                {nextStopResponse.remaining_stops !== 1 ? "s" : ""}
              </p>
            ) : (
              <p className="text-sm text-blue-700">No hay paradas pendientes.</p>
            )}
          </div>

          {/* Stop list */}
          <div className="space-y-3">
            {selectedRoute.stops.length === 0 ? (
              <p className="py-4 text-center text-sm text-gray-500">Esta ruta no tiene paradas.</p>
            ) : (
              selectedRoute.stops.map((stop) => (
                <StopDetail
                  key={stop.id}
                  stop={stop}
                  routeId={selectedRoute.id}
                  actionLoadingStopId={actionLoadingStopId}
                  onArrive={onArrive}
                  onComplete={onComplete}
                  onFail={(stopId) => setFailStopId(stopId)}
                  onSkip={onSkip}
                  onReportIncident={(stopId) => setIncidentStopId(stopId)}
                />
              ))
            )}
          </div>
        </>
      )}

      {/* Fail modal */}
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

      {/* Incident modal */}
      {incidentStopId && selectedRoute && (
        <IncidentModal
          routeId={selectedRoute.id}
          stopId={incidentStopId}
          loading={incidentLoading}
          onConfirm={(payload) => {
            onReportIncident(payload);
            setIncidentStopId(null);
          }}
          onCancel={() => setIncidentStopId(null)}
        />
      )}
    </section>
  );
}
