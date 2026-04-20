"use client";

import React, { useState, useEffect, useCallback } from "react";
import type { Order, Customer, DriverOut, DashboardSummary, RoutingRoute, OrderImportResult } from "../lib/api";
import {
  listOrders,
  listAdminCustomers,
  listDrivers,
  getDailySummary,
  listRoutes,
  importOrdersXlsx,
} from "../lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

export type SidebarSection =
  | "routes"
  | "planner"
  | "orders"
  | "customers"
  | "drivers"
  | "insights"
  | "settings";

interface GlobalShellProps {
  activeSection: SidebarSection;
  onNavigate: (s: SidebarSection) => void;
  canManageRouting?: boolean;
  isAdmin?: boolean;
  onLogout: () => void;
  children: React.ReactNode;
}

// ── Design tokens ─────────────────────────────────────────────────────────────

const C = {
  accent: "#4353ff",
  accentBg: "#eef1ff",
  text: "#1a1d23",
  muted: "#6b7280",
  subtle: "#9ca3af",
  border: "#e8e8e8",
  surface: "#ffffff",
  bg: "#f7f8fa",
  danger: "#dc2626",
  success: "#16a34a",
  warning: "#d97706",
};

// ── Icons (SVG 20px, outline) ─────────────────────────────────────────────────

const Ico = {
  routes: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="5" cy="6" r="2" /><circle cx="19" cy="18" r="2" />
      <path d="M5 8v3a1 1 0 0 0 1 1h7a1 1 0 0 1 1 1v3" />
      <path d="M14 6h-3a1 1 0 0 0-1 1v3" />
    </svg>
  ),
  planner: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
      <line x1="8" y1="14" x2="8" y2="14" strokeWidth="2" /><line x1="12" y1="14" x2="12" y2="14" strokeWidth="2" />
    </svg>
  ),
  orders: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2" />
      <rect x="9" y="3" width="6" height="4" rx="1" />
      <line x1="9" y1="12" x2="15" y2="12" /><line x1="9" y1="16" x2="13" y2="16" />
    </svg>
  ),
  customers: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  ),
  drivers: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="2" />
      <line x1="12" y1="10" x2="12" y2="3" />
      <line x1="7.2" y1="14.8" x2="3.5" y2="17.5" />
      <line x1="16.8" y1="14.8" x2="20.5" y2="17.5" />
    </svg>
  ),
  insights: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
      <line x1="3" y1="20" x2="21" y2="20" />
    </svg>
  ),
  settings: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  ),
  logout: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  ),
};

// ── Nav item config ───────────────────────────────────────────────────────────

interface NavItem {
  id: SidebarSection;
  label: string;
  icon: React.ReactNode;
  adminOnly?: boolean;
  routingOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { id: "routes",    label: "Rutas",       icon: Ico.routes    },
  { id: "planner",   label: "Planificador", icon: Ico.planner,  routingOnly: true },
  { id: "orders",    label: "Pedidos",     icon: Ico.orders    },
  { id: "customers", label: "Clientes",    icon: Ico.customers },
  { id: "drivers",   label: "Conductores", icon: Ico.drivers   },
  { id: "insights",  label: "Insights",   icon: Ico.insights  },
  { id: "settings",  label: "Ajustes",    icon: Ico.settings, adminOnly: true },
];

// ── GlobalShell ───────────────────────────────────────────────────────────────

