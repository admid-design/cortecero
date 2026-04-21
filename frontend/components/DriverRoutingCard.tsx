"use client";

import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import {
  APIError,
  formatError,
  createStopProof,
  getProofUploadUrl,
  confirmProofPhoto,
} from "../lib/api";
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
 *  Builds a Waze/Maps deep-link from coordinates embedded in the stop. */
export function buildNavUrl(lat?: number | null, lng?: number | null): string | null {
  if (lat == null || lng == null) return null;
  // Universal Waze deep link; falls back gracefully on desktop to Maps web.
  return `https://waze.com/ul?ll=${lat},${lng}&navigate=yes`;
}

// ── Sub-components ───────────────────────────────────────────────────────────

export type StopStatusBadgeProps = { status: RouteStopStatus };
export function StopStatusBadge({ status }: StopStatusBadgeProps) {
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

export type FailModalProps = {
  stopId: string;
  onConfirm: (stopId: string, reason: string) => void;
  onCancel: () => void;
  loading: boolean;
};
export function FailModal({ stopId, onConfirm, onCancel, loading }: FailModalProps) {
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

export type IncidentModalProps = {
  routeId: string;
  stopId?: string | null;
  onConfirm: (payload: IncidentCreateRequest) => void;
  onCancel: () => void;
  loading: boolean;
};
export function IncidentModal({ routeId, stopId, onConfirm, onCancel, loading }: IncidentModalProps) {
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

  const navUrl = buildNavUrl(stop.customer_lat, stop.customer_lng);
  const navDisabled = navUrl === null;

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-sm font-semibold text-gray-800">Parada #{stop.sequence_number}</span>
        <StopStatusBadge status={stop.status} />
      </div>

      <dl className="mb-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-600">
        <dt className="font-medium">Pedido</dt>
        <dd className="truncate font-mono">{stop.order_id ? stop.order_id.slice(0, 8) + "…" : "—"}</dd>
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
            Navegación no disponible — cliente sin coordenadas
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

// ── Proof Modal (R8-POD-FOTO-UI) — evolución de SignatureModal ───────────────

type ProofTab = "signature" | "photo";
type PhotoFlowState = "idle" | "creating_proof" | "uploading" | "confirming" | "error";

const PHOTO_STATE_LABELS: Record<PhotoFlowState, string> = {
  idle: "Subir foto",
  creating_proof: "Creando registro…",
  uploading: "Subiendo foto…",
  confirming: "Confirmando…",
  error: "Reintentar",
};

export type ProofModalProps = {
  stopId: string;
  token: string | null;
  apiBaseUrl: string;
  proofLoading: boolean;
  /** Pestaña inicial — útil para tests. Por defecto "signature". */
  defaultTab?: ProofTab;
  onConfirmSignature: (stopId: string, signatureDataUrl: string, signedBy: string) => void;
  onComplete: (stopId: string) => void;
  onCancel: () => void;
};

export function ProofModal({
  stopId,
  token,
  proofLoading,
  defaultTab = "signature",
  onConfirmSignature,
  onComplete,
  onCancel,
}: ProofModalProps) {
  const [activeTab, setActiveTab] = useState<ProofTab>(defaultTab);

  // ── Signature state ──────────────────────────────────────────────────────
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [hasSig, setHasSig] = useState(false);

  // Canvas pixel-buffer fix: sync canvas.width from layout width (HAL-001 / mobile)
  useLayoutEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const w = canvas.offsetWidth;
    if (w > 0) canvas.width = w;
  }, []);
  const [signedBy, setSignedBy] = useState("");
  const lastPos = useRef<{ x: number; y: number } | null>(null);

  function getPos(e: React.TouchEvent | React.MouseEvent, canvas: HTMLCanvasElement) {
    const rect = canvas.getBoundingClientRect();
    if ("touches" in e) {
      return { x: e.touches[0].clientX - rect.left, y: e.touches[0].clientY - rect.top };
    }
    return { x: (e as React.MouseEvent).clientX - rect.left, y: (e as React.MouseEvent).clientY - rect.top };
  }
  function startDraw(e: React.TouchEvent | React.MouseEvent) {
    const canvas = canvasRef.current;
    if (!canvas) return;
    e.preventDefault();
    setIsDrawing(true);
    lastPos.current = getPos(e, canvas);
  }
  function draw(e: React.TouchEvent | React.MouseEvent) {
    if (!isDrawing) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    e.preventDefault();
    const ctx = canvas.getContext("2d");
    if (!ctx || !lastPos.current) return;
    const pos = getPos(e, canvas);
    ctx.beginPath();
    ctx.moveTo(lastPos.current.x, lastPos.current.y);
    ctx.lineTo(pos.x, pos.y);
    ctx.strokeStyle = "#111827";
    ctx.lineWidth = 2.5;
    ctx.lineCap = "round";
    ctx.stroke();
    lastPos.current = pos;
    setHasSig(true);
  }
  function stopDraw() { setIsDrawing(false); lastPos.current = null; }
  function clearCanvas() {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    ctx?.clearRect(0, 0, canvas.width, canvas.height);
    setHasSig(false);
  }
  function handleConfirmSignature() {
    const canvas = canvasRef.current;
    if (!canvas || !hasSig) return;
    onConfirmSignature(stopId, canvas.toDataURL("image/png"), signedBy.trim());
  }

  // ── Photo state ──────────────────────────────────────────────────────────
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [photoState, setPhotoState] = useState<PhotoFlowState>("idle");
  const [photoError, setPhotoError] = useState<string | null>(null);

  const photoAvailable = !!token;
  const photoInProgress = photoState !== "idle" && photoState !== "error";

  async function handlePhotoUpload() {
    if (!selectedFile || !token) return;
    setPhotoError(null);

    // Step 1 — create proof (photo-only); 409 = proof already exists → continue
    setPhotoState("creating_proof");
    try {
      await createStopProof(token, stopId, { proof_type: "photo" });
    } catch (err) {
      if (!(err instanceof APIError && err.status === 409)) {
        setPhotoState("error");
        setPhotoError(`Error al crear registro: ${formatError(err)}`);
        return;
      }
    }

    // Step 2 — get presigned upload URL
    let uploadUrl: string;
    let objectKey: string;
    try {
      const urlData = await getProofUploadUrl(token, stopId);
      uploadUrl = urlData.upload_url;
      objectKey = urlData.object_key;
    } catch (err) {
      setPhotoState("error");
      setPhotoError(`Error al obtener URL de subida: ${formatError(err)}`);
      return;
    }

    // Step 3 — compress + PUT directly to R2 (no Authorization header)
    setPhotoState("uploading");
    let blob: Blob;
    try {
      blob = await compressImage(selectedFile);
    } catch {
      blob = selectedFile;
    }
    try {
      const res = await fetch(uploadUrl, {
        method: "PUT",
        body: blob,
        headers: { "Content-Type": "image/jpeg" },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
    } catch (err) {
      setPhotoState("error");
      setPhotoError(`Error al subir foto: ${formatError(err)}`);
      return;
    }

    // Step 4 — confirm photo_url in backend
    setPhotoState("confirming");
    try {
      await confirmProofPhoto(token, stopId, objectKey);
    } catch (err) {
      setPhotoState("error");
      setPhotoError(`Error al confirmar foto: ${formatError(err)}`);
      return;
    }

    // Step 5 — done
    setPhotoState("idle");
    onComplete(stopId);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-sm rounded-xl bg-white p-5 shadow-2xl">
        <h3 className="mb-3 text-base font-semibold text-gray-900">Prueba de entrega</h3>

        {/* Tab bar */}
        <div className="mb-4 flex overflow-hidden rounded-lg border border-gray-200">
          <button
            className={`flex-1 py-2 text-sm font-medium transition-colors ${
              activeTab === "signature"
                ? "bg-gray-900 text-white"
                : "bg-white text-gray-600 hover:bg-gray-50"
            }`}
            onClick={() => setActiveTab("signature")}
          >
            Firma
          </button>
          <button
            className={`flex-1 py-2 text-sm font-medium transition-colors ${
              activeTab === "photo"
                ? "bg-gray-900 text-white"
                : "bg-white text-gray-600 hover:bg-gray-50"
            } disabled:cursor-not-allowed disabled:opacity-40`}
            onClick={() => setActiveTab("photo")}
            disabled={!photoAvailable}
            title={!photoAvailable ? "Sin token de sesión — foto no disponible" : undefined}
          >
            Foto{!photoAvailable ? " (sin conexión)" : ""}
          </button>
        </div>

        {/* ── Signature tab ─────────────────────────────────────────────── */}
        {activeTab === "signature" && (
          <>
            <p className="mb-3 text-xs text-gray-500">Pide al cliente que firme en el recuadro</p>
            <div className="mb-3 overflow-hidden rounded-lg border-2 border-dashed border-gray-300 bg-gray-50">
              <canvas
                ref={canvasRef}
                width={320}
                height={150}
                className="block w-full touch-none"
                style={{ cursor: "crosshair" }}
                onMouseDown={startDraw}
                onMouseMove={draw}
                onMouseUp={stopDraw}
                onMouseLeave={stopDraw}
                onTouchStart={startDraw}
                onTouchMove={draw}
                onTouchEnd={stopDraw}
              />
            </div>
            {hasSig && (
              <button className="mb-3 text-xs text-gray-400 underline" onClick={clearCanvas}>
                Borrar firma
              </button>
            )}
            <label className="mb-1 block text-xs font-medium text-gray-700">
              Nombre del receptor <span className="text-gray-400">(opcional)</span>
            </label>
            <input
              className="mb-4 w-full rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
              placeholder="Ej: María García"
              value={signedBy}
              onChange={(e) => setSignedBy(e.target.value)}
            />
            <button
              className="mb-2 w-full rounded bg-green-600 px-3 py-2 text-sm font-semibold text-white hover:bg-green-700 disabled:opacity-50"
              onClick={handleConfirmSignature}
              disabled={!hasSig || proofLoading}
            >
              {proofLoading ? "Guardando…" : "Completar con firma"}
            </button>
          </>
        )}

        {/* ── Photo tab ─────────────────────────────────────────────────── */}
        {activeTab === "photo" && (
          <>
            <p className="mb-3 text-xs text-gray-500">
              Toma o selecciona una foto de la entrega
            </p>
            <label className="mb-3 flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-gray-300 bg-gray-50 p-4 hover:bg-gray-100">
              <span className="mb-1 text-sm text-gray-600">
                {selectedFile ? selectedFile.name : "Toca para abrir cámara o galería"}
              </span>
              {selectedFile && (
                <span className="text-xs text-gray-400">
                  {(selectedFile.size / 1024).toFixed(0)} KB
                </span>
              )}
              <input
                type="file"
                accept="image/*"
                capture="environment"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0] ?? null;
                  setSelectedFile(f);
                  setPhotoState("idle");
                  setPhotoError(null);
                }}
              />
            </label>

            {photoError && (
              <p className="mb-2 rounded bg-red-50 px-3 py-2 text-xs text-red-700">
                {photoError}
              </p>
            )}

            <button
              className="mb-2 w-full rounded bg-green-600 px-3 py-2 text-sm font-semibold text-white hover:bg-green-700 disabled:opacity-50"
              onClick={handlePhotoUpload}
              disabled={!selectedFile || photoInProgress}
            >
              {PHOTO_STATE_LABELS[photoState]}
            </button>
          </>
        )}

        {/* ── Footer siempre visible ─────────────────────────────────────── */}
        <button
          className="mb-1 w-full rounded border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          onClick={() => onComplete(stopId)}
          disabled={proofLoading || photoInProgress}
        >
          Completar sin prueba
        </button>
        <button
          className="w-full rounded px-3 py-2 text-xs text-gray-400 hover:bg-gray-50"
          onClick={onCancel}
          disabled={proofLoading || photoInProgress}
        >
          Cancelar
        </button>
      </div>
    </div>
  );
}

