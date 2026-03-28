"use client";

import { useMemo, useState } from "react";

type Dict = Record<string, unknown>;

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function api<T>(path: string, token: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(options?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body?.detail?.code ? `${body.detail.code}: ${body.detail.message}` : `HTTP ${res.status}`;
    throw new Error(detail);
  }

  return res.json() as Promise<T>;
}

export default function HomePage() {
  const [email, setEmail] = useState("logistics@demo.local");
  const [password, setPassword] = useState("logistics123");
  const [token, setToken] = useState("");
  const [serviceDate, setServiceDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [error, setError] = useState("");

  const [summary, setSummary] = useState<Dict | null>(null);
  const [orders, setOrders] = useState<Dict[]>([]);
  const [plans, setPlans] = useState<Dict[]>([]);
  const [exceptions, setExceptions] = useState<Dict[]>([]);

  const [newPlanZoneId, setNewPlanZoneId] = useState("");
  const [includePlanId, setIncludePlanId] = useState("");
  const [includeOrderId, setIncludeOrderId] = useState("");
  const [exceptionOrderId, setExceptionOrderId] = useState("");
  const [exceptionNote, setExceptionNote] = useState("Pedido fuera de corte");

  const isAuthenticated = useMemo(() => token.length > 0, [token]);

  async function login() {
    setError("");
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        throw new Error("Credenciales inválidas");
      }
      const body = (await res.json()) as { access_token: string };
      setToken(body.access_token);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error de login");
    }
  }

  async function refresh() {
    if (!token) return;
    setError("");
    try {
      const [summaryRes, ordersRes, plansRes, exceptionsRes] = await Promise.all([
        api<Dict>(`/dashboard/daily-summary?service_date=${serviceDate}`, token),
        api<{ items: Dict[] }>(`/orders?service_date=${serviceDate}`, token),
        api<{ items: Dict[] }>(`/plans?service_date=${serviceDate}`, token),
        api<{ items: Dict[] }>(`/exceptions`, token),
      ]);
      setSummary(summaryRes);
      setOrders(ordersRes.items ?? []);
      setPlans(plansRes.items ?? []);
      setExceptions(exceptionsRes.items ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error cargando datos");
    }
  }

  async function createPlan() {
    try {
      await api("/plans", token, {
        method: "POST",
        body: JSON.stringify({ service_date: serviceDate, zone_id: newPlanZoneId }),
      });
      setNewPlanZoneId("");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error creando plan");
    }
  }

  async function lockPlan(planId: string) {
    try {
      await api(`/plans/${planId}/lock`, token, { method: "POST" });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error bloqueando plan");
    }
  }

  async function includeOrder() {
    try {
      await api(`/plans/${includePlanId}/orders`, token, {
        method: "POST",
        body: JSON.stringify({ order_id: includeOrderId }),
      });
      setIncludeOrderId("");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error incluyendo pedido");
    }
  }

  async function createException() {
    try {
      await api(`/exceptions`, token, {
        method: "POST",
        body: JSON.stringify({ order_id: exceptionOrderId, type: "late_order", note: exceptionNote }),
      });
      setExceptionOrderId("");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error creando excepción");
    }
  }

  async function approveException(exceptionId: string) {
    try {
      await api(`/exceptions/${exceptionId}/approve`, token, { method: "POST" });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error aprobando excepción");
    }
  }

  async function rejectException(exceptionId: string) {
    try {
      await api(`/exceptions/${exceptionId}/reject`, token, {
        method: "POST",
        body: JSON.stringify({ note: "No aplica para este service_date" }),
      });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error rechazando excepción");
    }
  }

  return (
    <main className="grid" style={{ gap: 16 }}>
      <div className="card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1>CorteCero Ops</h1>
          <p style={{ margin: 0, color: "#6b7280" }}>Cut-off, planes bloqueados y excepciones auditadas</p>
        </div>
        <div className="row">
          <input type="date" value={serviceDate} onChange={(e) => setServiceDate(e.target.value)} />
          <button className="secondary" onClick={refresh} disabled={!isAuthenticated}>
            Refrescar
          </button>
        </div>
      </div>

      {!isAuthenticated && (
        <div className="card grid cols-2">
          <input placeholder="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <input placeholder="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <button onClick={login}>Entrar</button>
        </div>
      )}

      {error && (
        <div className="card" style={{ borderColor: "#fca5a5", color: "#991b1b" }}>
          {error}
        </div>
      )}

      {summary && (
        <div className="card grid cols-2">
          {Object.entries(summary).map(([k, v]) => (
            <div key={k}>
              <strong>{k}</strong>: {String(v)}
            </div>
          ))}
        </div>
      )}

      {isAuthenticated && (
        <div className="grid cols-2">
          <div className="card grid">
            <h2>Planes</h2>
            <div className="row">
              <input
                placeholder="zone_id para crear plan"
                value={newPlanZoneId}
                onChange={(e) => setNewPlanZoneId(e.target.value)}
              />
              <button onClick={createPlan}>Crear plan</button>
            </div>
            <div className="row">
              <input placeholder="plan_id" value={includePlanId} onChange={(e) => setIncludePlanId(e.target.value)} />
              <input placeholder="order_id" value={includeOrderId} onChange={(e) => setIncludeOrderId(e.target.value)} />
              <button className="secondary" onClick={includeOrder}>
                Incluir pedido
              </button>
            </div>
            <table>
              <thead>
                <tr>
                  <th>id</th>
                  <th>zona</th>
                  <th>estado</th>
                  <th>pedidos</th>
                  <th>acción</th>
                </tr>
              </thead>
              <tbody>
                {plans.map((p) => {
                  const id = String(p.id);
                  const status = String(p.status);
                  return (
                    <tr key={id}>
                      <td>{id.slice(0, 8)}</td>
                      <td>{String(p.zone_id).slice(0, 8)}</td>
                      <td>{status}</td>
                      <td>{Array.isArray(p.orders) ? p.orders.length : 0}</td>
                      <td>
                        {status === "open" && <button onClick={() => lockPlan(id)}>Lock</button>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="card grid">
            <h2>Excepciones</h2>
            <div className="row">
              <input
                placeholder="order_id"
                value={exceptionOrderId}
                onChange={(e) => setExceptionOrderId(e.target.value)}
              />
              <input placeholder="nota" value={exceptionNote} onChange={(e) => setExceptionNote(e.target.value)} />
              <button className="warn" onClick={createException}>
                Solicitar excepción
              </button>
            </div>
            <table>
              <thead>
                <tr>
                  <th>id</th>
                  <th>order</th>
                  <th>estado</th>
                  <th>acción</th>
                </tr>
              </thead>
              <tbody>
                {exceptions.map((ex) => {
                  const id = String(ex.id);
                  const status = String(ex.status);
                  return (
                    <tr key={id}>
                      <td>{id.slice(0, 8)}</td>
                      <td>{String(ex.order_id).slice(0, 8)}</td>
                      <td>{status}</td>
                      <td className="row">
                        {status === "pending" && (
                          <>
                            <button onClick={() => approveException(id)}>Aprobar</button>
                            <button className="danger" onClick={() => rejectException(id)}>
                              Rechazar
                            </button>
                          </>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {isAuthenticated && (
        <div className="card">
          <h2>Pedidos</h2>
          <table>
            <thead>
              <tr>
                <th>ref</th>
                <th>cliente</th>
                <th>zona</th>
                <th>estado</th>
                <th>late</th>
                <th>cutoff</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => {
                const status = String(o.status);
                const isLate = Boolean(o.is_late);
                const badgeClass = status === "exception_rejected" ? "badge rejected" : isLate ? "badge late" : "badge ok";
                return (
                  <tr key={String(o.id)}>
                    <td>{String(o.external_ref)}</td>
                    <td>{String(o.customer_id).slice(0, 8)}</td>
                    <td>{String(o.zone_id).slice(0, 8)}</td>
                    <td>{status}</td>
                    <td>
                      <span className={badgeClass}>{isLate ? "late" : "on_time"}</span>
                    </td>
                    <td>{String(o.effective_cutoff_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