export function GlobalShell({
  activeSection,
  onNavigate,
  canManageRouting = false,
  isAdmin = false,
  onLogout,
  children,
}: GlobalShellProps) {
  const visibleItems = NAV_ITEMS.filter((item) => {
    if (item.adminOnly && !isAdmin) return false;
    if (item.routingOnly && !canManageRouting) return false;
    return true;
  });

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: C.bg }}>
      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <aside
        style={{
          width: 80,
          flexShrink: 0,
          height: "100vh",
          background: C.surface,
          borderRight: `1px solid ${C.border}`,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          paddingTop: 14,
          paddingBottom: 14,
          gap: 2,
          zIndex: 200,
        }}
      >
        {/* Logo */}
        <div
          style={{
            width: 38,
            height: 38,
            borderRadius: 10,
            background: C.accent,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            marginBottom: 18,
            flexShrink: 0,
          }}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path d="M3 7h7l2 10 4-14 2 4h3" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>

        {/* Nav items */}
        {visibleItems.map((item) => {
          const active = activeSection === item.id;
          return (
            <button
              key={item.id}
              title={item.label}
              onClick={() => onNavigate(item.id)}
              style={{
                width: 58,
                height: 50,
                borderRadius: 10,
                border: "none",
                cursor: "pointer",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: 3,
                fontSize: 9,
                fontWeight: 600,
                letterSpacing: "0.02em",
                background: active ? C.accentBg : "transparent",
                color: active ? C.accent : C.muted,
                transition: "background 0.12s, color 0.12s",
                outline: "none",
              }}
              onMouseEnter={(e) => {
                if (!active) (e.currentTarget as HTMLButtonElement).style.background = "#f5f6f8";
              }}
              onMouseLeave={(e) => {
                if (!active) (e.currentTarget as HTMLButtonElement).style.background = "transparent";
              }}
            >
              {item.icon}
              <span style={{ lineHeight: 1.1 }}>{item.label}</span>
            </button>
          );
        })}

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Logout */}
        <button
          title="Cerrar sesión"
          onClick={onLogout}
          style={{
            width: 58,
            height: 50,
            borderRadius: 10,
            border: "none",
            cursor: "pointer",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 3,
            fontSize: 9,
            fontWeight: 600,
            background: "transparent",
            color: C.muted,
            transition: "background 0.12s, color 0.12s",
            outline: "none",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = "#fff0f0";
            (e.currentTarget as HTMLButtonElement).style.color = C.danger;
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = "transparent";
            (e.currentTarget as HTMLButtonElement).style.color = C.muted;
          }}
        >
          {Ico.logout}
          <span style={{ lineHeight: 1.1 }}>Salir</span>
        </button>
      </aside>

      {/* ── Main content ─────────────────────────────────────────────────── */}
      <main
        style={{
          flex: 1,
          height: "100vh",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
          minWidth: 0,
        }}
      >
        {children}
      </main>
    </div>
  );
}

// ── Shared section UI helpers ─────────────────────────────────────────────────

function SectionPage({
  title,
  subtitle,
  action,
  children,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: C.bg }}>
      {/* Header */}
      <div
        style={{
          background: C.surface,
          borderBottom: `1px solid ${C.border}`,
          padding: "0 28px",
          height: 58,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexShrink: 0,
        }}
      >
        <div>
          <div style={{ fontSize: 18, fontWeight: 700, color: C.text, lineHeight: 1.2 }}>{title}</div>
          {subtitle && <div style={{ fontSize: 12, color: C.muted, marginTop: 1 }}>{subtitle}</div>}
        </div>
        {action && <div>{action}</div>}
      </div>
      {/* Content */}
      <div style={{ flex: 1, overflow: "auto", padding: "24px 28px" }}>{children}</div>
    </div>
  );
}

function PrimaryBtn({ children, onClick }: { children: React.ReactNode; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: C.accent,
        color: "#fff",
        border: "none",
        borderRadius: 8,
        padding: "8px 16px",
        fontSize: 13,
        fontWeight: 600,
        cursor: "pointer",
        display: "flex",
        alignItems: "center",
        gap: 6,
      }}
    >
      {children}
    </button>
  );
}

