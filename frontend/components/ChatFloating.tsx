"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import type { RoutingRoute, RouteMessageOut } from "../lib/api";
import { getRouteMessages, sendRouteMessage, formatError } from "../lib/api";

type ChatFloatingProps = {
  token: string;
  activeRoutes: RoutingRoute[];
  vehicleNameMap: Record<string, string>;
  driverNameMap: Record<string, string>;
};

const POLL_INTERVAL_MS = 10_000;

function routeLabel(
  r: RoutingRoute,
  vehicleNameMap: Record<string, string>,
  driverNameMap: Record<string, string>,
): string {
  if (r.vehicle_id && vehicleNameMap[r.vehicle_id]) return vehicleNameMap[r.vehicle_id];
  if (r.driver_id && driverNameMap[r.driver_id]) return driverNameMap[r.driver_id].split(" ")[0];
  return r.id.slice(0, 8);
}

export function ChatFloating({
  token,
  activeRoutes,
  vehicleNameMap,
  driverNameMap,
}: ChatFloatingProps) {
  const [open, setOpen] = useState(false);
  const [minimized, setMinimized] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [activeTabId, setActiveTabId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Record<string, RouteMessageOut[]>>({});
  const [tabLoading, setTabLoading] = useState<Record<string, boolean>>({});
  const [inputText, setInputText] = useState("");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Auto-select first tab when routes become available
  useEffect(() => {
    if (activeRoutes.length === 0) return;
    setActiveTabId((prev) => {
      if (prev && activeRoutes.find((r) => r.id === prev)) return prev;
      return activeRoutes[0]!.id;
    });
  }, [activeRoutes]);

  // Load messages for the active tab
  const loadMessages = useCallback(
    async (routeId: string, silent = false) => {
      if (!token || !routeId) return;
      if (!silent) setTabLoading((p) => ({ ...p, [routeId]: true }));
      try {
        const msgs = await getRouteMessages(token, routeId);
        setMessages((p) => ({ ...p, [routeId]: msgs }));
      } catch {
        // silent on poll failure — don't disrupt UX
      } finally {
        if (!silent) setTabLoading((p) => ({ ...p, [routeId]: false }));
      }
    },
    [token],
  );

  // Load on open / tab change
  useEffect(() => {
    if (!open || minimized || !activeTabId) return;
    void loadMessages(activeTabId);
  }, [open, minimized, activeTabId, loadMessages]);

  // Polling every 10 s
  useEffect(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    if (!open || minimized || !activeTabId) return;
    pollRef.current = setInterval(() => void loadMessages(activeTabId, true), POLL_INTERVAL_MS);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [open, minimized, activeTabId, loadMessages]);

  // Scroll to bottom on new messages
  useEffect(() => {
    if (open && !minimized) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, activeTabId, open, minimized]);

  const handleSend = async () => {
    if (!activeTabId || !inputText.trim() || sending) return;
    setSending(true);
    setSendError("");
    const text = inputText.trim();
    setInputText("");
    try {
      const msg = await sendRouteMessage(token, activeTabId, text);
      setMessages((p) => ({
        ...p,
        [activeTabId]: [...(p[activeTabId] ?? []), msg],
      }));
    } catch (e) {
      setSendError(formatError(e));
      setInputText(text); // restore on error
    } finally {
      setSending(false);
    }
  };

  if (activeRoutes.length === 0) return null;

  const activeMessages = activeTabId ? (messages[activeTabId] ?? []) : [];
  const isLoadingTab = activeTabId ? (tabLoading[activeTabId] ?? false) : false;

  return (
    <div className={`mf-chat-float${open ? " open" : ""}${minimized ? " minimized" : ""}`}>
      {/* Toggle button — visible when chat is closed */}
      {!open && (
        <button
          className="mf-chat-toggle"
          onClick={() => {
            setOpen(true);
            setMinimized(false);
          }}
          title="Abrir chat de operaciones"
        >
          💬
          <span className="mf-chat-toggle-label">Chat</span>
          <span className="mf-chat-toggle-count">{activeRoutes.length}</span>
        </button>
      )}

      {/* Chat panel */}
      {open && (
        <div className={`mf-chat-panel${expanded ? " expanded" : ""}`}>
          {/* Header */}
          <div className="mf-chat-header">
            <span className="mf-chat-header-title">💬 Chat operativo</span>
            <div className="mf-chat-header-actions">
              <button
                className="mf-chat-icon-btn"
                onClick={() => setExpanded((v) => !v)}
                title={expanded ? "Reducir" : "Ampliar"}
              >
                {expanded ? "⊡" : "⊞"}
              </button>
              <button
                className="mf-chat-icon-btn"
                onClick={() => setMinimized((v) => !v)}
                title={minimized ? "Expandir" : "Minimizar"}
              >
                {minimized ? "▲" : "▼"}
              </button>
              <button
                className="mf-chat-icon-btn"
                onClick={() => setOpen(false)}
                title="Cerrar"
              >
                ×
              </button>
            </div>
          </div>

          {!minimized && (
            <>
              {/* Route tabs */}
              <div className="mf-chat-tabs">
                {activeRoutes.map((r) => (
                  <button
                    key={r.id}
                    className={`mf-chat-tab${activeTabId === r.id ? " active" : ""}`}
                    onClick={() => setActiveTabId(r.id)}
                    title={r.id}
                  >
                    {routeLabel(r, vehicleNameMap, driverNameMap)}
                  </button>
                ))}
              </div>

              {/* Messages area */}
              <div className="mf-chat-messages">
                {isLoadingTab && (
                  <div className="mf-chat-empty">
                    <div style={{ color: "var(--subtle)", fontSize: 13 }}>Cargando mensajes...</div>
                  </div>
                )}

                {!isLoadingTab && activeMessages.length === 0 && (
                  <div className="mf-chat-empty">
                    <div className="mf-chat-empty-icon">💬</div>
                    <div className="mf-chat-empty-title">Sin mensajes aún</div>
                    <div className="mf-chat-empty-sub">
                      Escribe el primer mensaje a esta ruta
                    </div>
                  </div>
                )}

                {!isLoadingTab &&
                  activeMessages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`mf-chat-msg${msg.author_role === "dispatcher" ? " dispatcher" : " driver"}`}
                    >
                      <div className="mf-chat-msg-meta">
                        <span className="mf-chat-msg-role">
                          {msg.author_role === "dispatcher" ? "Dispatcher" : "Conductor"}
                        </span>
                        <span className="mf-chat-msg-time">{msg.created_at.slice(11, 16)}</span>
                      </div>
                      <div className="mf-chat-msg-body">{msg.body}</div>
                    </div>
                  ))}
                <div ref={messagesEndRef} />
              </div>

              {/* Send error */}
              {sendError && <div className="mf-chat-error">⚠️ {sendError}</div>}

              {/* Input row */}
              <div className="mf-chat-input-row">
                <input
                  className="mf-chat-input"
                  type="text"
                  placeholder="Mensaje..."
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      void handleSend();
                    }
                  }}
                  disabled={sending}
                  maxLength={2000}
                />
                <button
                  className="mf-chat-send-btn"
                  onClick={() => void handleSend()}
                  disabled={sending || !inputText.trim()}
                  title="Enviar"
                >
                  {sending ? "…" : "➤"}
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
