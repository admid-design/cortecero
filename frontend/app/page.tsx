"use client";

import { useCallback, useMemo, useState } from "react";

import {
  type AdminUser,
  APIError,
  approveException,
  createAdminCustomer,
  createAdminUser,
  createAdminZone,
  createException,
  createPlan,
  deactivateAdminCustomer,
  deactivateAdminZone,
  getDailySummary,
  getSourceMetrics,
  getAdminTenantSettings,
  includeOrderInPlan,
  listPendingQueue,
  listAdminCustomers,
  listAdminUsers,
  listAdminZones,
  listExceptions,
  listOrders,
  listPlans,
  lockPlan,
  login,
  rejectException,
  runAutoLock,
  updateAdminCustomer,
  updateAdminTenantSettings,
  updateAdminUser,
  updateAdminZone,
  type AutoLockRunResponse,
  type Customer,
  type DashboardSummary,
  type DashboardSourceMetricsItem,
  type ExceptionItem,
  type Order,
  type PendingQueueItem,
  type PendingQueueReason,
  type Plan,
  type TenantSettings,
  type UserRole,
  type Zone,
} from "../lib/api";

type ViewMode = "ops" | "admin";
type AdminSection = "zones" | "customers" | "users" | "tenant";

function decodeRoleFromToken(token: string): UserRole | null {
  try {
    const [, payload] = token.split(".");
    if (!payload) return null;
    const decoded = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    const parsed = JSON.parse(decoded) as { role?: string };
    if (parsed.role === "office" || parsed.role === "logistics" || parsed.role === "admin") {
      return parsed.role;
    }
    return null;
  } catch {
    return null;
  }
}