function DataTable({
  columns,
  rows,
  empty,
  onRowClick,
}: {
  columns: string[];
  rows: React.ReactNode[][];
  empty?: React.ReactNode;
  onRowClick?: (index: number) => void;
}) {
  return (
    <div
      style={{
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: 10,
        overflow: "hidden",
      }}
    >
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ background: "#f5f6f8" }}>
            {columns.map((col) => (
              <th
                key={col}
                style={{
                  textAlign: "left",
                  padding: "10px 16px",
                  fontSize: 11,
                  fontWeight: 600,
                  color: C.muted,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  borderBottom: `1px solid ${C.border}`,
                }}
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              onClick={onRowClick ? () => onRowClick(i) : undefined}
              style={{
                borderBottom: i < rows.length - 1 ? `1px solid #f0f0f0` : "none",
                cursor: onRowClick ? "pointer" : "default",
                transition: "background 0.1s",
              }}
              onMouseEnter={onRowClick ? (e) => { (e.currentTarget as HTMLElement).style.background = "#f9fafb"; } : undefined}
              onMouseLeave={onRowClick ? (e) => { (e.currentTarget as HTMLElement).style.background = ""; } : undefined}
            >
              {row.map((cell, j) => (
                <td key={j} style={{ padding: "12px 16px", color: C.text, verticalAlign: "middle" }}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && (
        <div
          style={{
            padding: "72px 0",
            textAlign: "center",
            color: C.subtle,
            fontSize: 14,
          }}
        >
          {empty ?? "Sin datos"}
        </div>
      )}
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const map: Record<string, { bg: string; color: string; label: string }> = {
    eligible:           { bg: "#dcfce7", color: "#15803d", label: "Elegible" },
    restricted:         { bg: "#fef3c7", color: "#92400e", label: "Restringido" },
    pending:            { bg: "#f3f4f6", color: "#374151", label: "Pendiente" },
    planned:            { bg: "#dbeafe", color: "#1e40af", label: "Planificado" },
    dispatched:         { bg: "#e0e7ff", color: "#3730a3", label: "Despachado" },
    in_progress:        { bg: "#fef3c7", color: "#92400e", label: "En ruta" },
    completed:          { bg: "#dcfce7", color: "#15803d", label: "Completado" },
    cancelled:          { bg: "#fee2e2", color: "#991b1b", label: "Cancelado" },
    ready_for_planning: { bg: "#dbeafe", color: "#1e40af", label: "Listo" },
  };
  const s = map[status] ?? { bg: "#f3f4f6", color: "#374151", label: status };
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: 99,
        fontSize: 11,
        fontWeight: 600,
        background: s.bg,
        color: s.color,
      }}
    >
      {s.label}
    </span>
  );
}

function Skeleton({ width = "100%", height = 16 }: { width?: string | number; height?: number }) {
  return (
    <div
      style={{
        width,
        height,
        borderRadius: 4,
        background: "linear-gradient(90deg, #f0f0f0 25%, #e8e8e8 50%, #f0f0f0 75%)",
        backgroundSize: "200% 100%",
        animation: "shimmer 1.2s infinite",
      }}
    />
  );
}

// ── Toast helper ─────────────────────────────────────────────────────────────

function useToast() {
  const [msg, setMsg] = useState("");
  const show = useCallback((text: string) => {
    setMsg(text);
    setTimeout(() => setMsg(""), 3000);
  }, []);
  const el = msg ? (
    <div
      style={{
        position: "fixed",
        bottom: 24,
        left: "50%",
        transform: "translateX(-50%)",
        background: C.text,
        color: "#fff",
        padding: "10px 20px",
        borderRadius: 8,
        fontSize: 13,
        fontWeight: 500,
        zIndex: 9999,
        pointerEvents: "none",
        boxShadow: "0 4px 16px rgba(0,0,0,0.18)",
      }}
    >
      {msg}
    </div>
  ) : null;
  return { show, el };
}

// ── DetailPanel ───────────────────────────────────────────────────────────────

function DetailPanel({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: 10,
        padding: "18px 20px",
        marginBottom: 20,
        position: "relative",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 14,
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 700, color: C.text }}>{title}</div>
        <button
          onClick={onClose}
          style={{
            border: "none",
            background: "transparent",
            cursor: "pointer",
            fontSize: 18,
            color: C.muted,
            lineHeight: 1,
            padding: "0 2px",
          }}
        >
          ×
        </button>
      </div>
      {children}
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: "flex", gap: 12, marginBottom: 8, fontSize: 13 }}>
      <span style={{ color: C.muted, width: 120, flexShrink: 0 }}>{label}</span>
      <span style={{ color: C.text }}>{value}</span>
    </div>
  );
}

// ── OrderImportModal ──────────────────────────────────────────────────────────