// ── Image compression helper (R8-POD-FOTO-UI) ────────────────────────────────

export function compressImage(file: File, maxBytes = 500 * 1024): Promise<Blob> {
  return new Promise((resolve, reject) => {
    if (file.size <= maxBytes) {
      resolve(file);
      return;
    }
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      const canvas = document.createElement("canvas");
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        reject(new Error("canvas context unavailable"));
        return;
      }
      ctx.drawImage(img, 0, 0);
      canvas.toBlob(
        (blob) => {
          if (!blob) { reject(new Error("compression failed")); return; }
          resolve(blob);
        },
        "image/jpeg",
        0.75,
      );
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("image load failed")); };
    img.src = url;
  });
}

// ── GPS tracking hook (A3 — GPS-001) ─────────────────────────────────────────

export type GpsPosition = { lat: number; lng: number; heading: number | null };
export type GpsTrackingState = {
  /** true cuando watchPosition está activo */
  active: boolean;
  /** Última posición conocida — null hasta el primer fix */
  position: GpsPosition | null;
};

export function useGpsTracking(
  activeRouteId: string | null,
  token: string | null,
  apiBaseUrl: string,
): GpsTrackingState {
  const watchIdRef = useRef<number | null>(null);
  const [position, setPosition] = useState<GpsPosition | null>(null);
  const [active, setActive] = useState(false);

  const sendPosition = useCallback(
    (routeId: string, lat: number, lng: number, accuracy: number | null, speed: number | null, heading: number | null) => {
      if (!token) return;
      const body = JSON.stringify({
        route_id: routeId,
        lat,
        lng,
        accuracy_m: accuracy,
        speed_kmh: speed != null ? speed * 3.6 : null, // m/s → km/h
        heading,
        recorded_at: new Date().toISOString(),
      });
      // fire-and-forget; navigator.sendBeacon could also work
      fetch(`${apiBaseUrl}/driver/location`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body,
      }).catch(() => {
        // silent — connectivity might be intermittent on a delivery route
      });
    },
    [token, apiBaseUrl],
  );

  useEffect(() => {
    if (!activeRouteId || !token || typeof navigator === "undefined" || !navigator.geolocation) return;

    setActive(true);
    watchIdRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        setPosition({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          heading: pos.coords.heading,
        });
        sendPosition(
          activeRouteId,
          pos.coords.latitude,
          pos.coords.longitude,
          pos.coords.accuracy,
          pos.coords.speed,
          pos.coords.heading,
        );
      },
      () => {
        // ignore errors silently — GPS might be unavailable indoors
      },
      { enableHighAccuracy: true, maximumAge: 15000, timeout: 20000 },
    );

    return () => {
      setActive(false);
      if (watchIdRef.current != null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
        watchIdRef.current = null;
      }
    };
  }, [activeRouteId, token, sendPosition]);

  return { active, position };
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
  proofLoading: boolean;
  errorMessage: string | null;
  successMessage: string | null;
  /** JWT token del driver — usado para enviar posición GPS. */
  token?: string | null;
  /** Base URL de la API — usado por el hook de GPS. */
  apiBaseUrl?: string;
  onRefresh: () => void;
  onArrive: (stopId: string) => void;
  onComplete: (stopId: string) => void;
  onCompleteWithProof: (stopId: string, signatureData: string, signedBy: string) => void;
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
}: DriverRoutingCardProps) {
  const [failStopId, setFailStopId] = useState<string | null>(null);
  const [incidentStopId, setIncidentStopId] = useState<string | null>(null);
  const [signatureStopId, setSignatureStopId] = useState<string | null>(null);

  // A3 — GPS tracking: activo mientras haya ruta in_progress seleccionada
  const gpsRouteId =
    selectedRoute?.status === "in_progress" ? selectedRoute.id : null;
  const { active: gpsActive } = useGpsTracking(gpsRouteId, token, apiBaseUrl);

  const failLoadingThisStop = failStopId !== null && actionLoadingStopId === failStopId;
  const sigLoadingThisStop = signatureStopId !== null && proofLoading;

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-base font-bold text-gray-900">Driver — Mis Rutas</h2>
        <div className="flex items-center gap-2">
          {gpsActive && (
            <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-green-500" />
              GPS activo
            </span>
          )}
          <button
            className="rounded border border-gray-300 px-3 py-1 text-xs text-gray-600 hover:bg-gray-50 disabled:opacity-50"
            onClick={onRefresh}
            disabled={loading}
          >
            {loading ? "Cargando…" : "Actualizar"}
          </button>
        </div>
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
                  onComplete={(stopId) => setSignatureStopId(stopId)}
                  onFail={(stopId) => setFailStopId(stopId)}
                  onSkip={onSkip}
                  onReportIncident={(stopId) => setIncidentStopId(stopId)}
                />
              ))
            )}
          </div>
        </>
      )}

      {/* Proof modal — se abre al pulsar "Completar" (firma + foto + sin prueba) */}
      {signatureStopId && (
        <ProofModal
          stopId={signatureStopId}
          token={token}
          apiBaseUrl={apiBaseUrl}
          proofLoading={sigLoadingThisStop}
          onConfirmSignature={(stopId, dataUrl, signedBy) => {
            onCompleteWithProof(stopId, dataUrl, signedBy);
            setSignatureStopId(null);
          }}
          onComplete={(stopId) => {
            onComplete(stopId);
            setSignatureStopId(null);
          }}
          onCancel={() => setSignatureStopId(null)}
        />
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
