"use client";

/**
 * useRouteStream — R8-SSE-FE
 *
 * Hook que abre una conexión SSE a GET /routes/{id}/stream?token=...
 * y llama a `onEvent` por cada evento recibido.
 *
 * Fallback automático a polling si SSE falla MAX_RETRIES veces seguidas:
 *   1. Reintenta la conexión SSE hasta MAX_RETRIES veces con RETRY_DELAY_MS entre intentos.
 *   2. Tras MAX_RETRIES fallos, entra en modo degradado: activa el intervalo de
 *      polling con onFallbackPoll y programa un reintento SSE tras DEGRADED_RECONNECT_MS.
 *   3. Si SSE vuelve a conectarse, cancela el polling y sale del modo degradado.
 *
 * Limitación conocida (REALTIME-001): el backend usa asyncio.Queue in-process.
 * En despliegue multi-worker (gunicorn) los eventos pueden no llegar al worker
 * que tiene la conexión SSE abierta. Fix R9: Redis pub/sub.
 */

import { useEffect, useRef, useState } from "react";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

/** Max consecutive SSE errors before entering degraded (fallback) mode. */
const MAX_RETRIES = 3;
/** Delay between SSE reconnect retries (ms). */
const RETRY_DELAY_MS = 2_000;
/** How long to wait before attempting SSE reconnection when degraded (ms). */
const DEGRADED_RECONNECT_MS = 60_000;

/** SSE event names published by the backend (REALTIME-001, B2, B3, B4). */
const STREAM_EVENT_TYPES = [
  "stop_status_changed",
  "driver_position_updated",
  "chat_message",
  "stop_added",
  "stop_removed",
  "delay_alert",
] as const;

export type StreamEventType = (typeof STREAM_EVENT_TYPES)[number];

export interface UseRouteStreamOptions {
  /** UUID of the route to stream. Empty string disables the stream. */
  routeId: string;
  /** JWT token — passed as ?token= query param (provisional B1 auth). */
  token: string;
  /** When false the stream is not opened. Equivalent to polling disabled. */
  enabled: boolean;
  /**
   * Called for every SSE event received.
   * `type` is the SSE event name (e.g. "driver_position_updated").
   * `data` is the parsed JSON payload.
   * Use a stable reference (useCallback) to avoid unnecessary reconnects.
   */
  onEvent?: (type: StreamEventType, data: unknown) => void;
  /**
   * Called on each polling tick when SSE is in degraded mode.
   * Should perform a single API fetch equivalent to what SSE would provide.
   * Use a stable reference (useCallback) to avoid unnecessary interval resets.
   */
  onFallbackPoll?: () => void;
  /** Fallback polling interval when degraded (ms). Default: 30 000. */
  fallbackIntervalMs?: number;
}

export interface UseRouteStreamResult {
  /** True while the EventSource connection is open and healthy. */
  connected: boolean;
  /**
   * True when SSE has failed MAX_RETRIES times and we have fallen back to polling.
   * Useful to show a visual indicator of degraded mode in the UI.
   */
  degraded: boolean;
}

export function useRouteStream({
  routeId,
  token,
  enabled,
  onEvent,
  onFallbackPoll,
  fallbackIntervalMs = 30_000,
}: UseRouteStreamOptions): UseRouteStreamResult {
  const [connected, setConnected] = useState(false);
  const [degraded, setDegraded] = useState(false);

  // Stable refs for callbacks — changes don't re-open the stream.
  const onEventRef = useRef(onEvent);
  const onFallbackPollRef = useRef(onFallbackPoll);
  onEventRef.current = onEvent;
  onFallbackPollRef.current = onFallbackPoll;

  // Internal mutable state shared by all closures in the effect.
  const internalRef = useRef({
    es: null as EventSource | null,
    retries: 0,
    isDegraded: false,
    isDestroyed: false,
    fallbackTimer: null as ReturnType<typeof setInterval> | null,
    retryTimer: null as ReturnType<typeof setTimeout> | null,
  });

  useEffect(() => {
    // EventSource is a browser-only API — guard for SSR.
    if (typeof EventSource === "undefined") return;

    const s = internalRef.current;
    s.isDestroyed = false;
    s.retries = 0;
    s.isDegraded = false;

    // Clear any leftover timers from a previous render cycle.
    if (s.fallbackTimer) { clearInterval(s.fallbackTimer); s.fallbackTimer = null; }
    if (s.retryTimer) { clearTimeout(s.retryTimer); s.retryTimer = null; }
    if (s.es) { s.es.close(); s.es = null; }

    const cleanup = () => {
      s.isDestroyed = true;
      if (s.es) { s.es.close(); s.es = null; }
      if (s.fallbackTimer) { clearInterval(s.fallbackTimer); s.fallbackTimer = null; }
      if (s.retryTimer) { clearTimeout(s.retryTimer); s.retryTimer = null; }
      setConnected(false);
    };

    if (!enabled || !routeId || !token) {
      setConnected(false);
      setDegraded(false);
      return cleanup;
    }

    // --- Internal helpers (hoisted via function declarations) ---

    function scheduleRetry(delayMs: number): void {
      if (s.retryTimer) clearTimeout(s.retryTimer);
      s.retryTimer = setTimeout(() => {
        s.retryTimer = null;
        if (!s.isDestroyed) connect();
      }, delayMs);
    }

    function enterDegraded(): void {
      if (s.isDegraded || s.isDestroyed) return;
      s.isDegraded = true;
      setDegraded(true);
      setConnected(false);
      // Immediate first fallback poll.
      onFallbackPollRef.current?.();
      // Periodic fallback poll.
      if (!s.fallbackTimer) {
        s.fallbackTimer = setInterval(() => {
          onFallbackPollRef.current?.();
        }, fallbackIntervalMs);
      }
      // Schedule SSE reconnect attempt.
      scheduleRetry(DEGRADED_RECONNECT_MS);
    }

    function exitDegraded(): void {
      if (!s.isDegraded) return;
      s.isDegraded = false;
      setDegraded(false);
      if (s.fallbackTimer) { clearInterval(s.fallbackTimer); s.fallbackTimer = null; }
    }

    function connect(): void {
      if (s.isDestroyed) return;
      if (s.es) { s.es.close(); s.es = null; }

      const url =
        `${API_BASE}/routes/${encodeURIComponent(routeId)}/stream` +
        `?token=${encodeURIComponent(token)}`;

      const es = new EventSource(url);
      s.es = es;

      es.onopen = () => {
        if (s.isDestroyed) { es.close(); return; }
        s.retries = 0;
        setConnected(true);
        exitDegraded();
      };

      es.onerror = () => {
        if (s.isDestroyed) return;
        es.close();
        s.es = null;
        setConnected(false);
        s.retries += 1;
        if (s.retries >= MAX_RETRIES) {
          enterDegraded();
        } else {
          scheduleRetry(RETRY_DELAY_MS);
        }
      };

      for (const eventType of STREAM_EVENT_TYPES) {
        es.addEventListener(eventType, (ev: MessageEvent) => {
          if (s.isDestroyed) return;
          try {
            const data = JSON.parse(ev.data as string) as unknown;
            onEventRef.current?.(eventType, data);
          } catch {
            // Malformed JSON — ignore silently.
          }
        });
      }
    }

    connect();
    return cleanup;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, routeId, token, fallbackIntervalMs]);

  return { connected, degraded };
}