function OrderImportModal({
  token,
  onClose,
  onSuccess,
}: {
  token: string;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const [file, setFile] = useState<File | null>(null);
  const [serviceDate, setServiceDate] = useState(today);
  const [phase, setPhase] = useState<"idle" | "loading" | "result">("idle");
  const [result, setResult] = useState<OrderImportResult | null>(null);
  const [importError, setImportError] = useState("");

  const handleImport = async () => {
    if (!file) return;
    setPhase("loading");
    setImportError("");
    try {
      const res = await importOrdersXlsx(token, file, serviceDate);
      setResult(res);
      setPhase("result");
      if (res.imported > 0) onSuccess();
    } catch (e) {
      setImportError(String(e));
      setPhase("idle");
    }
  };

  const overlayStyle: React.CSSProperties = {
    position: "fixed",
    inset: 0,
    background: "rgba(0,0,0,0.45)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1000,
  };

  const boxStyle: React.CSSProperties = {
    background: C.surface,
    borderRadius: 14,
    padding: "28px 28px 24px",
    width: 440,
    maxWidth: "92vw",
    boxShadow: "0 8px 32px rgba(0,0,0,0.18)",
    display: "flex",
    flexDirection: "column",
    gap: 20,
  };

  const labelStyle: React.CSSProperties = {
    fontSize: 12,
    fontWeight: 600,
    color: C.muted,
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    marginBottom: 6,
    display: "block",
  };

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "9px 12px",
    borderRadius: 8,
    border: `1px solid ${C.border}`,
    fontSize: 13,
    color: C.text,
    background: C.bg,
    outline: "none",
    boxSizing: "border-box",
  };

  return (
    <div style={overlayStyle} onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={boxStyle}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: C.text }}>Importar pedidos</div>
          <button
            onClick={onClose}
            style={{ background: "none", border: "none", cursor: "pointer", fontSize: 20, color: C.muted, lineHeight: 1 }}
            aria-label="Cerrar"
          >
            ×
          </button>
        </div>

        {phase !== "result" && (
          <>
            {/* File picker */}
            <div>
              <label style={labelStyle}>Fichero (.xlsx o .csv)</label>
              <input
                type="file"
                accept=".xlsx,.csv"
                disabled={phase === "loading"}
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                style={{ ...inputStyle, cursor: "pointer" }}
              />
              {file && (
                <div style={{ marginTop: 6, fontSize: 12, color: C.muted }}>
                  {file.name} · {(file.size / 1024).toFixed(1)} KB
                </div>
              )}
            </div>

            {/* Date picker */}
            <div>
              <label style={labelStyle}>Fecha de servicio</label>
              <input
                type="date"
                value={serviceDate}
                disabled={phase === "loading"}
                onChange={(e) => setServiceDate(e.target.value)}
                style={inputStyle}
              />
            </div>

            {/* Error */}
            {importError && (
              <div style={{ padding: "10px 14px", background: "#fee2e2", borderRadius: 8, color: C.danger, fontSize: 13 }}>
                {importError}
              </div>
            )}

            {/* Actions */}
            <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
              <button
                onClick={onClose}
                disabled={phase === "loading"}
                style={{
                  padding: "9px 16px", borderRadius: 8, border: `1px solid ${C.border}`,
                  background: C.surface, fontSize: 13, cursor: "pointer", color: C.text,
                }}
              >
                Cancelar
              </button>
              <button
                onClick={handleImport}
                disabled={!file || phase === "loading"}
                style={{
                  padding: "9px 18px", borderRadius: 8, border: "none",
                  background: !file || phase === "loading" ? C.border : C.accent,
                  color: "#fff", fontSize: 13, fontWeight: 600,
                  cursor: !file || phase === "loading" ? "not-allowed" : "pointer",
                  display: "flex", alignItems: "center", gap: 8,
                }}
              >
                {phase === "loading" ? (
                  <>
                    <span style={{ display: "inline-block", width: 14, height: 14, border: "2px solid rgba(255,255,255,0.4)", borderTopColor: "#fff", borderRadius: "50%", animation: "spin 0.7s linear infinite" }} />
                    Importando…
                  </>
                ) : "Importar"}
              </button>
            </div>
          </>
        )}

        {phase === "result" && result && (
          <>
            {/* Summary */}
            <div style={{ display: "flex", gap: 12 }}>
              <div style={{ flex: 1, background: result.imported > 0 ? "#f0fdf4" : C.bg, borderRadius: 10, padding: "14px 16px", textAlign: "center" }}>
                <div style={{ fontSize: 28, fontWeight: 700, color: result.imported > 0 ? C.success : C.muted }}>{result.imported}</div>
                <div style={{ fontSize: 12, color: C.muted, marginTop: 2 }}>importados</div>
              </div>
              <div style={{ flex: 1, background: result.skipped > 0 ? "#fffbeb" : C.bg, borderRadius: 10, padding: "14px 16px", textAlign: "center" }}>
                <div style={{ fontSize: 28, fontWeight: 700, color: result.skipped > 0 ? C.warning : C.muted }}>{result.skipped}</div>
                <div style={{ fontSize: 12, color: C.muted, marginTop: 2 }}>saltados</div>
              </div>
            </div>

            {/* Update notice */}
            {result.imported > 0 && (
              <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 14px", background: "#f0fdf4", borderRadius: 8, fontSize: 13, color: C.success }}>
                <span>✓</span>
                <span>La lista de pedidos se ha actualizado</span>
              </div>
            )}

            {/* Errors */}
            {result.errors.length > 0 && (
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: C.danger, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  Errores ({result.errors.length})
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 4, maxHeight: 140, overflowY: "auto" }}>
                  {result.errors.map((e, i) => (
                    <div key={i} style={{ fontSize: 12, padding: "6px 10px", background: "#fee2e2", borderRadius: 6, color: C.danger }}>
                      Fila {e.row}: {e.reason}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Warnings */}
            {result.warnings.length > 0 && (
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: C.warning, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  Avisos ({result.warnings.length})
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 4, maxHeight: 140, overflowY: "auto" }}>
                  {result.warnings.map((w, i) => (
                    <div key={i} style={{ fontSize: 12, padding: "6px 10px", background: "#fffbeb", borderRadius: 6, color: C.warning }}>
                      Fila {w.row}: {w.reason}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Close */}
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button
                onClick={onClose}
                style={{
                  padding: "9px 18px", borderRadius: 8, border: "none",
                  background: C.accent, color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer",
                }}
              >
                Cerrar
              </button>
            </div>
          </>
        )}
      </div>

      {/* Keyframe for spinner */}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// ── OrdersSection ─────────────────────────────────────────────────────────────

export function OrdersSection({ token }: { token: string }) {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [showImportModal, setShowImportModal] = useState(false);
  const toast = useToast();

  const today = new Date().toISOString().slice(0, 10);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listOrders(token, today);
      setOrders(res.items ?? []);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [token, today]);

  useEffect(() => { void load(); }, [load]);

  const filtered = orders.filter((o) => {
    const q = search.toLowerCase();
    return (
      (o.external_ref ?? "").toLowerCase().includes(q) ||
      o.id.toLowerCase().includes(q) ||
      o.status.toLowerCase().includes(q)
    );
  });

  const cols = ["Referencia", "Estado", "Zona", "Peso (kg)", "Fecha servicio"];

  const rows = filtered.map((o) => [
    <span style={{ fontFamily: "monospace", fontSize: 12, color: C.muted }}>{o.external_ref || o.id.slice(0, 8)}</span>,
    <StatusPill status={o.status} />,
    <span style={{ color: C.muted, fontSize: 12 }}>{o.zone_id.slice(0, 8)}</span>,
    <span>{o.total_weight_kg != null ? `${o.total_weight_kg} kg` : "—"}</span>,
    <span style={{ color: C.muted }}>{o.service_date}</span>,
  ]);

  return (
    <SectionPage
      title="Pedidos"
      subtitle={`${orders.length} pedido${orders.length !== 1 ? "s" : ""} · ${today}`}
      action={
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={() => setShowImportModal(true)}
            style={{
              padding: "8px 14px",
              borderRadius: 8,
              border: `1px solid ${C.border}`,
              background: C.surface,
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
              color: C.text,
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            ↑ Importar XLSX
          </button>
          <PrimaryBtn onClick={() => toast.show("Creación de pedidos disponible en la próxima versión")}>+ Nuevo pedido</PrimaryBtn>
        </div>
      }
    >
      {toast.el}
      {showImportModal && (
        <OrderImportModal
          token={token}
          onClose={() => setShowImportModal(false)}
          onSuccess={() => { void load(); }}
        />
      )}
      {error && (
        <div style={{ padding: "12px 16px", background: "#fee2e2", borderRadius: 8, color: C.danger, marginBottom: 16, fontSize: 13 }}>
          {error}
        </div>
      )}
      {selectedOrder && (
        <DetailPanel
          title={`Pedido ${selectedOrder.external_ref || selectedOrder.id.slice(0, 8).toUpperCase()}`}
          onClose={() => setSelectedOrder(null)}
        >
          <DetailRow label="ID" value={<span style={{ fontFamily: "monospace", fontSize: 12 }}>{selectedOrder.id}</span>} />
          <DetailRow label="Referencia" value={selectedOrder.external_ref || "—"} />
          <DetailRow label="Estado" value={<StatusPill status={selectedOrder.status} />} />
          <DetailRow label="Fecha servicio" value={selectedOrder.service_date} />
          <DetailRow label="Zona" value={selectedOrder.zone_id.slice(0, 8)} />
          <DetailRow label="Peso" value={selectedOrder.total_weight_kg != null ? `${selectedOrder.total_weight_kg} kg` : "—"} />
          {selectedOrder.operational_state && (
            <DetailRow label="Estado operativo" value={<StatusPill status={selectedOrder.operational_state} />} />
          )}
        </DetailPanel>
      )}
      <div style={{ marginBottom: 16 }}>
        <input
          type="search"
          placeholder="Buscar pedidos…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            width: 280,
            padding: "8px 14px",
            borderRadius: 8,
            border: `1px solid ${C.border}`,
            fontSize: 13,
            outline: "none",
            background: C.surface,
            color: C.text,
          }}
        />
      </div>
      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[1, 2, 3, 4].map((i) => <Skeleton key={i} height={44} />)}
        </div>
      ) : (
        <DataTable
          columns={cols}
          rows={rows}
          onRowClick={(i) => {
            const o = filtered[i];
            if (o) setSelectedOrder(selectedOrder?.id === o.id ? null : o);
          }}
          empty={
            <div>
              <div style={{ fontSize: 36, marginBottom: 12 }}>📦</div>
              <div style={{ fontSize: 15, fontWeight: 600, color: C.text, marginBottom: 4 }}>Sin pedidos hoy</div>
              <div style={{ fontSize: 13, color: C.muted }}>Los pedidos de hoy aparecerán aquí</div>
            </div>
          }
        />
      )}
    </SectionPage>
  );
}

