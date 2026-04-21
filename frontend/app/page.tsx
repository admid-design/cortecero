"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouteStream, type StreamEventType } from "../lib/useRouteStream";

import {
  type AdminUser,
  type DriverPositionOut,
  type IncidentCreateRequest,
  type RouteNextStopResponse,
  APIError,
  formatError,
  arriveStop,
  completeStop,
  createStopProof,
  failStop,
  getActivePositions,
  getDelayAlerts,
  getDriverPosition,
  skipStop,
  createIncident,
  getDriverRoutes,
  getRouteNextStop,
  approveException,
  createAdminUser,
  createException,
  createPlan,
  dispatchRoute,
  getDailySummary,
  getPlanCapacityAlerts,
  getPlanCustomerConsolidation,
  getSourceMetrics,
  getAdminTenantSettings,
  getRoute,
  includeOrderInPlan,
  listAvailableVehicles,
  listOrderOperationalSnapshots,
  listOperationalQueue,
  listOperationalResolutionQueue,
  listPendingQueue,
  listReadyToDispatchOrders,
  listRouteEvents,
  listRoutes,
  listAdminUsers,
  listAdminZones,
  listExceptions,
  listOrders,
  listDrivers,
  listPlans,
  lockPlan,
  login,
  moveRouteStop,
  optimizeRoute,
  recalculateEta,
  planRoutes,
  rejectException,
  runAutoLock,
  updatePlanVehicle,
  updateOrderWeight,
  updateAdminTenantSettings,
  updateAdminUser,
  type AutoLockRunResponse,
  type AvailableVehicleItem,
  type CapacityAlertLevel,
  type DashboardSummary,
  type DashboardSourceMetricsItem,
  type ExceptionItem,
  type Order,
  type OrderOperationalSeverity,
  type OperationalQueueItem,
  type OperationalQueueReason,
  type OperationalResolutionQueueItem,
  type OperationalResolutionQueueReason,
  type OperationalResolutionQueueSeverity,
  type OrderOperationalSnapshotItem,
  type PendingQueueItem,
  type PendingQueueReason,
  type DriverOut,
  type Plan,
  type PlanCapacityAlert,
  type PlanCustomerConsolidationResponse,
  type DelayAlertOut,
  type ReadyToDispatchItem,
  type RouteEventItem,
  type RoutingRoute,
  type RoutingRouteStatus,
  type TenantSettings,
  type UserRole,
  type Zone,
} from "../lib/api";
import { DispatcherRoutingCard } from "../components/DispatcherRoutingCard";
import { OperationalQueueTableCard } from "../components/OperationalQueueTableCard";
import { OperationalResolutionQueueTableCard } from "../components/OperationalResolutionQueueTableCard";
import { OrderSnapshotsTimelineCard } from "../components/OrderSnapshotsTimelineCard";
import { PendingQueueTableCard } from "../components/PendingQueueTableCard";
import { AdminProductsCard } from "../components/AdminProductsCard";
import { OrdersTableCard } from "../components/OrdersTableCard";
import { PlansTableCard } from "../components/PlansTableCard";
import { PlanConsolidationCard } from "../components/PlanConsolidationCard";
import { ExceptionsTableCard } from "../components/ExceptionsTableCard";
import { CapacityAlertsTableCard } from "../components/CapacityAlertsTableCard";
import { AppShell, GlobalBanner, SectionHeader, SidebarNav, TopTabs } from "../components/AppShell";
import { KpiRow } from "../components/KpiRow";
import { DispatcherRoutingShell } from "../components/DispatcherRoutingShell";
import { AdminShell } from "../components/AdminShell";
import { AdminZonesSection } from "../components/AdminZonesSection";
import { AdminCustomersSection } from "../components/AdminCustomersSection";
import { OpsMapDashboard } from "../components/OpsMapDashboard";
import { DriverMobileView } from "../components/DriverMobileView";
import { RoutePlannerCalendar } from "../components/RoutePlannerCalendar";
import {
  GlobalShell,
  OrdersSection,
  CustomersSection,
  DriversSection,
  InsightsSection,
  RouteTemplatesSection,
} from "../components/GlobalShell";
import type { SidebarSection } from "../components/GlobalShell";
type ViewMode = "ops" | "admin" | "planner" | "orders" | "customers" | "drivers" | "templates" | "insights";
type AdminSection = "zones" | "customers" | "users" | "tenant" | "products";
type OrdersOperationalStateFilter = "all" | "eligible" | "restricted";

const OPERATIONAL_REASON_ORDER = [
  "CUSTOMER_DATE_BLOCKED",
  "CUSTOMER_NOT_ACCEPTING_ORDERS",
  "OUTSIDE_CUSTOMER_WINDOW",
  "INSUFFICIENT_LEAD_TIME",
] as const;
const OPERATIONAL_SEVERITY_ORDER = ["critical", "high", "medium", "low"] as const;