function formatError(error: unknown): string {
  if (error instanceof APIError) {
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return "Error inesperado";
}

function shortId(value: string): string {
  return value.slice(0, 8);
}

function intakeBadgeMeta(intakeType: string): { className: string; label: string } {
  if (intakeType === "new_order") {
    return { className: "badge intake-new", label: "nuevo" };
  }
  if (intakeType === "same_customer_addon") {
    return { className: "badge intake-addon", label: "añadido" };
  }
  return { className: "badge intake-unknown", label: intakeType || "unknown" };
}

export default function HomePage() {
  const [tenantSlug, setTenantSlug] = useState("demo-cortecero");
  const [email, setEmail] = useState("logistics@demo.cortecero.app");
  const [password, setPassword] = useState("logistics123");
  const [token, setToken] = useState("");
  const [role, setRole] = useState<UserRole | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("ops");
  const [adminSection, setAdminSection] = useState<AdminSection>("zones");

  const [serviceDate, setServiceDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [error, setError] = useState("");

  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [sourceMetrics, setSourceMetrics] = useState<DashboardSourceMetricsItem[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [pendingQueue, setPendingQueue] = useState<PendingQueueItem[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [exceptions, setExceptions] = useState<ExceptionItem[]>([]);
  const [pendingQueueZoneId, setPendingQueueZoneId] = useState("all");
  const [pendingQueueReason, setPendingQueueReason] = useState<"all" | PendingQueueReason>("all");
  const [sourceDateFrom, setSourceDateFrom] = useState(() => new Date().toISOString().slice(0, 10));
  const [sourceDateTo, setSourceDateTo] = useState(() => new Date().toISOString().slice(0, 10));
  const [sourceZoneId, setSourceZoneId] = useState("all");

  const [newPlanZoneId, setNewPlanZoneId] = useState("");
  const [includePlanId, setIncludePlanId] = useState("");
  const [includeOrderId, setIncludeOrderId] = useState("");
  const [autoLockRunning, setAutoLockRunning] = useState(false);
  const [autoLockResult, setAutoLockResult] = useState<AutoLockRunResponse | null>(null);
  const [exceptionOrderId, setExceptionOrderId] = useState("");
  const [exceptionNote, setExceptionNote] = useState("Pedido fuera de corte");

  const [zoneFilter, setZoneFilter] = useState<"all" | "active" | "inactive">("all");
  const [zones, setZones] = useState<Zone[]>([]);
  const [newZoneName, setNewZoneName] = useState("");
  const [newZoneCutoff, setNewZoneCutoff] = useState("10:00:00");
  const [newZoneTimezone, setNewZoneTimezone] = useState("Europe/Madrid");
  const [editingZoneId, setEditingZoneId] = useState("");
  const [editZoneName, setEditZoneName] = useState("");
  const [editZoneCutoff, setEditZoneCutoff] = useState("10:00:00");
  const [editZoneTimezone, setEditZoneTimezone] = useState("Europe/Madrid");

  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerFilter, setCustomerFilter] = useState<"all" | "active" | "inactive">("all");
  const [customerZoneFilter, setCustomerZoneFilter] = useState("all");
  const [newCustomerName, setNewCustomerName] = useState("");
  const [newCustomerZoneId, setNewCustomerZoneId] = useState("");
  const [newCustomerPriority, setNewCustomerPriority] = useState("0");
  const [newCustomerCutoff, setNewCustomerCutoff] = useState("");
  const [editingCustomerId, setEditingCustomerId] = useState("");
  const [editCustomerName, setEditCustomerName] = useState("");
  const [editCustomerZoneId, setEditCustomerZoneId] = useState("");
  const [editCustomerPriority, setEditCustomerPriority] = useState("0");
  const [editCustomerCutoff, setEditCustomerCutoff] = useState("");

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [userFilter, setUserFilter] = useState<"all" | "active" | "inactive">("all");
  const [userRoleFilter, setUserRoleFilter] = useState<"all" | UserRole>("all");
  const [newUserEmail, setNewUserEmail] = useState("");
  const [newUserName, setNewUserName] = useState("");
  const [newUserRole, setNewUserRole] = useState<UserRole>("office");
  const [newUserPassword, setNewUserPassword] = useState("");
  const [newUserActive, setNewUserActive] = useState(true);
  const [editingUserId, setEditingUserId] = useState("");
  const [editUserEmail, setEditUserEmail] = useState("");
  const [editUserName, setEditUserName] = useState("");
  const [editUserRole, setEditUserRole] = useState<UserRole>("office");
  const [editUserPassword, setEditUserPassword] = useState("");
  const [editUserActive, setEditUserActive] = useState(true);

  const [tenantSettings, setTenantSettings] = useState<TenantSettings | null>(null);
  const [tenantCutoff, setTenantCutoff] = useState("10:00:00");
  const [tenantTimezone, setTenantTimezone] = useState("Europe/Madrid");
  const [tenantAutoLock, setTenantAutoLock] = useState(false);

  const isAuthenticated = useMemo(() => token.length > 0, [token]);
  const isAdmin = useMemo(() => role === "admin", [role]);
  const canRunAutoLock = useMemo(() => role === "logistics" || role === "admin", [role]);
  const pendingQueueZoneOptions = useMemo(() => {
    const values = new Set<string>();
    for (const order of orders) values.add(order.zone_id);
    for (const plan of plans) values.add(plan.zone_id);
    for (const item of pendingQueue) values.add(item.zone_id);
    return [...values];
  }, [orders, plans, pendingQueue]);
  const sourceMetricsZoneOptions = useMemo(() => {
    const values = new Set<string>();
    for (const order of orders) values.add(order.zone_id);
    for (const plan of plans) values.add(plan.zone_id);
    for (const item of pendingQueue) values.add(item.zone_id);
    return [...values];
  }, [orders, plans, pendingQueue]);

  const refreshOps = useCallback(async (authToken?: string) => {
    const activeToken = authToken ?? token;
    if (!activeToken) return;
    setError("");
    try {
      const zone_id = pendingQueueZoneId === "all" ? undefined : pendingQueueZoneId;
      const reason = pendingQueueReason === "all" ? undefined : pendingQueueReason;
      const source_zone_id = sourceZoneId === "all" ? undefined : sourceZoneId;
      const [summaryRes, sourceMetricsRes, ordersRes, plansRes, exceptionsRes, pendingQueueRes] = await Promise.all([
        getDailySummary(activeToken, serviceDate),
        getSourceMetrics(activeToken, {
          date_from: sourceDateFrom,
          date_to: sourceDateTo,
          zone_id: source_zone_id,
        }),
        listOrders(activeToken, serviceDate),
        listPlans(activeToken, serviceDate),
        listExceptions(activeToken),
        listPendingQueue(activeToken, { service_date: serviceDate, zone_id, reason }),
      ]);
      setSummary(summaryRes);
      setSourceMetrics(sourceMetricsRes.items ?? []);
      setOrders(ordersRes.items ?? []);
      setPlans(plansRes.items ?? []);
      setExceptions(exceptionsRes.items ?? []);
      setPendingQueue(pendingQueueRes.items ?? []);
    } catch (e) {
      setError(formatError(e));
    }
  }, [pendingQueueReason, pendingQueueZoneId, serviceDate, sourceDateFrom, sourceDateTo, sourceZoneId, token]);

  const refreshZones = useCallback(async (authToken?: string) => {
    const activeToken = authToken ?? token;
    if (!activeToken) return;
    setError("");
    try {
      const active = zoneFilter === "all" ? undefined : zoneFilter === "active";
      const res = await listAdminZones(activeToken, { active });
      setZones(res.items ?? []);
    } catch (e) {
      setError(formatError(e));
    }
  }, [token, zoneFilter]);

  const refreshCustomers = useCallback(async (authToken?: string) => {
    const activeToken = authToken ?? token;
    if (!activeToken) return;
    setError("");
    try {
      const active = customerFilter === "all" ? undefined : customerFilter === "active";
      const zone_id = customerZoneFilter === "all" ? undefined : customerZoneFilter;
      const res = await listAdminCustomers(activeToken, { active, zone_id });
      setCustomers(res.items ?? []);
    } catch (e) {
      setError(formatError(e));
    }
  }, [customerFilter, customerZoneFilter, token]);

  const refreshUsers = useCallback(async (authToken?: string) => {
    const activeToken = authToken ?? token;
    if (!activeToken) return;
    setError("");
    try {
      const is_active = userFilter === "all" ? undefined : userFilter === "active";
      const role = userRoleFilter === "all" ? undefined : userRoleFilter;
      const res = await listAdminUsers(activeToken, { is_active, role });
      setUsers(res.items ?? []);
    } catch (e) {
      setError(formatError(e));
    }
  }, [token, userFilter, userRoleFilter]);

  const refreshTenantSettings = useCallback(async (authToken?: string) => {
    const activeToken = authToken ?? token;
    if (!activeToken) return;
    setError("");
    try {
      const data = await getAdminTenantSettings(activeToken);
      setTenantSettings(data);
      setTenantCutoff(data.default_cutoff_time);
      setTenantTimezone(data.default_timezone);
      setTenantAutoLock(data.auto_lock_enabled);
    } catch (e) {
      setError(formatError(e));
    }
  }, [token]);

  async function onLogin() {
    setError("");
    try {
      const auth = await login({
        tenant_slug: tenantSlug,
        email,
        password,
      });
      const nextRole = decodeRoleFromToken(auth.access_token);
      setToken(auth.access_token);
      setRole(nextRole);
      setViewMode("ops");
      setAutoLockResult(null);
      await refreshOps(auth.access_token);
      if (nextRole === "admin") {
        await refreshZones(auth.access_token);
        await refreshCustomers(auth.access_token);
        await refreshUsers(auth.access_token);
        await refreshTenantSettings(auth.access_token);
      } else {
        setZones([]);
        setCustomers([]);
        setUsers([]);
        setTenantSettings(null);
      }
    } catch (e) {
      setError(formatError(e));
    }
  }

  function onLogout() {
    setToken("");
    setRole(null);
    setSummary(null);
    setSourceMetrics([]);
    setOrders([]);
    setPendingQueue([]);
    setPlans([]);
    setExceptions([]);
    setZones([]);
    setCustomers([]);
    setUsers([]);
    setTenantSettings(null);
    setViewMode("ops");
    setAutoLockResult(null);
    setAutoLockRunning(false);
  }

  async function onCreatePlan() {
    if (!token || !newPlanZoneId) return;
    try {
      await createPlan(token, { service_date: serviceDate, zone_id: newPlanZoneId });
      setNewPlanZoneId("");
      await refreshOps();
    } catch (e) {
      setError(formatError(e));
    }
  }

  async function onLockPlan(planId: string) {
    if (!token) return;
    try {
      await lockPlan(token, planId);
      await refreshOps();
    } catch (e) {
      setError(formatError(e));
    }
  }

  async function onRunAutoLock() {
    if (!token || !canRunAutoLock) return;
    setError("");
    setAutoLockRunning(true);
    try {
      const result = await runAutoLock(token);
      setAutoLockResult(result);
      await refreshOps();
    } catch (e) {
      setError(formatError(e));
    } finally {
      setAutoLockRunning(false);
    }
  }

  async function onIncludeOrder() {
    if (!token || !includePlanId || !includeOrderId) return;
    try {
      await includeOrderInPlan(token, includePlanId, includeOrderId);
      setIncludeOrderId("");
      await refreshOps();
    } catch (e) {
      setError(formatError(e));
    }
  }

  async function onCreateException() {
    if (!token || !exceptionOrderId || !exceptionNote) return;
    try {
      await createException(token, {
        order_id: exceptionOrderId,
        type: "late_order",
        note: exceptionNote,
      });
      setExceptionOrderId("");
      await refreshOps();
    } catch (e) {
      setError(formatError(e));
    }
  }

  async function onApproveException(exceptionId: string) {
    if (!token) return;
    try {
      await approveException(token, exceptionId);
      await refreshOps();
    } catch (e) {
      setError(formatError(e));
    }
  }

  async function onRejectException(exceptionId: string) {
    if (!token) return;
    try {
      await rejectException(token, exceptionId, "No aplica para este service_date");
      await refreshOps();
    } catch (e) {
      setError(formatError(e));
    }
  }

  async function onCreateZone() {
    if (!token || !isAdmin) return;
    if (!newZoneName.trim()) {
      setError("El nombre de zona es obligatorio");
      return;
    }
    try {
      await createAdminZone(token, {
        name: newZoneName.trim(),
        default_cutoff_time: newZoneCutoff,
        timezone: newZoneTimezone.trim(),
      });
      setNewZoneName("");
      await refreshZones();
    } catch (e) {
      setError(formatError(e));
    }
  }

  function startEditZone(zone: Zone) {
    setEditingZoneId(zone.id);
    setEditZoneName(zone.name);
    setEditZoneCutoff(zone.default_cutoff_time);
    setEditZoneTimezone(zone.timezone);
  }

  function cancelEditZone() {
    setEditingZoneId("");
  }

  async function onSaveZoneEdit() {
    if (!token || !isAdmin || !editingZoneId) return;
    if (!editZoneName.trim()) {
      setError("El nombre de zona es obligatorio");
      return;
    }
    try {
      await updateAdminZone(token, editingZoneId, {
        name: editZoneName.trim(),
        default_cutoff_time: editZoneCutoff,
        timezone: editZoneTimezone.trim(),
      });
      setEditingZoneId("");
      await refreshZones();
    } catch (e) {
      setError(formatError(e));
    }
  }

  async function onDeactivateZone(zoneId: string) {
    if (!token || !isAdmin) return;
    const confirmed = window.confirm("¿Desactivar esta zona?");
    if (!confirmed) return;
    try {
      await deactivateAdminZone(token, zoneId);
      if (editingZoneId === zoneId) {
        setEditingZoneId("");
      }
      await refreshZones();
    } catch (e) {
      setError(formatError(e));
    }
  }

  async function onCreateCustomer() {
    if (!token || !isAdmin) return;
    if (!newCustomerName.trim()) {
      setError("El nombre de cliente es obligatorio");
      return;
    }
    if (!newCustomerZoneId) {
      setError("Debes seleccionar una zona");
      return;
    }
    try {
      await createAdminCustomer(token, {
        zone_id: newCustomerZoneId,
        name: newCustomerName.trim(),
        priority: Number.parseInt(newCustomerPriority, 10) || 0,
        cutoff_override_time: newCustomerCutoff.trim() || null,
      });
      setNewCustomerName("");
      setNewCustomerPriority("0");
      setNewCustomerCutoff("");
      await refreshCustomers();
    } catch (e) {
      setError(formatError(e));
    }
  }

  function startEditCustomer(customer: Customer) {
    setEditingCustomerId(customer.id);
    setEditCustomerName(customer.name);
    setEditCustomerZoneId(customer.zone_id);
    setEditCustomerPriority(String(customer.priority));
    setEditCustomerCutoff(customer.cutoff_override_time ?? "");
  }

  function cancelEditCustomer() {
    setEditingCustomerId("");
  }

  async function onSaveCustomerEdit() {
    if (!token || !isAdmin || !editingCustomerId) return;
    if (!editCustomerName.trim()) {
      setError("El nombre de cliente es obligatorio");
      return;
    }
    if (!editCustomerZoneId) {
      setError("Debes seleccionar una zona");
      return;
    }
    try {
      await updateAdminCustomer(token, editingCustomerId, {
        zone_id: editCustomerZoneId,
        name: editCustomerName.trim(),
        priority: Number.parseInt(editCustomerPriority, 10) || 0,
        cutoff_override_time: editCustomerCutoff.trim() || null,
      });
      setEditingCustomerId("");
      await refreshCustomers();
    } catch (e) {
      setError(formatError(e));
    }
  }

  async function onDeactivateCustomer(customerId: string) {
    if (!token || !isAdmin) return;
    const confirmed = window.confirm("¿Desactivar este cliente?");
    if (!confirmed) return;
    try {
      await deactivateAdminCustomer(token, customerId);
      if (editingCustomerId === customerId) {
        setEditingCustomerId("");
      }
      await refreshCustomers();
    } catch (e) {
      setError(formatError(e));
    }
  }

  async function onCreateUser() {
    if (!token || !isAdmin) return;
    if (!newUserEmail.trim() || !newUserName.trim()) {
      setError("Email y nombre son obligatorios");
      return;
    }
    if (newUserPassword.trim().length < 8) {
      setError("La password debe tener al menos 8 caracteres");
      return;
    }
    try {
      await createAdminUser(token, {
        email: newUserEmail.trim(),
        full_name: newUserName.trim(),
        role: newUserRole,
        password: newUserPassword,
        is_active: newUserActive,
      });
      setNewUserEmail("");
      setNewUserName("");
      setNewUserPassword("");
      setNewUserRole("office");
      setNewUserActive(true);
      await refreshUsers();
    } catch (e) {
      setError(formatError(e));
    }
  }

  function startEditUser(user: AdminUser) {
    setEditingUserId(user.id);
    setEditUserEmail(user.email);
    setEditUserName(user.full_name);
    setEditUserRole(user.role);
    setEditUserActive(user.is_active);
    setEditUserPassword("");
  }

  function cancelEditUser() {
    setEditingUserId("");
  }

  async function onSaveUserEdit() {
    if (!token || !isAdmin || !editingUserId) return;
    if (!editUserEmail.trim() || !editUserName.trim()) {
      setError("Email y nombre son obligatorios");
      return;
    }
    if (editUserPassword.trim().length > 0 && editUserPassword.trim().length < 8) {
      setError("La nueva password debe tener al menos 8 caracteres");
      return;
    }
    try {
      await updateAdminUser(token, editingUserId, {
        email: editUserEmail.trim(),
        full_name: editUserName.trim(),
        role: editUserRole,
        is_active: editUserActive,
        ...(editUserPassword.trim().length > 0 ? { password: editUserPassword } : {}),
      });
      setEditingUserId("");
      await refreshUsers();
    } catch (e) {
      setError(formatError(e));
    }
  }

  async function onDeactivateUser(userId: string) {
    if (!token || !isAdmin) return;
    const confirmed = window.confirm("¿Desactivar este usuario?");
    if (!confirmed) return;
    try {
      await updateAdminUser(token, userId, { is_active: false });
      if (editingUserId === userId) {
        setEditingUserId("");
      }
      await refreshUsers();
    } catch (e) {
      setError(formatError(e));
    }
  }

  async function onSaveTenantSettings() {
    if (!token || !isAdmin) return;
    if (!tenantCutoff.trim()) {
      setError("default_cutoff_time es obligatorio");
      return;
    }
    if (!tenantTimezone.trim()) {
      setError("default_timezone es obligatorio");
      return;
    }
    try {
      const updated = await updateAdminTenantSettings(token, {
        default_cutoff_time: tenantCutoff.trim(),
        default_timezone: tenantTimezone.trim(),
        auto_lock_enabled: tenantAutoLock,
      });
      setTenantSettings(updated);
      setTenantCutoff(updated.default_cutoff_time);
      setTenantTimezone(updated.default_timezone);
      setTenantAutoLock(updated.auto_lock_enabled);
    } catch (e) {
      setError(formatError(e));
    }
  }

  return (
    <main className="grid" style={{ gap: 16 }}>
      <div className="card topbar">
        <div>
          <h1>CorteCero Ops</h1>
          <p style={{ margin: 0, color: "#6b7280" }}>Cut-off, lock y excepciones con trazabilidad operativa</p>
        </div>
        {isAuthenticated && (
          <div className="row">
            <span className="pill">Rol: {role ?? "desconocido"}</span>
            <button className="secondary" onClick={onLogout}>
              Cerrar sesión
            </button>
          </div>
        )}
      </div>

      {!isAuthenticated && (
        <div className="card grid cols-2">
          <input placeholder="tenant_slug" value={tenantSlug} onChange={(e) => setTenantSlug(e.target.value)} />
          <input placeholder="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <input placeholder="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <button onClick={onLogin}>Entrar</button>
        </div>
      )}

      {error && (
        <div className="card" style={{ borderColor: "#fca5a5", color: "#991b1b" }}>
          {error}
        </div>
      )}

      {isAuthenticated && (
        <div className="card row">
          <button className={viewMode === "ops" ? "tab active" : "tab"} onClick={() => setViewMode("ops")}>
            Operación
          </button>
          {isAdmin && (
            <button
              className={viewMode === "admin" ? "tab active" : "tab"}
              onClick={() => {
                setViewMode("admin");
                void refreshZones();
              }}
            >
              Admin
            </button>
          )}
        </div>
      )}

      {isAuthenticated && viewMode === "ops" && (
        <>
          <div className="card row">
            <input type="date" value={serviceDate} onChange={(e) => setServiceDate(e.target.value)} />
            <button className="secondary" onClick={() => void refreshOps()}>
              Refrescar operación
            </button>
          </div>

          {summary && (
            <div className="card metric-grid">
              <div>
                <strong>Total pedidos</strong>
                <p>{summary.total_orders}</p>
              </div>
              <div>
                <strong>Tardíos</strong>
                <p>{summary.late_orders}</p>
              </div>
              <div>
                <strong>Planes open</strong>
                <p>{summary.plans_open}</p>
              </div>
              <div>
                <strong>Planes locked</strong>
                <p>{summary.plans_locked}</p>
              </div>
              <div>
                <strong>Excepciones pending</strong>
                <p>{summary.pending_exceptions}</p>
              </div>
              <div>
                <strong>Excepciones approved</strong>
                <p>{summary.approved_exceptions}</p>
              </div>
            </div>
          )}

          <div className="card grid">
            <h2>Métricas por Origen</h2>
            <div className="row">
              <label>
                date_from{" "}
                <input type="date" value={sourceDateFrom} onChange={(e) => setSourceDateFrom(e.target.value)} />
              </label>
              <label>
                date_to <input type="date" value={sourceDateTo} onChange={(e) => setSourceDateTo(e.target.value)} />
              </label>
              <label>
                zone_id{" "}
                <select value={sourceZoneId} onChange={(e) => setSourceZoneId(e.target.value)}>
                  <option value="all">all</option>
                  {sourceMetricsZoneOptions.map((zoneId) => (
                    <option key={zoneId} value={zoneId}>
                      {zoneId}
                    </option>
                  ))}
                </select>
              </label>
              <button className="secondary" onClick={() => void refreshOps()}>
                Aplicar filtros
              </button>
            </div>
            <table>
              <thead>
                <tr>
                  <th>source_channel</th>
                  <th>total_orders</th>
                  <th>late_orders</th>
                  <th>late_rate</th>
                  <th>approved_exceptions</th>
                  <th>rejected_exceptions</th>
                </tr>
              </thead>
              <tbody>
                {sourceMetrics.length === 0 && (
                  <tr>
                    <td colSpan={6} style={{ color: "#6b7280" }}>
                      Sin métricas para los filtros actuales.
                    </td>
                  </tr>
                )}
                {sourceMetrics.map((item) => (
                  <tr key={item.source_channel}>
                    <td>{item.source_channel}</td>
                    <td>{item.total_orders}</td>
                    <td>{item.late_orders}</td>
                    <td>{item.late_rate}</td>
                    <td>{item.approved_exceptions}</td>
                    <td>{item.rejected_exceptions}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="grid cols-2">
            <div className="card grid">
              <h2>Planes</h2>
              {canRunAutoLock && (
                <div className="row">
                  <button className="secondary" onClick={onRunAutoLock} disabled={autoLockRunning}>
                    {autoLockRunning ? "Ejecutando auto-lock..." : "Ejecutar auto-lock"}
                  </button>
                  {autoLockResult && (
                    <span className="pill">
                      service_date {autoLockResult.service_date} · locked {autoLockResult.locked_count}/
                      {autoLockResult.considered_open_plans} · enabled{" "}
                      {autoLockResult.auto_lock_enabled ? "true" : "false"} · window{" "}
                      {autoLockResult.window_reached ? "reached" : "not_reached"}
                    </span>
                  )}
                </div>
              )}
              <div className="row">
                <input
                  placeholder="zone_id para crear plan"
                  value={newPlanZoneId}
                  onChange={(e) => setNewPlanZoneId(e.target.value)}
                />
                <button onClick={onCreatePlan}>Crear plan</button>
              </div>
              <div className="row">
                <input placeholder="plan_id" value={includePlanId} onChange={(e) => setIncludePlanId(e.target.value)} />
                <input placeholder="order_id" value={includeOrderId} onChange={(e) => setIncludeOrderId(e.target.value)} />
                <button className="secondary" onClick={onIncludeOrder}>
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
                  {plans.map((plan) => (
                    <tr key={plan.id}>
                      <td>{shortId(plan.id)}</td>
                      <td>{shortId(plan.zone_id)}</td>
                      <td>{plan.status}</td>
                      <td>{Array.isArray(plan.orders) ? plan.orders.length : 0}</td>
                      <td>{plan.status === "open" && <button onClick={() => onLockPlan(plan.id)}>Lock</button>}</td>
                    </tr>
                  ))}
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
                <button className="warn" onClick={onCreateException}>
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
                  {exceptions.map((item) => (
                    <tr key={item.id}>
                      <td>{shortId(item.id)}</td>
                      <td>{shortId(item.order_id)}</td>
                      <td>{item.status}</td>
                      <td className="row">
                        {item.status === "pending" && (
                          <>
                            <button onClick={() => onApproveException(item.id)}>Aprobar</button>
                            <button className="danger" onClick={() => onRejectException(item.id)}>
                              Rechazar
                            </button>
                          </>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="card grid">
            <h2>Pending Queue</h2>
            <div className="row">
              <label>
                service_date{" "}
                <input type="date" value={serviceDate} onChange={(e) => setServiceDate(e.target.value)} />
              </label>
              <label>
                zone_id{" "}
                <select value={pendingQueueZoneId} onChange={(e) => setPendingQueueZoneId(e.target.value)}>
                  <option value="all">all</option>
                  {pendingQueueZoneOptions.map((zoneId) => (
                    <option key={zoneId} value={zoneId}>
                      {zoneId}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                reason{" "}
                <select
                  value={pendingQueueReason}
                  onChange={(e) => setPendingQueueReason(e.target.value as "all" | PendingQueueReason)}
                >
                  <option value="all">all</option>
                  <option value="LATE_PENDING_EXCEPTION">LATE_PENDING_EXCEPTION</option>
                  <option value="LOCKED_PLAN_EXCEPTION_REQUIRED">LOCKED_PLAN_EXCEPTION_REQUIRED</option>
                  <option value="EXCEPTION_REJECTED">EXCEPTION_REJECTED</option>
                </select>
              </label>
              <button className="secondary" onClick={() => void refreshOps()}>
                Aplicar filtros
              </button>
            </div>
            <table>
              <thead>
                <tr>
                  <th>ref</th>
                  <th>order_id</th>
                  <th>zone_id</th>
                  <th>status</th>
                  <th>reason</th>
                  <th>created_at</th>
                </tr>
              </thead>
              <tbody>
                {pendingQueue.length === 0 && (
                  <tr>
                    <td colSpan={6} style={{ color: "#6b7280" }}>
                      Sin pendientes para los filtros actuales.
                    </td>
                  </tr>
                )}
                {pendingQueue.map((item) => (
                  <tr key={item.order_id}>
                    <td>{item.external_ref}</td>
                    <td>{shortId(item.order_id)}</td>
                    <td>{shortId(item.zone_id)}</td>
                    <td>{item.status}</td>
                    <td>{item.reason}</td>
                    <td>{new Date(item.created_at).toLocaleString("es-ES")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card">
            <h2>Pedidos</h2>
            <table>
              <thead>
                <tr>
                  <th>ref</th>
                  <th>cliente</th>
                  <th>zona</th>
                  <th>tipo</th>
                  <th>estado</th>
                  <th>late</th>
                  <th>cutoff</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((order) => {
                  const badgeClass =
                    order.status === "exception_rejected" ? "badge rejected" : order.is_late ? "badge late" : "badge ok";
                  const intakeMeta = intakeBadgeMeta(order.intake_type);
                  return (
                    <tr key={order.id}>
                      <td>{order.external_ref}</td>
                      <td>{shortId(order.customer_id)}</td>
                      <td>{shortId(order.zone_id)}</td>
                      <td>
                        <span className={intakeMeta.className}>{intakeMeta.label}</span>
                      </td>
                      <td>{order.status}</td>
                      <td>
                        <span className={badgeClass}>{order.is_late ? "late" : "on_time"}</span>
                      </td>
                      <td>{new Date(order.effective_cutoff_at).toLocaleString("es-ES")}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {isAuthenticated && viewMode === "admin" && (
        <>
          {!isAdmin && (
            <div className="card" style={{ borderColor: "#fca5a5", color: "#991b1b" }}>
              RBAC_FORBIDDEN: Solo `admin` puede acceder a esta sección.
            </div>
          )}

          {isAdmin && (
            <>
              <div className="card row">
                <button
                  className={adminSection === "zones" ? "tab active" : "tab"}
                  onClick={() => {
                    setAdminSection("zones");
                    void refreshZones();
                  }}
                >
                  Zonas
                </button>
                <button
                  className={adminSection === "customers" ? "tab active" : "tab muted"}
                  onClick={() => {
                    setAdminSection("customers");
                    void refreshZones();
                    void refreshCustomers();
                  }}
                >
                  Clientes
                </button>
                <button
                  className={adminSection === "users" ? "tab active" : "tab muted"}
                  onClick={() => {
                    setAdminSection("users");
                    void refreshUsers();
                  }}
                >
                  Usuarios
                </button>
                <button
                  className={adminSection === "tenant" ? "tab active" : "tab muted"}
                  onClick={() => {
                    setAdminSection("tenant");
                    void refreshTenantSettings();
                  }}
                >
                  Tenant
                </button>
              </div>

              {adminSection === "zones" && (
                <div className="grid cols-2">
                  <div className="card grid">
                    <h2>Crear Zona</h2>
                    <input placeholder="Nombre" value={newZoneName} onChange={(e) => setNewZoneName(e.target.value)} />
                    <input
                      placeholder="default_cutoff_time HH:MM:SS"
                      value={newZoneCutoff}
                      onChange={(e) => setNewZoneCutoff(e.target.value)}
                    />
                    <input
                      placeholder="Timezone IANA"
                      value={newZoneTimezone}
                      onChange={(e) => setNewZoneTimezone(e.target.value)}
                    />
                    <button onClick={onCreateZone}>Crear</button>
                  </div>

                  <div className="card grid">
                    <h2>Editar Zona</h2>
                    {!editingZoneId && <p style={{ margin: 0, color: "#6b7280" }}>Selecciona una zona para editar.</p>}
                    {editingZoneId && (
                      <>
                        <input value={editZoneName} onChange={(e) => setEditZoneName(e.target.value)} />
                        <input value={editZoneCutoff} onChange={(e) => setEditZoneCutoff(e.target.value)} />
                        <input value={editZoneTimezone} onChange={(e) => setEditZoneTimezone(e.target.value)} />
                        <div className="row">
                          <button onClick={onSaveZoneEdit}>Guardar</button>
                          <button className="secondary" onClick={cancelEditZone}>
                            Cancelar
                          </button>
                        </div>
                      </>
                    )}
                  </div>

                  <div className="card" style={{ gridColumn: "1 / -1" }}>
                    <div className="row" style={{ marginBottom: 10 }}>
                      <h2 style={{ marginRight: 12 }}>Listado de Zonas</h2>
                      <select value={zoneFilter} onChange={(e) => setZoneFilter(e.target.value as "all" | "active" | "inactive")}>
                        <option value="all">Todas</option>
                        <option value="active">Activas</option>
                        <option value="inactive">Inactivas</option>
                      </select>
                      <button className="secondary" onClick={() => void refreshZones()}>
                        Refrescar
                      </button>
                    </div>
                    <table>
                      <thead>
                        <tr>
                          <th>id</th>
                          <th>nombre</th>
                          <th>cutoff</th>
                          <th>timezone</th>
                          <th>estado</th>
                          <th>acciones</th>
                        </tr>
                      </thead>
                      <tbody>
                        {zones.map((zone) => (
                          <tr key={zone.id}>
                            <td>{shortId(zone.id)}</td>
                            <td>{zone.name}</td>
                            <td>{zone.default_cutoff_time}</td>
                            <td>{zone.timezone}</td>
                            <td>
                              <span className={zone.active ? "badge ok" : "badge rejected"}>
                                {zone.active ? "active" : "inactive"}
                              </span>
                            </td>
                            <td className="row">
                              <button className="secondary" onClick={() => startEditZone(zone)}>
                                Editar
                              </button>
                              {zone.active && (
                                <button className="danger" onClick={() => onDeactivateZone(zone.id)}>
                                  Desactivar
                                </button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {adminSection === "customers" && (
                <div className="admin-layout">
                  <div className="card">
                    <div className="row" style={{ marginBottom: 10 }}>
                      <h2 style={{ marginRight: 12 }}>Listado de Clientes</h2>
                      <select
                        value={customerFilter}
                        onChange={(e) => setCustomerFilter(e.target.value as "all" | "active" | "inactive")}
                      >
                        <option value="all">Todos</option>
                        <option value="active">Activos</option>
                        <option value="inactive">Inactivos</option>
                      </select>
                      <select value={customerZoneFilter} onChange={(e) => setCustomerZoneFilter(e.target.value)}>
                        <option value="all">Todas las zonas</option>
                        {zones.map((zone) => (
                          <option key={zone.id} value={zone.id}>
                            {zone.name}
                          </option>
                        ))}
                      </select>
                      <button className="secondary" onClick={() => void refreshCustomers()}>
                        Refrescar
                      </button>
                    </div>
                    <table>
                      <thead>
                        <tr>
                          <th>id</th>
                          <th>nombre</th>
                          <th>zona</th>
                          <th>prioridad</th>
                          <th>cutoff override</th>
                          <th>estado</th>
                          <th>acciones</th>
                        </tr>
                      </thead>
                      <tbody>
                        {customers.map((customer) => {
                          const zoneName = zones.find((zone) => zone.id === customer.zone_id)?.name ?? shortId(customer.zone_id);
                          return (
                            <tr key={customer.id}>
                              <td>{shortId(customer.id)}</td>
                              <td>{customer.name}</td>
                              <td>{zoneName}</td>
                              <td>{customer.priority}</td>
                              <td>{customer.cutoff_override_time ?? "-"}</td>
                              <td>
                                <span className={customer.active ? "badge ok" : "badge rejected"}>
                                  {customer.active ? "active" : "inactive"}
                                </span>
                              </td>
                              <td className="row">
                                <button className="secondary" onClick={() => startEditCustomer(customer)}>
                                  Editar
                                </button>
                                {customer.active && (
                                  <button className="danger" onClick={() => onDeactivateCustomer(customer.id)}>
                                    Desactivar
                                  </button>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>

                  <div className="grid" style={{ gap: 12 }}>
                    <div className="card grid">
                      <h2>Crear Cliente</h2>
                      <input
                        placeholder="Nombre cliente"
                        value={newCustomerName}
                        onChange={(e) => setNewCustomerName(e.target.value)}
                      />
                      <select value={newCustomerZoneId} onChange={(e) => setNewCustomerZoneId(e.target.value)}>
                        <option value="">Selecciona zona</option>
                        {zones.map((zone) => (
                          <option key={zone.id} value={zone.id}>
                            {zone.name}
                          </option>
                        ))}
                      </select>
                      <input
                        placeholder="Prioridad (int)"
                        value={newCustomerPriority}
                        onChange={(e) => setNewCustomerPriority(e.target.value)}
                      />
                      <input
                        placeholder="cutoff_override_time HH:MM:SS (opcional)"
                        value={newCustomerCutoff}
                        onChange={(e) => setNewCustomerCutoff(e.target.value)}
                      />
                      <button onClick={onCreateCustomer}>Crear</button>
                    </div>

                    <div className="card grid">
                      <h2>Editar Cliente</h2>
                      {!editingCustomerId && <p style={{ margin: 0, color: "#6b7280" }}>Selecciona un cliente para editar.</p>}
                      {editingCustomerId && (
                        <>
                          <input value={editCustomerName} onChange={(e) => setEditCustomerName(e.target.value)} />
                          <select value={editCustomerZoneId} onChange={(e) => setEditCustomerZoneId(e.target.value)}>
                            <option value="">Selecciona zona</option>
                            {zones.map((zone) => (
                              <option key={zone.id} value={zone.id}>
                                {zone.name}
                              </option>
                            ))}
                          </select>
                          <input value={editCustomerPriority} onChange={(e) => setEditCustomerPriority(e.target.value)} />
                          <input value={editCustomerCutoff} onChange={(e) => setEditCustomerCutoff(e.target.value)} />
                          <div className="row">
                            <button onClick={onSaveCustomerEdit}>Guardar</button>
                            <button className="secondary" onClick={cancelEditCustomer}>
                              Cancelar
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {adminSection === "users" && (
                <div className="admin-layout">
                  <div className="card">
                    <div className="row" style={{ marginBottom: 10 }}>
                      <h2 style={{ marginRight: 12 }}>Listado de Usuarios</h2>
                      <select value={userFilter} onChange={(e) => setUserFilter(e.target.value as "all" | "active" | "inactive")}>
                        <option value="all">Todos</option>
                        <option value="active">Activos</option>
                        <option value="inactive">Inactivos</option>
                      </select>
                      <select value={userRoleFilter} onChange={(e) => setUserRoleFilter(e.target.value as "all" | UserRole)}>
                        <option value="all">Todos los roles</option>
                        <option value="office">office</option>
                        <option value="logistics">logistics</option>
                        <option value="admin">admin</option>
                      </select>
                      <button className="secondary" onClick={() => void refreshUsers()}>
                        Refrescar
                      </button>
                    </div>
                    <table>
                      <thead>
                        <tr>
                          <th>id</th>
                          <th>email</th>
                          <th>nombre</th>
                          <th>rol</th>
                          <th>estado</th>
                          <th>acciones</th>
                        </tr>
                      </thead>
                      <tbody>
                        {users.map((user) => (
                          <tr key={user.id}>
                            <td>{shortId(user.id)}</td>
                            <td>{user.email}</td>
                            <td>{user.full_name}</td>
                            <td>{user.role}</td>
                            <td>
                              <span className={user.is_active ? "badge ok" : "badge rejected"}>
                                {user.is_active ? "active" : "inactive"}
                              </span>
                            </td>
                            <td className="row">
                              <button className="secondary" onClick={() => startEditUser(user)}>
                                Editar
                              </button>
                              {user.is_active && (
                                <button className="danger" onClick={() => onDeactivateUser(user.id)}>
                                  Desactivar
                                </button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div className="grid" style={{ gap: 12 }}>
                    <div className="card grid">
                      <h2>Crear Usuario</h2>
                      <input placeholder="Email" value={newUserEmail} onChange={(e) => setNewUserEmail(e.target.value)} />
                      <input placeholder="Nombre" value={newUserName} onChange={(e) => setNewUserName(e.target.value)} />
                      <select value={newUserRole} onChange={(e) => setNewUserRole(e.target.value as UserRole)}>
                        <option value="office">office</option>
                        <option value="logistics">logistics</option>
                        <option value="admin">admin</option>
                      </select>
                      <input
                        placeholder="Password (mín. 8)"
                        type="password"
                        value={newUserPassword}
                        onChange={(e) => setNewUserPassword(e.target.value)}
                      />
                      <label className="row" style={{ gap: 6 }}>
                        <input
                          type="checkbox"
                          checked={newUserActive}
                          onChange={(e) => setNewUserActive(e.target.checked)}
                        />
                        Activo
                      </label>
                      <button onClick={onCreateUser}>Crear</button>
                    </div>

                    <div className="card grid">
                      <h2>Editar Usuario</h2>
                      {!editingUserId && <p style={{ margin: 0, color: "#6b7280" }}>Selecciona un usuario para editar.</p>}
                      {editingUserId && (
                        <>
                          <input value={editUserEmail} onChange={(e) => setEditUserEmail(e.target.value)} />
                          <input value={editUserName} onChange={(e) => setEditUserName(e.target.value)} />
                          <select value={editUserRole} onChange={(e) => setEditUserRole(e.target.value as UserRole)}>
                            <option value="office">office</option>
                            <option value="logistics">logistics</option>
                            <option value="admin">admin</option>
                          </select>
                          <input
                            placeholder="Nueva password (opcional)"
                            type="password"
                            value={editUserPassword}
                            onChange={(e) => setEditUserPassword(e.target.value)}
                          />
                          <label className="row" style={{ gap: 6 }}>
                            <input
                              type="checkbox"
                              checked={editUserActive}
                              onChange={(e) => setEditUserActive(e.target.checked)}
                            />
                            Activo
                          </label>
                          <div className="row">
                            <button onClick={onSaveUserEdit}>Guardar</button>
                            <button className="secondary" onClick={cancelEditUser}>
                              Cancelar
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {adminSection === "tenant" && (
                <div className="grid cols-2">
                  <div className="card grid">
                    <h2>Tenant Settings</h2>
                    <div>
                      <strong>Tenant:</strong> {tenantSettings?.name ?? "-"}
                    </div>
                    <div>
                      <strong>Slug:</strong> {tenantSettings?.slug ?? "-"}
                    </div>
                    <input
                      placeholder="default_cutoff_time HH:MM:SS"
                      value={tenantCutoff}
                      onChange={(e) => setTenantCutoff(e.target.value)}
                    />
                    <input
                      placeholder="default_timezone"
                      value={tenantTimezone}
                      onChange={(e) => setTenantTimezone(e.target.value)}
                    />
                    <label className="row" style={{ gap: 6 }}>
                      <input
                        type="checkbox"
                        checked={tenantAutoLock}
                        onChange={(e) => setTenantAutoLock(e.target.checked)}
                      />
                      auto_lock_enabled
                    </label>
                    <div className="row">
                      <button onClick={onSaveTenantSettings}>Guardar</button>
                      <button className="secondary" onClick={() => refreshTenantSettings()}>
                        Recargar
                      </button>
                    </div>
                  </div>

                  <div className="card">
                    <h2>Contexto</h2>
                    <p style={{ margin: 0, color: "#6b7280" }}>
                      Cambios aquí impactan la configuración base del tenant para reglas de cut-off y lock automático.
                    </p>
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}
    </main>
  );
}