// ── CustomersSection ──────────────────────────────────────────────────────────

export function CustomersSection({ token }: { token: string }) {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const toast = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listAdminCustomers(token, {});
      setCustomers(res.items ?? []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { void load(); }, [load]);

  const filtered = customers.filter((c) =>
    c.name.toLowerCase().includes(search.toLowerCase())
  );

  const cols = ["Cliente", "Prioridad", "Estado", "Creado"];
  const rows = filtered.map((c) => [
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <div
        style={{
          width: 30,
          height: 30,
          borderRadius: "50%",
          background: C.accentBg,
          color: C.accent,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 11,
          fontWeight: 700,
          flexShrink: 0,
        }}
      >
        {c.name.slice(0, 2).toUpperCase()}
      </div>
      <span style={{ fontWeight: 500 }}>{c.name}</span>
    </div>,
    <span style={{ color: C.muted }}>{c.priority}</span>,
    <StatusPill status={c.active ? "eligible" : "cancelled"} />,
    <span style={{ color: C.muted, fontSize: 12 }}>{c.created_at?.slice(0, 10) ?? "—"}</span>,
  ]);

  return (
    <SectionPage
      title="Clientes"
      subtitle={`${customers.length} cliente${customers.length !== 1 ? "s" : ""}`}
      action={<PrimaryBtn onClick={() => toast.show("Gestión de clientes disponible en Admin → Clientes")}>+ Añadir cliente</PrimaryBtn>}
    >
      {toast.el}
      {selectedCustomer && (
        <DetailPanel
          title={selectedCustomer.name}
          onClose={() => setSelectedCustomer(null)}
        >
          <DetailRow label="ID" value={<span style={{ fontFamily: "monospace", fontSize: 12 }}>{selectedCustomer.id}</span>} />
          <DetailRow label="Prioridad" value={selectedCustomer.priority} />
          <DetailRow label="Zona" value={selectedCustomer.zone_id.slice(0, 8)} />
          <DetailRow label="Estado" value={<StatusPill status={selectedCustomer.active ? "eligible" : "cancelled"} />} />
          {selectedCustomer.cutoff_override_time && (
            <DetailRow label="Corte personalizado" value={selectedCustomer.cutoff_override_time} />
          )}
          <DetailRow label="Creado" value={selectedCustomer.created_at?.slice(0, 10) ?? "—"} />
        </DetailPanel>
      )}
      <div style={{ marginBottom: 16 }}>
        <input
          type="search"
          placeholder="Buscar clientes…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            width: 280,
            padding: "8px 14px",
            borderRadius: 8,
            border: `1px solid ${C.border}`,
            fontSize: 13,
            outline: "none",
            background: C.surface,
            color: C.text,
          }}
        />
      </div>
      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[1, 2, 3].map((i) => <Skeleton key={i} height={52} />)}
        </div>
      ) : (
        <DataTable
          columns={cols}
          rows={rows}
          onRowClick={(i) => {
            const c = filtered[i];
            if (c) setSelectedCustomer(selectedCustomer?.id === c.id ? null : c);
          }}
          empty={
            <div>
              <div style={{ fontSize: 36, marginBottom: 12 }}>🤝</div>
              <div style={{ fontSize: 15, fontWeight: 600, color: C.text, marginBottom: 4 }}>Sin clientes aún</div>
              <div style={{ fontSize: 13, color: C.muted }}>Añade tu primer cliente para empezar</div>
            </div>
          }
        />
      )}
    </SectionPage>
  );
}