function decodeRoleFromToken(token: string): UserRole | null {
  try {
    const [, payload] = token.split(".");
    if (!payload) return null;
    const decoded = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    const parsed = JSON.parse(decoded) as { role?: string };
    if (
      parsed.role === "office" ||
      parsed.role === "logistics" ||
      parsed.role === "admin" ||
      parsed.role === "driver"
    ) {
      return parsed.role;
    }
    return null;
  } catch {
    return null;
  }
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

function operationalStateBadgeMeta(state: string): { className: string; label: string } {
  if (state === "eligible") {
    return { className: "badge ok", label: "eligible" };
  }
  if (state === "restricted") {
    return { className: "badge late", label: "restricted" };
  }
  return { className: "badge intake-unknown", label: state || "unknown" };
}

function operationalReasonBadgeClass(reason: string): string {
  if (reason === "CUSTOMER_DATE_BLOCKED" || reason === "CUSTOMER_NOT_ACCEPTING_ORDERS") {
    return "badge rejected";
  }
  if (reason === "OUTSIDE_CUSTOMER_WINDOW" || reason === "INSUFFICIENT_LEAD_TIME") {
    return "badge late";
  }
  return "badge intake-unknown";
}

function operationalSeverityBadgeClass(severity: OrderOperationalSeverity | string | null): string {
  if (severity === "critical") return "badge rejected";
  if (severity === "high") return "badge late";
  if (severity === "medium") return "badge intake-addon";
  if (severity === "low") return "badge ok";
  return "badge intake-unknown";
}

export default function HomePage() {
  const [tenantSlug, setTenantSlug] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");
  const [role, setRole] = useState<UserRole | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("planner");
  const [adminSection, setAdminSection] = useState<AdminSection>("zones");

  const [serviceDate, setServiceDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [error, setError] = useState("");
  const [toastMsg, setToastMsg] = useState<{ text: string; kind: "ok" | "err" } | null>(null);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  function showToast(text: string, kind: "ok" | "err" = "ok") {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToastMsg({ text, kind });
    toastTimerRef.current = setTimeout(() => setToastMsg(null), 3500);
  }

  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [sourceMetrics, setSourceMetrics] = useState<DashboardSourceMetricsItem[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [ordersOperationalStateFilter, setOrdersOperationalStateFilter] = useState<OrdersOperationalStateFilter>("all");
  const [ordersOperationalReasonFilter, setOrdersOperationalReasonFilter] = useState("all");
  const [pendingQueue, setPendingQueue] = useState<PendingQueueItem[]>([]);
  const [operationalQueue, setOperationalQueue] = useState<OperationalQueueItem[]>([]);
  const [operationalResolutionQueue, setOperationalResolutionQueue] = useState<OperationalResolutionQueueItem[]>([]);
  const [selectedSnapshotOrderId, setSelectedSnapshotOrderId] = useState("");
  const [orderOperationalSnapshots, setOrderOperationalSnapshots] = useState<OrderOperationalSnapshotItem[]>([]);
  const [orderOperationalSnapshotsLoading, setOrderOperationalSnapshotsLoading] = useState(false);
  const [orderOperationalSnapshotsError, setOrderOperationalSnapshotsError] = useState("");
  const [capacityAlerts, setCapacityAlerts] = useState<PlanCapacityAlert[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [selectedConsolidationPlanId, setSelectedConsolidationPlanId] = useState("");
  const [planConsolidation, setPlanConsolidation] = useState<PlanCustomerConsolidationResponse | null>(null);
  const [planConsolidationLoading, setPlanConsolidationLoading] = useState(false);
  const [exceptions, setExceptions] = useState<ExceptionItem[]>([]);
  const [dispatcherReadyOrders, setDispatcherReadyOrders] = useState<ReadyToDispatchItem[]>([]);
  const [dispatcherVehicles, setDispatcherVehicles] = useState<AvailableVehicleItem[]>([]);
  const [dispatcherRoutes, setDispatcherRoutes] = useState<RoutingRoute[]>([]);
  const [dispatcherRouteStatus, setDispatcherRouteStatus] = useState<"all" | RoutingRouteStatus>("all");
  const [dispatcherLoading, setDispatcherLoading] = useState(false);
  const [dispatcherRouteDetailLoading, setDispatcherRouteDetailLoading] = useState(false);
  const [selectedDispatcherRouteId, setSelectedDispatcherRouteId] = useState("");
  const [selectedDispatcherRoute, setSelectedDispatcherRoute] = useState<RoutingRoute | null>(null);
  const [selectedDispatcherRouteEvents, setSelectedDispatcherRouteEvents] = useState<RouteEventItem[]>([]);
  const [selectedDispatcherRouteDelayAlerts, setSelectedDispatcherRouteDelayAlerts] = useState<DelayAlertOut[]>([]);
  const [dispatcherPlanId, setDispatcherPlanId] = useState("");
  const [dispatcherPlanVehicleId, setDispatcherPlanVehicleId] = useState("");
  const [dispatcherPlanDriverId, setDispatcherPlanDriverId] = useState("");
  const [dispatcherPlanOrderIds, setDispatcherPlanOrderIds] = useState("");
  const [opsDrivers, setOpsDrivers] = useState<DriverOut[]>([]);
  const [dispatcherPlanCreating, setDispatcherPlanCreating] = useState(false);
  const [dispatcherOptimizingRouteId, setDispatcherOptimizingRouteId] = useState<string | null>(null);
  const [dispatcherDispatchingRouteId, setDispatcherDispatchingRouteId] = useState<string | null>(null);
  const [dispatcherRecalculatingEtaRouteId, setDispatcherRecalculatingEtaRouteId] = useState<string | null>(null);
  const [dispatcherMoveSourceRouteId, setDispatcherMoveSourceRouteId] = useState("");
  const [dispatcherMoveStopId, setDispatcherMoveStopId] = useState("");
  const [dispatcherMoveTargetRouteId, setDispatcherMoveTargetRouteId] = useState("");
  const [dispatcherMovingStop, setDispatcherMovingStop] = useState(false);
  const [pendingQueueZoneId, setPendingQueueZoneId] = useState("all");
  const [pendingQueueReason, setPendingQueueReason] = useState<"all" | PendingQueueReason>("all");
  const [operationalQueueZoneId, setOperationalQueueZoneId] = useState("all");
  const [operationalQueueReason, setOperationalQueueReason] = useState<"all" | OperationalQueueReason | string>("all");
  const [operationalResolutionQueueZoneId, setOperationalResolutionQueueZoneId] = useState("all");
  const [operationalResolutionQueueReason, setOperationalResolutionQueueReason] =
    useState<"all" | OperationalResolutionQueueReason | string>("all");
  const [operationalResolutionQueueSeverity, setOperationalResolutionQueueSeverity] =
    useState<"all" | OperationalResolutionQueueSeverity | string>("all");
  const [capacityAlertZoneId, setCapacityAlertZoneId] = useState("all");
  const [capacityAlertLevel, setCapacityAlertLevel] = useState<"all" | CapacityAlertLevel>("all");
  const [sourceDateFrom, setSourceDateFrom] = useState(() => new Date().toISOString().slice(0, 10));
  const [sourceDateTo, setSourceDateTo] = useState(() => new Date().toISOString().slice(0, 10));
  const [sourceZoneId, setSourceZoneId] = useState("all");

  const [newPlanZoneId, setNewPlanZoneId] = useState("");
  const [includePlanId, setIncludePlanId] = useState("");
  const [includeOrderId, setIncludeOrderId] = useState("");
  const [autoLockRunning, setAutoLockRunning] = useState(false);
  const [autoLockResult, setAutoLockResult] = useState<AutoLockRunResponse | null>(null);
  const [weightDrafts, setWeightDrafts] = useState<Record<string, string>>({});
  const [savingWeightOrderId, setSavingWeightOrderId] = useState<string | null>(null);
  const [vehicleDrafts, setVehicleDrafts] = useState<Record<string, string>>({});
  const [savingVehiclePlanId, setSavingVehiclePlanId] = useState<string | null>(null);
  const [exceptionOrderId, setExceptionOrderId] = useState("");
  const [exceptionNote, setExceptionNote] = useState("Pedido fuera de corte");

  const [zoneFilter, setZoneFilter] = useState<"all" | "active" | "inactive">("all");
  const [zones, setZones] = useState<Zone[]>([]);

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

  // ── Driver PWA state ──────────────────────────────────────────────────────
  const [driverRoutes, setDriverRoutes] = useState<RoutingRoute[]>([]);
  const [driverLoading, setDriverLoading] = useState(false);
  const [selectedDriverRouteId, setSelectedDriverRouteId] = useState("");
  const [selectedDriverRoute, setSelectedDriverRoute] = useState<RoutingRoute | null>(null);
  const [driverNextStop, setDriverNextStop] = useState<RouteNextStopResponse | null>(null);
  const [driverNextStopLoading, setDriverNextStopLoading] = useState(false);
  const [driverActionLoadingStopId, setDriverActionLoadingStopId] = useState<string | null>(null);
  const [driverIncidentLoading, setDriverIncidentLoading] = useState(false);
  const [driverProofLoading, setDriverProofLoading] = useState(false);
  const [driverError, setDriverError] = useState<string | null>(null);
  const [driverSuccess, setDriverSuccess] = useState<string | null>(null);
  // Posición del conductor vista desde el dispatcher (polling cada 30s)
  const [dispatcherDriverPosition, setDispatcherDriverPosition] = useState<DriverPositionOut | null>(null);
  // Posiciones de toda la flota activa (polling cada 30s — fleet view)
  const [activePositions, setActivePositions] = useState<DriverPositionOut[]>([]);

  const isAuthenticated = useMemo(() => token.length > 0, [token]);
  const isAdmin = useMemo(() => role === "admin", [role]);
  const isDriver = useMemo(() => role === "driver", [role]);
  const canManageRouting = useMemo(() => role === "logistics" || role === "admin", [role]);
  const canViewRouting = useMemo(() => role === "office" || role === "logistics" || role === "admin", [role]);
  const canEditOrderWeight = useMemo(() => role === "logistics" || role === "admin", [role]);
  const canRunAutoLock = useMemo(() => role === "logistics" || role === "admin", [role]);
  const canAssignPlanVehicle = useMemo(() => role === "logistics" || role === "admin", [role]);
  const pendingQueueZoneOptions = useMemo(() => {
    const values = new Set<string>();
    for (const order of orders) values.add(order.zone_id);
    for (const plan of plans) values.add(plan.zone_id);
    for (const item of pendingQueue) values.add(item.zone_id);
    for (const item of operationalQueue) values.add(item.zone_id);
    for (const item of operationalResolutionQueue) values.add(item.zone_id);
    return [...values];
  }, [operationalQueue, operationalResolutionQueue, orders, pendingQueue, plans]);
  const operationalQueueZoneOptions = useMemo(() => {
    const values = new Set<string>();
    for (const item of operationalQueue) values.add(item.zone_id);
    for (const order of orders) values.add(order.zone_id);
    for (const plan of plans) values.add(plan.zone_id);
    return [...values];
  }, [operationalQueue, orders, plans]);
  const operationalResolutionQueueZoneOptions = useMemo(() => {
    const values = new Set<string>();
    for (const item of operationalResolutionQueue) values.add(item.zone_id);
    for (const order of orders) values.add(order.zone_id);
    for (const plan of plans) values.add(plan.zone_id);
    return [...values];
  }, [operationalResolutionQueue, orders, plans]);
  const sourceMetricsZoneOptions = useMemo(() => {
    const values = new Set<string>();
    for (const order of orders) values.add(order.zone_id);
    for (const plan of plans) values.add(plan.zone_id);
    for (const item of pendingQueue) values.add(item.zone_id);
    for (const item of operationalQueue) values.add(item.zone_id);
    for (const item of operationalResolutionQueue) values.add(item.zone_id);
    return [...values];
  }, [operationalQueue, operationalResolutionQueue, orders, pendingQueue, plans]);
  const ordersOperationalReasonOptions = useMemo(() => {
    const values = new Set<string>();
    for (const order of orders) {
      if (order.operational_reason) values.add(order.operational_reason);
    }
    const orderedKnown = OPERATIONAL_REASON_ORDER.filter((reason) => values.has(reason));
    const unknown = [...values].filter((reason) => !OPERATIONAL_REASON_ORDER.includes(reason as (typeof OPERATIONAL_REASON_ORDER)[number]));
    unknown.sort();
    return [...orderedKnown, ...unknown];
  }, [orders]);
  const snapshotOrderOptions = useMemo(
    () =>
      orders.map((order) => ({
        id: order.id,
        externalRef: order.external_ref,
        serviceDate: order.service_date,
      })),
    [orders],
  );
  const operationalQueueReasonOptions = useMemo(() => {
    const values = new Set<string>();
    for (const item of operationalQueue) values.add(item.reason);
    const unknown = [...values].filter(
      (reason) => !OPERATIONAL_REASON_ORDER.includes(reason as (typeof OPERATIONAL_REASON_ORDER)[number]),
    );
    unknown.sort();
    return [...OPERATIONAL_REASON_ORDER, ...unknown];
  }, [operationalQueue]);
  const operationalResolutionQueueReasonOptions = useMemo(() => {
    const values = new Set<string>();
    for (const item of operationalResolutionQueue) values.add(item.operational_reason);
    const unknown = [...values].filter(
      (reason) => !OPERATIONAL_REASON_ORDER.includes(reason as (typeof OPERATIONAL_REASON_ORDER)[number]),
    );
    unknown.sort();
    return [...OPERATIONAL_REASON_ORDER, ...unknown];
  }, [operationalResolutionQueue]);
  const filteredOrders = useMemo(() => {
    return orders.filter((order) => {
      if (ordersOperationalStateFilter !== "all" && order.operational_state !== ordersOperationalStateFilter) {
        return false;
      }
      if (ordersOperationalReasonFilter !== "all" && order.operational_reason !== ordersOperationalReasonFilter) {
        return false;
      }
      return true;
    });
  }, [orders, ordersOperationalReasonFilter, ordersOperationalStateFilter]);

  const refreshOps = useCallback(async (authToken?: string) => {
    const activeToken = authToken ?? token;
    if (!activeToken) return;
    setError("");
    try {
      const zone_id = pendingQueueZoneId === "all" ? undefined : pendingQueueZoneId;
      const reason = pendingQueueReason === "all" ? undefined : pendingQueueReason;
      const operational_zone_id = operationalQueueZoneId === "all" ? undefined : operationalQueueZoneId;
      const operational_reason = operationalQueueReason === "all" ? undefined : operationalQueueReason;
      const operational_resolution_zone_id =
        operationalResolutionQueueZoneId === "all" ? undefined : operationalResolutionQueueZoneId;
      const operational_resolution_reason =
        operationalResolutionQueueReason === "all" ? undefined : operationalResolutionQueueReason;
      const operational_resolution_severity =
        operationalResolutionQueueSeverity === "all" ? undefined : operationalResolutionQueueSeverity;
      const source_zone_id = sourceZoneId === "all" ? undefined : sourceZoneId;
      const capacity_zone_id = capacityAlertZoneId === "all" ? undefined : capacityAlertZoneId;
      const level = capacityAlertLevel === "all" ? undefined : capacityAlertLevel;
      const [
        summaryRes,
        sourceMetricsRes,
        ordersRes,
        plansRes,
        exceptionsRes,
        pendingQueueRes,
        operationalQueueRes,
        operationalResolutionQueueRes,
        capacityAlertsRes,
      ] = await Promise.all([
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
        listOperationalQueue(activeToken, {
          service_date: serviceDate,
          zone_id: operational_zone_id,
          reason: operational_reason,
        }),
        listOperationalResolutionQueue(activeToken, {
          service_date: serviceDate,
          zone_id: operational_resolution_zone_id,
          reason: operational_resolution_reason,
          severity: operational_resolution_severity,
        }),
        getPlanCapacityAlerts(activeToken, { service_date: serviceDate, zone_id: capacity_zone_id, level }),
      ]);
      setSummary(summaryRes);
      setSourceMetrics(sourceMetricsRes.items ?? []);
      setOrders(ordersRes.items ?? []);
      setPlans(plansRes.items ?? []);
      setExceptions(exceptionsRes.items ?? []);
      setPendingQueue(pendingQueueRes.items ?? []);
      setOperationalQueue(operationalQueueRes.items ?? []);
      setOperationalResolutionQueue(operationalResolutionQueueRes.items ?? []);
      setCapacityAlerts(capacityAlertsRes.items ?? []);
    } catch (e) {
      setError(formatError(e));
    }
  }, [
    capacityAlertLevel,
    capacityAlertZoneId,
    operationalQueueReason,
    operationalQueueZoneId,
    operationalResolutionQueueReason,
    operationalResolutionQueueSeverity,
    operationalResolutionQueueZoneId,
    pendingQueueReason,
    pendingQueueZoneId,
    serviceDate,
    sourceDateFrom,
    sourceDateTo,
    sourceZoneId,
    token,
  ]);

  const loadDispatcherRouteDetail = useCallback(
    async (routeId: string, authToken?: string) => {
      const activeToken = authToken ?? token;
      if (!activeToken || !routeId) return;
      setDispatcherRouteDetailLoading(true);
      try {
        const [routeRes, eventsRes, alertsRes] = await Promise.all([
          getRoute(activeToken, routeId),
          listRouteEvents(activeToken, routeId),
          getDelayAlerts(activeToken, routeId).catch(() => [] as DelayAlertOut[]),
        ]);
        setSelectedDispatcherRoute(routeRes);
        setSelectedDispatcherRouteEvents(eventsRes.items ?? []);
        setSelectedDispatcherRouteDelayAlerts(alertsRes);
        setDispatcherMoveSourceRouteId(routeRes.id);
      } catch (e) {
        setError(formatError(e));
        setSelectedDispatcherRoute(null);
        setSelectedDispatcherRouteEvents([]);
        setSelectedDispatcherRouteDelayAlerts([]);
      } finally {
        setDispatcherRouteDetailLoading(false);
      }
    },
    [token],
  );

  const refreshDispatcher = useCallback(
    async (authToken?: string, roleOverride?: UserRole | null) => {
      const activeToken = authToken ?? token;
      const activeRole = roleOverride ?? role;
      const canView = activeRole === "office" || activeRole === "logistics" || activeRole === "admin";
      const canManage = activeRole === "logistics" || activeRole === "admin";
      if (!activeToken || !canView) return;
      setDispatcherLoading(true);
      setError("");
      try {
        const status = dispatcherRouteStatus === "all" ? undefined : dispatcherRouteStatus;
        const routesRes = await listRoutes(activeToken, {
          service_date: serviceDate,
          status,
        });
        const routes = routesRes.items ?? [];
        setDispatcherRoutes(routes);

        if (canManage) {
          const [readyRes, vehiclesRes, driversRes] = await Promise.all([
            listReadyToDispatchOrders(activeToken, { service_date: serviceDate }),
            listAvailableVehicles(activeToken, { service_date: serviceDate }),
            listDrivers(activeToken, { active: true }),
          ]);
          setDispatcherReadyOrders(readyRes.items ?? []);
          setDispatcherVehicles(vehiclesRes.items ?? []);
          setOpsDrivers(driversRes.items ?? []);
        } else {
          setDispatcherReadyOrders([]);
          setDispatcherVehicles([]);
        }

        if (selectedDispatcherRouteId) {
          const existsInList = routes.some((route) => route.id === selectedDispatcherRouteId);
          if (existsInList) {
            await loadDispatcherRouteDetail(selectedDispatcherRouteId, activeToken);
          } else {
            setSelectedDispatcherRouteId("");
            setSelectedDispatcherRoute(null);
            setSelectedDispatcherRouteEvents([]);
            setDispatcherMoveSourceRouteId("");
          }
        }
      } catch (e) {
        setError(formatError(e));
      } finally {
        setDispatcherLoading(false);
      }
    },
    [
      dispatcherRouteStatus,
      loadDispatcherRouteDetail,
      role,
      selectedDispatcherRouteId,
      serviceDate,
      token,
    ],
  );

  const onSelectDispatcherRoute = useCallback(
    (routeId: string) => {
      setSelectedDispatcherRouteId(routeId);
      setDispatcherDriverPosition(null); // reset al cambiar de ruta
      if (!routeId) {
        setSelectedDispatcherRoute(null);
        setSelectedDispatcherRouteEvents([]);
        setDispatcherMoveSourceRouteId("");
        return;
      }
      void loadDispatcherRouteDetail(routeId);
    },
    [loadDispatcherRouteDetail],
  );

  // SSE de posición del conductor — R8-SSE-FE
  // Reemplaza el polling 30s anterior. Fallback automático a polling si SSE falla.
  const dispatcherSelectedRouteStatus = selectedDispatcherRoute?.status ?? null;
  const shouldPollDriverPosition =
    selectedDispatcherRouteId !== "" &&
    (dispatcherSelectedRouteStatus === "dispatched" || dispatcherSelectedRouteStatus === "in_progress");

  // Fetch inicial al seleccionar ruta activa (SSE no envía estado acumulado al conectar).
  useEffect(() => {
    if (!shouldPollDriverPosition || !token || !selectedDispatcherRouteId) {
      setDispatcherDriverPosition(null);
      return;
    }
    void getDriverPosition(token, selectedDispatcherRouteId)
      .then(setDispatcherDriverPosition)
      .catch(() => {
        // Sin posición aún — conductor no ha publicado GPS todavía.
      });
  }, [shouldPollDriverPosition, token, selectedDispatcherRouteId]);

  // Callback estable para onEvent SSE.
  const onDriverStreamEvent = useCallback(
    (type: StreamEventType, data: unknown) => {
      if (type === "driver_position_updated") {
        const d = data as { lat: number; lng: number; recorded_at: string };
        setDispatcherDriverPosition((prev) =>
          prev
            ? { ...prev, lat: d.lat, lng: d.lng, recorded_at: d.recorded_at }
            : null, // Sin fetch inicial aún — ignorar hasta que llegue el primer poll.
        );
      }
    },
    [],
  );

  // Callback estable para fallback polling cuando SSE está degradado.
  const onDriverStreamFallback = useCallback(() => {
    if (!token || !selectedDispatcherRouteId) return;
    void getDriverPosition(token, selectedDispatcherRouteId)
      .then(setDispatcherDriverPosition)
      .catch(() => {});
  }, [token, selectedDispatcherRouteId]);

  // Abre stream SSE. En modo degradado (sseDriverDegraded=true) activa polling 30s.
  const { degraded: sseDriverDegraded } = useRouteStream({
    routeId: selectedDispatcherRouteId,
    token: token ?? "",
    enabled: shouldPollDriverPosition && !!token,
    onEvent: onDriverStreamEvent,
    onFallbackPoll: onDriverStreamFallback,
    fallbackIntervalMs: 30_000,
  });

  // sseDriverDegraded expuesto para posible indicador visual futuro (no bloqueante).
  void sseDriverDegraded;

  // Polling de posiciones de toda la flota cada 30 s — fleet view en mapa dispatcher
  const pollFleetPositionsRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const isDispatcherView = role === "admin" || role === "logistics";
    if (!token || !isDispatcherView) {
      if (pollFleetPositionsRef.current) {
        clearInterval(pollFleetPositionsRef.current);
        pollFleetPositionsRef.current = null;
      }
      setActivePositions([]);
      return;
    }

    const poll = async () => {
      try {
        const positions = await getActivePositions(token);
        setActivePositions(positions);
      } catch {
        // sin conductores activos o endpoint no disponible
      }
    };

    void poll(); // primera llamada inmediata
    pollFleetPositionsRef.current = setInterval(() => void poll(), 30_000);

    return () => {
      if (pollFleetPositionsRef.current) {
        clearInterval(pollFleetPositionsRef.current);
        pollFleetPositionsRef.current = null;
      }
    };
  }, [token, role]);

  const onSnapshotOrderChange = useCallback((orderId: string) => {
    setSelectedSnapshotOrderId(orderId);
    setOrderOperationalSnapshots([]);
    setOrderOperationalSnapshotsError("");
  }, []);

  const loadOrderOperationalSnapshots = useCallback(async () => {
    if (!token) return;
    if (!selectedSnapshotOrderId) {
      setOrderOperationalSnapshotsError("ORDER_REQUIRED: Selecciona un pedido");
      return;
    }
    setOrderOperationalSnapshotsLoading(true);
    setOrderOperationalSnapshotsError("");
    try {
      const data = await listOrderOperationalSnapshots(token, selectedSnapshotOrderId);
      setOrderOperationalSnapshots(data.items ?? []);
    } catch (e) {
      setOrderOperationalSnapshotsError(formatError(e));
      setOrderOperationalSnapshots([]);
    } finally {
      setOrderOperationalSnapshotsLoading(false);
    }
  }, [selectedSnapshotOrderId, token]);

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

  // ── Driver actions ────────────────────────────────────────────────────────

  async function refreshDriver(tok?: string) {
    const t = tok ?? token;
    if (!t) return;
    setDriverLoading(true);
    setDriverError(null);
    try {
      const today = new Date().toISOString().slice(0, 10);
      const res = await getDriverRoutes(t, { service_date: today });
      setDriverRoutes(res.items);
    } catch (e) {
      setDriverError(formatError(e));
    } finally {
      setDriverLoading(false);
    }
  }

  async function onSelectDriverRoute(routeId: string) {
    setSelectedDriverRouteId(routeId);
    const route = driverRoutes.find((r) => r.id === routeId) ?? null;
    setSelectedDriverRoute(route);
    setDriverNextStop(null);
    if (!routeId || !route) return;
    setDriverNextStopLoading(true);
    try {
      const ns = await getRouteNextStop(token, routeId);
      setDriverNextStop(ns);
    } catch {
      // non-fatal: banner stays empty
    } finally {
      setDriverNextStopLoading(false);
    }
  }

  async function onDriverArrive(stopId: string) {
    setDriverActionLoadingStopId(stopId);
    setDriverError(null);
    setDriverSuccess(null);
    try {
      const updated = await arriveStop(token, stopId);
      setDriverSuccess(`Parada #${updated.sequence_number}: llegada registrada.`);
      await refreshDriverRouteAndNextStop();
    } catch (e) {
      setDriverError(formatError(e));
    } finally {
      setDriverActionLoadingStopId(null);
    }
  }

  async function onDriverComplete(stopId: string) {
    setDriverActionLoadingStopId(stopId);
    setDriverError(null);
    setDriverSuccess(null);
    try {
      const updated = await completeStop(token, stopId);
      setDriverSuccess(`Parada #${updated.sequence_number}: entrega completada.`);
      await refreshDriverRouteAndNextStop();
    } catch (e) {
      setDriverError(formatError(e));
    } finally {
      setDriverActionLoadingStopId(null);
    }
  }

  async function onDriverCompleteWithProof(stopId: string, signatureData: string, signedBy: string) {
    setDriverActionLoadingStopId(stopId);
    setDriverProofLoading(true);
    setDriverError(null);
    setDriverSuccess(null);
    try {
      // 1. Completar la parada
      const updated = await completeStop(token, stopId);
      // 2. Guardar la firma vinculada a la parada ya completada
      await createStopProof(token, stopId, {
        proof_type: "signature",
        signature_data: signatureData,
        signed_by: signedBy || null,
        captured_at: new Date().toISOString(),
      });
      setDriverSuccess(`Parada #${updated.sequence_number}: entrega completada con firma.`);
      await refreshDriverRouteAndNextStop();
    } catch (e) {
      setDriverError(formatError(e));
    } finally {
      setDriverActionLoadingStopId(null);
      setDriverProofLoading(false);
    }
  }

  async function onDriverFail(stopId: string, reason: string) {
    setDriverActionLoadingStopId(stopId);
    setDriverError(null);
    setDriverSuccess(null);
    try {
      const updated = await failStop(token, stopId, { failure_reason: reason });
      setDriverSuccess(`Parada #${updated.sequence_number}: falla registrada.`);
      await refreshDriverRouteAndNextStop();
    } catch (e) {
      setDriverError(formatError(e));
    } finally {
      setDriverActionLoadingStopId(null);
    }
  }

  async function onDriverSkip(stopId: string) {
    setDriverActionLoadingStopId(stopId);
    setDriverError(null);
    setDriverSuccess(null);
    try {
      const updated = await skipStop(token, stopId);
      setDriverSuccess(`Parada #${updated.sequence_number}: omitida.`);
      await refreshDriverRouteAndNextStop();
    } catch (e) {
      setDriverError(formatError(e));
    } finally {
      setDriverActionLoadingStopId(null);
    }
  }

  async function onDriverReportIncident(payload: IncidentCreateRequest) {
    setDriverIncidentLoading(true);
    setDriverError(null);
    setDriverSuccess(null);
    try {
      await createIncident(token, payload);
      setDriverSuccess("Incidencia reportada correctamente.");
    } catch (e) {
      setDriverError(formatError(e));
    } finally {
      setDriverIncidentLoading(false);
    }
  }

  async function refreshDriverRouteAndNextStop() {
    await refreshDriver();
    if (selectedDriverRouteId) {
      try {
        const ns = await getRouteNextStop(token, selectedDriverRouteId);
        setDriverNextStop(ns);
        // Sync selected route from fresh list
        const fresh = await getDriverRoutes(token, {
          service_date: new Date().toISOString().slice(0, 10),
        });
        const route = fresh.items.find((r) => r.id === selectedDriverRouteId) ?? null;
        setSelectedDriverRoute(route);
        setDriverRoutes(fresh.items);
      } catch {
        // non-fatal
      }
    }
  }

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
      setViewMode(nextRole === "driver" ? "ops" : "planner");
      setAutoLockResult(null);
      setWeightDrafts({});
      setSavingWeightOrderId(null);
      setVehicleDrafts({});
      setSavingVehiclePlanId(null);
      setSelectedConsolidationPlanId("");
      setPlanConsolidation(null);
      setPlanConsolidationLoading(false);
      if (nextRole === "driver") {
        await refreshDriver(auth.access_token);
      } else {
        await refreshOps(auth.access_token);
        await refreshDispatcher(auth.access_token, nextRole);
      }
      if (nextRole === "admin") {
        await refreshZones(auth.access_token);
        await refreshUsers(auth.access_token);
        await refreshTenantSettings(auth.access_token);
      } else {
        setZones([]);
        setUsers([]);
        setTenantSettings(null);
        setSelectedConsolidationPlanId("");
        setPlanConsolidation(null);
        setPlanConsolidationLoading(false);
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
    setOperationalQueue([]);
    setOperationalResolutionQueue([]);
    setCapacityAlerts([]);
    setPlans([]);
    setSelectedConsolidationPlanId("");
    setPlanConsolidation(null);
    setPlanConsolidationLoading(false);
    setExceptions([]);
    setDispatcherReadyOrders([]);
    setDispatcherVehicles([]);
    setDispatcherRoutes([]);
    setDispatcherRouteStatus("all");
    setDispatcherLoading(false);
    setDispatcherRouteDetailLoading(false);
    setSelectedDispatcherRouteId("");
    setSelectedDispatcherRoute(null);
    setSelectedDispatcherRouteEvents([]);
    setDispatcherPlanId("");
    setDispatcherPlanVehicleId("");
    setDispatcherPlanDriverId("");
    setDispatcherPlanOrderIds("");
    setDispatcherPlanCreating(false);
    setDispatcherOptimizingRouteId(null);
    setDispatcherDispatchingRouteId(null);
    setDispatcherMoveSourceRouteId("");
    setDispatcherMoveStopId("");
    setDispatcherMoveTargetRouteId("");
    setDispatcherMovingStop(false);
    setZones([]);
    setUsers([]);
    setTenantSettings(null);
    // Driver state reset
    setDriverRoutes([]);
    setDriverLoading(false);
    setSelectedDriverRouteId("");
    setSelectedDriverRoute(null);
    setDriverNextStop(null);
    setDriverNextStopLoading(false);
    setDriverActionLoadingStopId(null);
    setDriverIncidentLoading(false);
    setDriverError(null);
    setDriverSuccess(null);
    setViewMode("planner");
    setAutoLockResult(null);
    setAutoLockRunning(false);
    setWeightDrafts({});
    setSavingWeightOrderId(null);
    setVehicleDrafts({});
    setSavingVehiclePlanId(null);
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

  async function onSaveOrderWeight(order: Order) {
    if (!token || !canEditOrderWeight) return;

    const rawValue = (weightDrafts[order.id] ?? "").trim();
    let nextWeight: number | null = null;
    if (rawValue.length > 0) {
      const parsed = Number(rawValue.replace(",", "."));
      if (Number.isNaN(parsed)) {
        setError("Peso inválido. Usa formato numérico (ejemplo: 12.5)");
        return;
      }
      nextWeight = parsed;
    }

    setError("");
    setSavingWeightOrderId(order.id);
    try {
      await updateOrderWeight(token, order.id, { total_weight_kg: nextWeight });
      setWeightDrafts((current) => {
        const next = { ...current };
        delete next[order.id];
        return next;
      });
      await refreshOps();
    } catch (e) {
      setError(formatError(e));
    } finally {
      setSavingWeightOrderId(null);
    }
  }

  async function onSavePlanVehicle(plan: Plan, clear = false) {
    if (!token || !canAssignPlanVehicle) return;

    const rawValue = clear ? "" : (vehicleDrafts[plan.id] ?? plan.vehicle_id ?? "").trim();
    const nextVehicleId = rawValue.length > 0 ? rawValue : null;

    setError("");
    setSavingVehiclePlanId(plan.id);
    try {
      await updatePlanVehicle(token, plan.id, { vehicle_id: nextVehicleId });
      setVehicleDrafts((current) => {
        const next = { ...current };
        delete next[plan.id];
        return next;
      });
      await refreshOps();
    } catch (e) {
      setError(formatError(e));
    } finally {
      setSavingVehiclePlanId(null);
    }
  }

  async function onLoadPlanConsolidation(planId?: string) {
    const targetPlanId = (planId ?? selectedConsolidationPlanId).trim();
    if (!token || !targetPlanId) {
      setError("Selecciona un plan para cargar consolidación");
      return;
    }
    setPlanConsolidationLoading(true);
    try {
      const response = await getPlanCustomerConsolidation(token, targetPlanId);
      setSelectedConsolidationPlanId(targetPlanId);
      setPlanConsolidation(response);
    } catch (e) {
      setError(formatError(e));
    } finally {
      setPlanConsolidationLoading(false);
    }
  }

  async function onCreateDispatcherRoutePlan() {
    if (!token || !canManageRouting) return;
    const nextPlanId = dispatcherPlanId.trim();
    const nextVehicleId = dispatcherPlanVehicleId.trim();
    const nextDriverId = dispatcherPlanDriverId.trim();
    const orderIds = dispatcherPlanOrderIds
      .split(/[\s,]+/g)
      .map((value) => value.trim())
      .filter((value) => value.length > 0);

    if (!nextPlanId) {
      setError("plan_id es obligatorio para planificar ruta");
      return;
    }
    if (!nextVehicleId) {
      setError("vehicle_id es obligatorio para planificar ruta");
      return;
    }
    if (orderIds.length === 0) {
      setError("Debes informar al menos un order_id");
      return;
    }

    setDispatcherPlanCreating(true);
    setError("");
    try {
      await planRoutes(token, {
        plan_id: nextPlanId,
        service_date: serviceDate,
        routes: [
          {
            vehicle_id: nextVehicleId,
            driver_id: nextDriverId || null,
            order_ids: orderIds,
          },
        ],
      });
      setDispatcherPlanOrderIds("");
      await refreshDispatcher();
      await refreshOps();
    } catch (e) {
      setError(formatError(e));
    } finally {
      setDispatcherPlanCreating(false);
    }
  }

  async function onOptimizeDispatcherRoute(routeId: string) {
    if (!token || !canManageRouting) return;
    setDispatcherOptimizingRouteId(routeId);
    setError("");
    try {
      await optimizeRoute(token, routeId);
      await refreshDispatcher();
      await refreshOps();
      showToast("✓ Ruta optimizada — orden de paradas actualizada");
    } catch (e) {
      const msg = formatError(e);
      setError(msg);
      showToast(`Error al optimizar: ${msg}`, "err");
    } finally {
      setDispatcherOptimizingRouteId(null);
    }
  }

  async function onDispatchDispatcherRoute(routeId: string) {
    if (!token || !canManageRouting) return;
    setDispatcherDispatchingRouteId(routeId);
    setError("");
    try {
      await dispatchRoute(token, routeId);
      await refreshDispatcher();
      await refreshOps();
      showToast("✓ Ruta despachada — el conductor ya puede verla");
    } catch (e) {
      const msg = formatError(e);
      setError(msg);
      showToast(`Error al despachar: ${msg}`, "err");
    } finally {
      setDispatcherDispatchingRouteId(null);
    }
  }

  async function onRecalculateDispatcherEta(routeId: string) {
    if (!token || !canManageRouting) return;
    setDispatcherRecalculatingEtaRouteId(routeId);
    setError("");
    try {
      await recalculateEta(token, routeId);
      await onSelectDispatcherRoute(routeId);
      showToast("✓ ETA recalculada");
    } catch (e) {
      const msg = formatError(e);
      setError(msg);
      showToast(`Error al recalcular ETA: ${msg}`, "err");
    } finally {
      setDispatcherRecalculatingEtaRouteId(null);
    }
  }

  async function onMoveDispatcherStop() {
    if (!token || !canManageRouting) return;
    const sourceRouteId = dispatcherMoveSourceRouteId.trim();
    const stopId = dispatcherMoveStopId.trim();
    const targetRouteId = dispatcherMoveTargetRouteId.trim();

    if (!sourceRouteId || !stopId || !targetRouteId) {
      setError("source_route_id, stop_id y target_route_id son obligatorios");
      return;
    }

    setDispatcherMovingStop(true);
    setError("");
    try {
      await moveRouteStop(token, sourceRouteId, {
        stop_id: stopId,
        target_route_id: targetRouteId,
      });
      setDispatcherMoveStopId("");
      await refreshDispatcher();
      await refreshOps();
    } catch (e) {
      setError(formatError(e));
    } finally {
      setDispatcherMovingStop(false);
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

  // ── GlobalShell — vistas de dispatcher (excepto admin que usa AppShell) ─────
  if (isAuthenticated && !isDriver && viewMode !== "admin") {
    const sectionMap: Record<ViewMode, SidebarSection> = {
      ops:       "routes",
      planner:   "planner",
      orders:    "orders",
      customers: "customers",
      drivers:   "drivers",
      templates: "templates",
      insights:  "insights",
      admin:     "settings",
    };
    const activeSection = sectionMap[viewMode] ?? "routes";

    const handleNavigate = (s: SidebarSection) => {
      const vmMap: Record<SidebarSection, ViewMode> = {
        routes:    "ops",
        planner:   "planner",
        orders:    "orders",
        customers: "customers",
        drivers:   "drivers",
        templates: "templates",
        insights:  "insights",
        settings:  "admin",
      };
      const next = vmMap[s];
      if (next === "admin") void refreshZones();
      setViewMode(next);
    };

    return (
      <GlobalShell
        activeSection={activeSection}
        onNavigate={handleNavigate}
        canManageRouting={canManageRouting}
        isAdmin={isAdmin}
        onLogout={onLogout}
      >
        {/* ── Rutas (OpsMapDashboard) ── */}
        {viewMode === "ops" && (
          <OpsMapDashboard
            hideSidebar={true}
            defaultSidebarView="gestion"
            role={role}
            onLogout={onLogout}
            onSwitchToAdmin={
              isAdmin
                ? () => { setViewMode("admin"); void refreshZones(); }
                : undefined
            }
            onSwitchToPlanner={canManageRouting ? () => setViewMode("planner") : undefined}
            isAdmin={isAdmin}
            token={token || undefined}
            error={error}
            summary={summary}
            serviceDate={serviceDate}
            onServiceDateChange={setServiceDate}
            routeStatus={dispatcherRouteStatus}
            onRouteStatusChange={setDispatcherRouteStatus}
            loading={dispatcherLoading}
            routes={dispatcherRoutes}
            selectedRouteId={selectedDispatcherRouteId}
            onSelectedRouteIdChange={onSelectDispatcherRoute}
            selectedRoute={selectedDispatcherRoute}
            routeEvents={selectedDispatcherRouteEvents}
            delayAlerts={selectedDispatcherRouteDelayAlerts}
            routeDetailLoading={dispatcherRouteDetailLoading}
            canManage={canManageRouting}
            driverPosition={dispatcherDriverPosition}
            activePositions={activePositions}
            optimizingRouteId={dispatcherOptimizingRouteId}
            dispatchingRouteId={dispatcherDispatchingRouteId}
            recalculatingEtaRouteId={dispatcherRecalculatingEtaRouteId}
            onOptimizeRoute={(id) => void onOptimizeDispatcherRoute(id)}
            onDispatchRoute={(id) => void onDispatchDispatcherRoute(id)}
            onRecalculateEta={(id) => void onRecalculateDispatcherEta(id)}
            onRefresh={() => void refreshDispatcher()}
            readyOrders={dispatcherReadyOrders}
            availableVehicles={dispatcherVehicles}
            availableDrivers={opsDrivers}
            availablePlans={plans.filter((p) => p.service_date === serviceDate)}
            planId={dispatcherPlanId}
            onPlanIdChange={setDispatcherPlanId}
            planVehicleId={dispatcherPlanVehicleId}
            onPlanVehicleIdChange={setDispatcherPlanVehicleId}
            planDriverId={dispatcherPlanDriverId}
            onPlanDriverIdChange={setDispatcherPlanDriverId}
            planOrderIds={dispatcherPlanOrderIds}
            onPlanOrderIdsChange={setDispatcherPlanOrderIds}
            creatingPlan={dispatcherPlanCreating}
            onCreatePlan={() => void onCreateDispatcherRoutePlan()}
            moveSourceRouteId={dispatcherMoveSourceRouteId}
            onMoveSourceRouteIdChange={setDispatcherMoveSourceRouteId}
            moveStopId={dispatcherMoveStopId}
            onMoveStopIdChange={setDispatcherMoveStopId}
            moveTargetRouteId={dispatcherMoveTargetRouteId}
            onMoveTargetRouteIdChange={setDispatcherMoveTargetRouteId}
            movingStop={dispatcherMovingStop}
            onMoveStop={() => void onMoveDispatcherStop()}
          />
        )}

        {/* ── Planificador ── */}
        {viewMode === "planner" && (
          <RoutePlannerCalendar
            token={token}
            onBack={() => setViewMode("ops")}
            onNewRoute={() => setViewMode("ops")}
          />
        )}

        {/* ── Nuevas secciones ── */}
        {viewMode === "orders"     && <OrdersSection         token={token} />}
        {viewMode === "customers"  && <CustomersSection      token={token} />}
        {viewMode === "drivers"    && <DriversSection        token={token} />}
        {viewMode === "templates"  && <RouteTemplatesSection token={token} />}
        {viewMode === "insights"   && <InsightsSection       token={token} />}

      </GlobalShell>
    );
  }

  const shellSidebar = isAuthenticated ? (
    <SidebarNav
      title={isDriver ? "Modo conductor" : "Ops"}
      items={[
        ...(isDriver
          ? [{ id: "driver", label: "Mis rutas", active: true }]
          : [
            {
              id: "ops",
              label: "Operación",
              active: viewMode === "ops",
              onClick: () => setViewMode("ops"),
            },
            ...(isAdmin
              ? [
                {
                  id: "admin",
                  label: "Admin",
                  active: viewMode === "admin",
                  onClick: () => {
                    setViewMode("admin");
                    void refreshZones();
                  },
                },
              ]
              : []),
          ]),
      ]}
    />
  ) : undefined;

  const shellTabs =
    isAuthenticated && !isDriver ? (
      <TopTabs
        items={[
          { id: "ops-tab", label: "Operación", active: viewMode === "ops", onClick: () => setViewMode("ops") },
          ...(isAdmin
            ? [
              {
                id: "admin-tab",
                label: "Admin",
                active: viewMode === "admin",
                onClick: () => {
                  setViewMode("admin");
                  void refreshZones();
                },
              },
            ]
            : []),
        ]}
      />
    ) : undefined;

  // DRIVER-MOBILE-001 — bypass AppShell entirely for conductores
  if (isAuthenticated && isDriver) {
    return (
      <DriverMobileView
        loading={driverLoading}
        routes={driverRoutes}
        selectedRouteId={selectedDriverRouteId}
        onSelectedRouteIdChange={(id) => void onSelectDriverRoute(id)}
        selectedRoute={selectedDriverRoute}
        nextStopResponse={driverNextStop}
        nextStopLoading={driverNextStopLoading}
        actionLoadingStopId={driverActionLoadingStopId}
        incidentLoading={driverIncidentLoading}
        proofLoading={driverProofLoading}
        errorMessage={driverError}
        successMessage={driverSuccess}
        token={token}
        apiBaseUrl={process.env.NEXT_PUBLIC_API_BASE_URL ?? ""}
        onRefresh={() => void refreshDriver()}
        onArrive={(stopId) => void onDriverArrive(stopId)}
        onComplete={(stopId) => void onDriverComplete(stopId)}
        onCompleteWithProof={(stopId, sig, signedBy) => void onDriverCompleteWithProof(stopId, sig, signedBy)}
        onFail={(stopId, reason) => void onDriverFail(stopId, reason)}
        onSkip={(stopId) => void onDriverSkip(stopId)}
        onReportIncident={(payload) => void onDriverReportIncident(payload)}
        onLogout={onLogout}
      />
    );
  }

  return (
    <AppShell
      header={
        <SectionHeader
          title="CorteCero Ops"
          subtitle="Cut-off, lock y excepciones con trazabilidad operativa"
          actions={
            isAuthenticated ? (
              <div className="row">
                <span className="pill">Rol: {role ?? "desconocido"}</span>
                <button className="secondary" onClick={onLogout}>
                  Cerrar sesión
                </button>
              </div>
            ) : null
          }
        />
      }
      topTabs={shellTabs}
      banner={error ? <GlobalBanner tone="error">{error}</GlobalBanner> : undefined}
      sidebar={shellSidebar}
    >
      {!isAuthenticated && (
        <div className="login-screen">
          <div className="login-card">
            <div className="login-logo">
              <div className="login-logo-icon">C</div>
              <div>
                <div className="login-logo-name">CorteCero</div>
                <div className="login-logo-sub">Panel operativo</div>
              </div>
            </div>

            <div className="login-tagline">
              Gestión de rutas y distribución con trazabilidad operativa
            </div>

            <div className="login-form">
              <div className="login-field">
                <label className="login-label">Organización</label>
                <input
                  className="login-input"
                  placeholder="demo-cortecero"
                  value={tenantSlug}
                  onChange={(e) => setTenantSlug(e.target.value)}
                  autoComplete="organization"
                />
              </div>
              <div className="login-field">
                <label className="login-label">Email</label>
                <input
                  className="login-input"
                  placeholder="usuario@empresa.com"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                />
              </div>
              <div className="login-field">
                <label className="login-label">Contraseña</label>
                <input
                  className="login-input"
                  placeholder="••••••••"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  onKeyDown={(e) => e.key === "Enter" && onLogin()}
                />
              </div>
              <button className="login-btn" onClick={onLogin}>
                Entrar →
              </button>
            </div>

            <div className="login-footer">
              Acceso restringido · Solo usuarios autorizados
            </div>
          </div>
        </div>
      )}

      {isAuthenticated && !isDriver && viewMode === "ops" && (
        <>
          {summary && <KpiRow summary={summary} />}

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

          <DispatcherRoutingShell
            serviceDate={serviceDate}
            onServiceDateChange={setServiceDate}
            onRefresh={() => void refreshOps()}
            loading={dispatcherLoading}
            routeCount={dispatcherRoutes.length}
            readyOrderCount={dispatcherReadyOrders.length}
            vehicleCount={dispatcherVehicles.length}
          >
            {canViewRouting ? (
              <DispatcherRoutingCard
                serviceDate={serviceDate}
                onServiceDateChange={setServiceDate}
                routeStatus={dispatcherRouteStatus}
                onRouteStatusChange={setDispatcherRouteStatus}
                loading={dispatcherLoading}
                canManage={canManageRouting}
                readyOrders={dispatcherReadyOrders}
                availableVehicles={dispatcherVehicles}
                routes={dispatcherRoutes}
                selectedRouteId={selectedDispatcherRouteId}
                onSelectedRouteIdChange={onSelectDispatcherRoute}
                selectedRoute={selectedDispatcherRoute}
                routeEvents={selectedDispatcherRouteEvents}
                routeDetailLoading={dispatcherRouteDetailLoading}
                planId={dispatcherPlanId}
                onPlanIdChange={setDispatcherPlanId}
                planVehicleId={dispatcherPlanVehicleId}
                onPlanVehicleIdChange={setDispatcherPlanVehicleId}
                planDriverId={dispatcherPlanDriverId}
                onPlanDriverIdChange={setDispatcherPlanDriverId}
                planOrderIds={dispatcherPlanOrderIds}
                onPlanOrderIdsChange={setDispatcherPlanOrderIds}
                creatingPlan={dispatcherPlanCreating}
                optimizingRouteId={dispatcherOptimizingRouteId}
                dispatchingRouteId={dispatcherDispatchingRouteId}
                recalculatingEtaRouteId={dispatcherRecalculatingEtaRouteId}
                moveSourceRouteId={dispatcherMoveSourceRouteId}
                onMoveSourceRouteIdChange={setDispatcherMoveSourceRouteId}
                moveStopId={dispatcherMoveStopId}
                onMoveStopIdChange={setDispatcherMoveStopId}
                moveTargetRouteId={dispatcherMoveTargetRouteId}
                onMoveTargetRouteIdChange={setDispatcherMoveTargetRouteId}
                movingStop={dispatcherMovingStop}
                onRefresh={() => void refreshDispatcher()}
                onCreatePlan={() => void onCreateDispatcherRoutePlan()}
                onOptimizeRoute={(routeId) => void onOptimizeDispatcherRoute(routeId)}
                onDispatchRoute={(routeId) => void onDispatchDispatcherRoute(routeId)}
                onRecalculateEta={(routeId) => void onRecalculateDispatcherEta(routeId)}
                onMoveStop={() => void onMoveDispatcherStop()}
                driverPosition={dispatcherDriverPosition}
              />
            ) : (
              <div className="card" style={{ borderColor: "#fca5a5", color: "#991b1b" }}>
                RBAC_FORBIDDEN: El panel dispatcher requiere rol office/logistics/admin.
              </div>
            )}
          </DispatcherRoutingShell>

          <div className="grid cols-2">
            <div className="grid plans-column">
              <PlansTableCard
                plans={plans}
                canRunAutoLock={canRunAutoLock}
                autoLockRunning={autoLockRunning}
                autoLockResult={autoLockResult}
                onRunAutoLock={onRunAutoLock}
                newPlanZoneId={newPlanZoneId}
                onNewPlanZoneIdChange={setNewPlanZoneId}
                onCreatePlan={onCreatePlan}
                includePlanId={includePlanId}
                onIncludePlanIdChange={setIncludePlanId}
                includeOrderId={includeOrderId}
                onIncludeOrderIdChange={setIncludeOrderId}
                onIncludeOrder={onIncludeOrder}
                canAssignPlanVehicle={canAssignPlanVehicle}
                vehicleDrafts={vehicleDrafts}
                onVehicleDraftChange={(planId, value) =>
                  setVehicleDrafts((current) => ({
                    ...current,
                    [planId]: value,
                  }))
                }
                savingVehiclePlanId={savingVehiclePlanId}
                onSavePlanVehicle={(plan, clear) => void onSavePlanVehicle(plan, clear)}
                onLockPlan={onLockPlan}
                onLoadPlanConsolidation={(planId) => void onLoadPlanConsolidation(planId)}
                planConsolidationLoading={planConsolidationLoading}
                shortId={shortId}
              />

              <PlanConsolidationCard
                plans={plans}
                selectedConsolidationPlanId={selectedConsolidationPlanId}
                onSelectedConsolidationPlanIdChange={setSelectedConsolidationPlanId}
                onLoadPlanConsolidation={() => void onLoadPlanConsolidation()}
                planConsolidationLoading={planConsolidationLoading}
                planConsolidation={planConsolidation}
                shortId={shortId}
              />
            </div>

            <ExceptionsTableCard
              exceptionOrderId={exceptionOrderId}
              onExceptionOrderIdChange={setExceptionOrderId}
              exceptionNote={exceptionNote}
              onExceptionNoteChange={setExceptionNote}
              onCreateException={() => void onCreateException()}
              exceptions={exceptions}
              onApproveException={(exceptionId) => void onApproveException(exceptionId)}
              onRejectException={(exceptionId) => void onRejectException(exceptionId)}
            />
          </div>

          <CapacityAlertsTableCard
            serviceDate={serviceDate}
            onServiceDateChange={setServiceDate}
            zoneId={capacityAlertZoneId}
            onZoneIdChange={setCapacityAlertZoneId}
            zoneOptions={pendingQueueZoneOptions}
            level={capacityAlertLevel}
            onLevelChange={setCapacityAlertLevel}
            alerts={capacityAlerts}
            onApplyFilters={() => void refreshOps()}
          />

          <PendingQueueTableCard
            serviceDate={serviceDate}
            onServiceDateChange={setServiceDate}
            zoneId={pendingQueueZoneId}
            onZoneIdChange={setPendingQueueZoneId}
            zoneOptions={pendingQueueZoneOptions}
            reason={pendingQueueReason}
            onReasonChange={setPendingQueueReason}
            items={pendingQueue}
            onApplyFilters={() => void refreshOps()}
          />

          <OperationalQueueTableCard
            serviceDate={serviceDate}
            onServiceDateChange={setServiceDate}
            zoneId={operationalQueueZoneId}
            onZoneIdChange={setOperationalQueueZoneId}
            zoneOptions={operationalQueueZoneOptions}
            reason={operationalQueueReason}
            onReasonChange={setOperationalQueueReason}
            reasonOptions={operationalQueueReasonOptions}
            items={operationalQueue}
            onApplyFilters={() => void refreshOps()}
          />

          <OperationalResolutionQueueTableCard
            serviceDate={serviceDate}
            onServiceDateChange={setServiceDate}
            zoneId={operationalResolutionQueueZoneId}
            onZoneIdChange={setOperationalResolutionQueueZoneId}
            zoneOptions={operationalResolutionQueueZoneOptions}
            reason={operationalResolutionQueueReason}
            onReasonChange={setOperationalResolutionQueueReason}
            reasonOptions={operationalResolutionQueueReasonOptions}
            severity={operationalResolutionQueueSeverity}
            onSeverityChange={setOperationalResolutionQueueSeverity}
            severityOptions={OPERATIONAL_SEVERITY_ORDER}
            items={operationalResolutionQueue}
            onApplyFilters={() => void refreshOps()}
          />

          <OrderSnapshotsTimelineCard
            selectedOrderId={selectedSnapshotOrderId}
            onSelectedOrderIdChange={onSnapshotOrderChange}
            orderOptions={snapshotOrderOptions}
            items={orderOperationalSnapshots}
            loading={orderOperationalSnapshotsLoading}
            error={orderOperationalSnapshotsError}
            onLoad={() => void loadOrderOperationalSnapshots()}
          />

          <OrdersTableCard
            ordersOperationalStateFilter={ordersOperationalStateFilter}
            onOrdersOperationalStateFilterChange={setOrdersOperationalStateFilter}
            ordersOperationalReasonFilter={ordersOperationalReasonFilter}
            onOrdersOperationalReasonFilterChange={setOrdersOperationalReasonFilter}
            ordersOperationalReasonOptions={ordersOperationalReasonOptions}
            onRefresh={() => void refreshOps()}
            filteredOrders={filteredOrders}
            canEditOrderWeight={canEditOrderWeight}
            weightDrafts={weightDrafts}
            onWeightDraftChange={(orderId, value) =>
              setWeightDrafts((current) => ({
                ...current,
                [orderId]: value,
              }))
            }
            savingWeightOrderId={savingWeightOrderId}
            onSaveOrderWeight={(order) => void onSaveOrderWeight(order)}
            shortId={shortId}
            intakeBadgeMeta={intakeBadgeMeta}
            operationalStateBadgeMeta={operationalStateBadgeMeta}
            operationalReasonBadgeClass={operationalReasonBadgeClass}
            operationalSeverityBadgeClass={operationalSeverityBadgeClass}
          />
        </>
      )}

      {isAuthenticated && !isDriver && viewMode === "admin" && (
        <>
          {!isAdmin && (
            <div className="card" style={{ borderColor: "#fca5a5", color: "#991b1b" }}>
              RBAC_FORBIDDEN: Solo `admin` puede acceder a esta sección.
            </div>
          )}

          {isAdmin && (
            <>
              <AdminShell
                activeSection={adminSection}
                onSectionChange={(sec) => {
                  setAdminSection(sec);
                  if (sec === "zones") {
                    void refreshZones();
                  } else if (sec === "customers") {
                    void refreshZones();
                  } else if (sec === "users") {
                    void refreshUsers();
                  } else if (sec === "tenant") {
                    void refreshTenantSettings();
                  }
                }}
              >

                {adminSection === "zones" && <AdminZonesSection token={token} />}

                {adminSection === "customers" && <AdminCustomersSection token={token} zones={zones} />}

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

                {adminSection === "products" && (
                  <AdminProductsCard token={token} />
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
              </AdminShell>
            </>
          )}
        </>
      )}
      {toastMsg && (
        <div
          style={{
            position: "fixed",
            bottom: 28,
            left: "50%",
            transform: "translateX(-50%)",
            background: toastMsg.kind === "ok" ? "#166534" : "#991b1b",
            color: "#fff",
            padding: "10px 22px",
            borderRadius: 8,
            fontSize: 13,
            fontWeight: 500,
            zIndex: 9999,
            pointerEvents: "none",
            boxShadow: "0 4px 16px rgba(0,0,0,0.20)",
            whiteSpace: "nowrap",
          }}
        >
          {toastMsg.text}
        </div>
      )}
    </AppShell>
  );
}