// ── DriversSection ────────────────────────────────────────────────────────────

export function DriversSection({ token }: { token: string }) {
  const [drivers, setDrivers] = useState<DriverOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedDriver, setSelectedDriver] = useState<DriverOut | null>(null);
  const toast = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listDrivers(token, {});
      setDrivers(res.items ?? []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { void load(); }, [load]);

  const filtered = drivers.filter((d) =>
    d.name.toLowerCase().includes(search.toLowerCase()) ||
    (d.phone ?? "").toLowerCase().includes(search.toLowerCase())
  );

  const cols = ["Conductor", "Teléfono", "Vehículo", "Estado"];
  const rows = filtered.map((d) => [
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <div
        style={{
          width: 30,
          height: 30,
          borderRadius: "50%",
          background: "#fef3c7",
          color: "#92400e",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 11,
          fontWeight: 700,
          flexShrink: 0,
        }}
      >
        {d.name.slice(0, 2).toUpperCase()}
      </div>
      <span style={{ fontWeight: 500 }}>{d.name}</span>
    </div>,
    <span style={{ color: C.muted, fontFamily: "monospace", fontSize: 12 }}>{d.phone || "—"}</span>,
    <span style={{ color: C.muted, fontSize: 12 }}>{d.vehicle_id ? d.vehicle_id.slice(0, 8) : "Sin asignar"}</span>,
    <StatusPill status={d.is_active ? "eligible" : "cancelled"} />,
  ]);

  return (
    <SectionPage
      title="Conductores"
      subtitle={`${drivers.length} conductor${drivers.length !== 1 ? "es" : ""}`}
      action={<PrimaryBtn onClick={() => toast.show("Alta de conductores disponible en Admin → Usuarios")}>+ Invitar conductor</PrimaryBtn>}
    >
      {toast.el}
      {selectedDriver && (
        <DetailPanel
          title={selectedDriver.name}
          onClose={() => setSelectedDriver(null)}
        >
          <DetailRow label="ID" value={<span style={{ fontFamily: "monospace", fontSize: 12 }}>{selectedDriver.id}</span>} />
          <DetailRow label="Teléfono" value={selectedDriver.phone || "—"} />
          <DetailRow label="Vehículo" value={selectedDriver.vehicle_id ? selectedDriver.vehicle_id.slice(0, 8) : "Sin asignar"} />
          <DetailRow label="Estado" value={<StatusPill status={selectedDriver.is_active ? "eligible" : "cancelled"} />} />
        </DetailPanel>
      )}
      <div style={{ marginBottom: 16 }}>
        <input
          type="search"
          placeholder="Buscar conductores…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            width: 280,
            padding: "8px 14px",
            borderRadius: 8,
            border: `1px solid ${C.border}`,
            fontSize: 13,
            outline: "none",
            background: C.surface,
            color: C.text,
          }}
        />
      </div>
      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[1, 2, 3].map((i) => <Skeleton key={i} height={52} />)}
        </div>
      ) : (
        <DataTable
          columns={cols}
          rows={rows}
          onRowClick={(i) => {
            const d = filtered[i];
            if (d) setSelectedDriver(selectedDriver?.id === d.id ? null : d);
          }}
          empty={
            <div>
              <div style={{ fontSize: 36, marginBottom: 12 }}>🚚</div>
              <div style={{ fontSize: 15, fontWeight: 600, color: C.text, marginBottom: 4 }}>Sin conductores</div>
              <div style={{ fontSize: 13, color: C.muted }}>Invita a tu primer conductor para empezar</div>
            </div>
          }
        />
      )}
    </SectionPage>
  );
}

// ── InsightsSection ───────────────────────────────────────────────────────────

function KpiCard({ label, value, sub, color }: { label: string; value: number | string; sub: string; color: string }) {
  return (
    <div
      style={{
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: 10,
        padding: "20px 24px 16px",
        display: "flex",
        flexDirection: "column",
        gap: 4,
      }}
    >
      <div style={{ fontSize: 11, fontWeight: 600, color: C.muted, textTransform: "uppercase", letterSpacing: "0.04em" }}>
        {label}
      </div>
      <div style={{ fontSize: 38, fontWeight: 700, color, lineHeight: 1.1 }}>
        {value}
      </div>
      <div style={{ fontSize: 12, color: C.subtle }}>{sub}</div>
      <div style={{ marginTop: 14, height: 3, borderRadius: 99, background: `linear-gradient(90deg, ${color}30, ${color})` }} />
    </div>
  );
}

export function InsightsSection({ token }: { token: string }) {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [routes, setRoutes] = useState<RoutingRoute[]>([]);
  const [loading, setLoading] = useState(true);

  const today = new Date().toISOString().slice(0, 10);

  useEffect(() => {
    const fetchAll = async () => {
      setLoading(true);
      try {
        const [sum, rts] = await Promise.allSettled([
          getDailySummary(token, today),
          listRoutes(token, { service_date: today }),
        ] as const);
        if (sum.status === "fulfilled") setSummary(sum.value);
        if (rts.status === "fulfilled") setRoutes(rts.value.items);
      } finally {
        setLoading(false);
      }
    };
    void fetchAll();
  }, [token, today]);

  const totalRoutes     = routes.length;
  const activeRoutes    = routes.filter((r) => r.status === "in_progress" || r.status === "dispatched").length;
  const completedRoutes = routes.filter((r) => r.status === "completed").length;
  const totalStops      = routes.reduce((acc, r) => acc + r.stops.length, 0);
  const doneStops       = routes.reduce((acc, r) => acc + r.stops.filter((s) => s.status === "completed").length, 0);
  const failedStops     = routes.reduce((acc, r) => acc + r.stops.filter((s) => s.status === "failed").length, 0);
  const deliveryRate    = totalStops > 0 ? Math.round((doneStops / totalStops) * 100) : 0;

  return (
    <SectionPage
      title="Insights"
      subtitle={`Resumen operativo · ${today}`}
    >
      {loading ? (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
          {[1, 2, 3, 4, 5, 6].map((i) => <Skeleton key={i} height={130} />)}
        </div>
      ) : (
        <>
          {/* Pedidos */}
          <div style={{ fontSize: 11, fontWeight: 700, color: C.muted, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10 }}>
            Pedidos
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14, marginBottom: 24 }}>
            <KpiCard label="Pedidos hoy"       value={summary?.total_orders ?? 0} sub={`${summary?.late_orders ?? 0} tardíos`}           color={C.accent}   />
            <KpiCard label="Planes abiertos"   value={summary?.plans_open ?? 0}   sub={`${summary?.plans_locked ?? 0} cerrados`}          color="#16a34a"   />
            <KpiCard label="Excepciones"       value={summary?.pending_exceptions ?? 0} sub={`${summary?.approved_exceptions ?? 0} aprobadas · ${summary?.rejected_exceptions ?? 0} rechazadas`} color="#d97706" />
          </div>

          {/* Rutas */}
          <div style={{ fontSize: 11, fontWeight: 700, color: C.muted, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10 }}>
            Rutas del día
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14, marginBottom: 24 }}>
            <KpiCard label="Rutas totales"     value={totalRoutes}     sub={`${activeRoutes} activas · ${completedRoutes} completadas`} color={C.accent}  />
            <KpiCard label="Paradas totales"   value={totalStops}      sub={`${doneStops} entregadas · ${failedStops} fallidas`}        color="#7c3aed"   />
            <KpiCard label="Tasa de entrega"   value={`${deliveryRate}%`} sub={totalStops > 0 ? `${doneStops}/${totalStops} paradas` : "Sin datos"}   color={deliveryRate >= 90 ? "#16a34a" : deliveryRate >= 70 ? "#d97706" : "#dc2626"} />
          </div>

          {(summary == null && routes.length === 0) && (
            <div style={{ textAlign: "center", color: C.muted, padding: "40px 0", fontSize: 14 }}>
              Sin datos de resumen disponibles
            </div>
          )}
        </>
      )}
    </SectionPage>
  );
}
