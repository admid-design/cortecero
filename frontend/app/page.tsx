"use client";

import { useCallback, useMemo, useState } from "react";

import {
  type AdminUser,
  type IncidentCreateRequest,
  type RouteNextStopResponse,
  APIError,
  formatError,
  arriveStop,
  completeStop,
  failStop,
  skipStop,
  createIncident,
  getDriverRoutes,
  getRouteNextStop,
  approveException,
  createAdminCustomer,
  createAdminCustomerOperationalException,
  createAdminUser,
  createAdminZone,
  createException,
  createPlan,
  deactivateAdminCustomer,
  deleteAdminCustomerOperationalException,
  deactivateAdminZone,
  dispatchRoute,
  getDailySummary,
  getPlanCapacityAlerts,
  getPlanCustomerConsolidation,
  getAdminCustomerOperationalProfile,
  getSourceMetrics,
  getAdminTenantSettings,
  getRoute,
  includeOrderInPlan,
  listAvailableVehicles,
  listOrderOperationalSnapshots,
  listOperationalQueue,
  listOperationalResolutionQueue,
  listPendingQueue,
  listAdminCustomers,
  listAdminCustomerOperationalExceptions,
  listReadyToDispatchOrders,
  listRouteEvents,
  listRoutes,
  listAdminUsers,
  listAdminZones,
  listExceptions,
  listOrders,
  listPlans,
  lockPlan,
  login,
  moveRouteStop,
  optimizeRoute,
  planRoutes,
  rejectException,
  runAutoLock,
  updatePlanVehicle,
  updateOrderWeight,
  updateAdminCustomer,
  putAdminCustomerOperationalProfile,
  updateAdminTenantSettings,
  updateAdminUser,
  updateAdminZone,
  type AutoLockRunResponse,
  type AvailableVehicleItem,
  type CapacityAlertLevel,
  type Customer,
  type CustomerOperationalException,
  type CustomerOperationalExceptionType,
  type CustomerOperationalProfile,
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
  type Plan,
  type PlanCapacityAlert,
  type PlanCustomerConsolidationResponse,
  type ReadyToDispatchItem,
  type RouteEventItem,
  type RoutingRoute,
  type RoutingRouteStatus,
  type TenantSettings,
  type UserRole,
  type Zone,
} from "../lib/api";
import { DispatcherRoutingCard } from "../components/DispatcherRoutingCard";
import { DriverRoutingCard } from "../components/DriverRoutingCard";
import { OperationalQueueCard } from "../components/OperationalQueueCard";
import { OperationalResolutionQueueCard } from "../components/OperationalResolutionQueueCard";
import { OrderOperationalSnapshotsCard } from "../components/OrderOperationalSnapshotsCard";
import { PendingQueueTableCard } from "../components/PendingQueueTableCard";
import { AdminProductsCard } from "../components/AdminProductsCard";
import { OrdersTableCard } from "../components/OrdersTableCard";
import { PlansTableCard } from "../components/PlansTableCard";
import { PlanConsolidationCard } from "../components/PlanConsolidationCard";
import { AppShell, GlobalBanner, SectionHeader, SidebarNav, TopTabs } from "../components/AppShell";
import { KpiRow } from "../components/KpiRow";
import { DispatcherRoutingShell } from "../components/DispatcherRoutingShell";

type ViewMode = "ops" | "admin";
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
  const [dispatcherPlanId, setDispatcherPlanId] = useState("");
  const [dispatcherPlanVehicleId, setDispatcherPlanVehicleId] = useState("");
  const [dispatcherPlanDriverId, setDispatcherPlanDriverId] = useState("");
  const [dispatcherPlanOrderIds, setDispatcherPlanOrderIds] = useState("");
  const [dispatcherPlanCreating, setDispatcherPlanCreating] = useState(false);
  const [dispatcherOptimizingRouteId, setDispatcherOptimizingRouteId] = useState<string | null>(null);
  const [dispatcherDispatchingRouteId, setDispatcherDispatchingRouteId] = useState<string | null>(null);
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
  const [operationalProfile, setOperationalProfile] = useState<CustomerOperationalProfile | null>(null);
  const [operationalProfileLoading, setOperationalProfileLoading] = useState(false);
  const [operationalProfileSaving, setOperationalProfileSaving] = useState(false);
  const [opAcceptOrders, setOpAcceptOrders] = useState(true);
  const [opWindowStart, setOpWindowStart] = useState("");
  const [opWindowEnd, setOpWindowEnd] = useState("");
  const [opMinLeadHours, setOpMinLeadHours] = useState("0");
  const [opConsolidateByDefault, setOpConsolidateByDefault] = useState(false);
  const [opOpsNote, setOpOpsNote] = useState("");
  const [operationalExceptions, setOperationalExceptions] = useState<CustomerOperationalException[]>([]);
  const [operationalExceptionsLoading, setOperationalExceptionsLoading] = useState(false);
  const [operationalExceptionCreating, setOperationalExceptionCreating] = useState(false);
  const [operationalExceptionDeletingId, setOperationalExceptionDeletingId] = useState<string | null>(null);
  const [opExceptionDate, setOpExceptionDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [opExceptionType, setOpExceptionType] = useState<CustomerOperationalExceptionType>("blocked");
  const [opExceptionNote, setOpExceptionNote] = useState("");

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
  const [driverError, setDriverError] = useState<string | null>(null);
  const [driverSuccess, setDriverSuccess] = useState<string | null>(null);

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
        const [routeRes, eventsRes] = await Promise.all([
          getRoute(activeToken, routeId),
          listRouteEvents(activeToken, routeId),
        ]);
        setSelectedDispatcherRoute(routeRes);
        setSelectedDispatcherRouteEvents(eventsRes.items ?? []);
        setDispatcherMoveSourceRouteId(routeRes.id);
      } catch (e) {
        setError(formatError(e));
        setSelectedDispatcherRoute(null);
        setSelectedDispatcherRouteEvents([]);
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
          const [readyRes, vehiclesRes] = await Promise.all([
            listReadyToDispatchOrders(activeToken, { service_date: serviceDate }),
            listAvailableVehicles(activeToken, { service_date: serviceDate }),
          ]);
          setDispatcherReadyOrders(readyRes.items ?? []);
          setDispatcherVehicles(vehiclesRes.items ?? []);
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

  const fillOperationalProfileForm = useCallback((profile: CustomerOperationalProfile) => {
    setOperationalProfile(profile);
    setOpAcceptOrders(profile.accept_orders);
    setOpWindowStart(profile.window_start ?? "");
    setOpWindowEnd(profile.window_end ?? "");
    setOpMinLeadHours(String(profile.min_lead_hours));
    setOpConsolidateByDefault(profile.consolidate_by_default);
    setOpOpsNote(profile.ops_note ?? "");
  }, []);

  const resetOperationalProfileForm = useCallback(() => {
    setOperationalProfile(null);
    setOpAcceptOrders(true);
    setOpWindowStart("");
    setOpWindowEnd("");
    setOpMinLeadHours("0");
    setOpConsolidateByDefault(false);
    setOpOpsNote("");
  }, []);

  const loadCustomerOperationalProfile = useCallback(async (customerId: string, authToken?: string) => {
    const activeToken = authToken ?? token;
    if (!activeToken || !customerId) return;
    setOperationalProfileLoading(true);
    try {
      const profile = await getAdminCustomerOperationalProfile(activeToken, customerId);
      fillOperationalProfileForm(profile);
    } catch (e) {
      setError(formatError(e));
    } finally {
      setOperationalProfileLoading(false);
    }
  }, [fillOperationalProfileForm, token]);

  const resetOperationalExceptionsState = useCallback(() => {
    setOperationalExceptions([]);
    setOperationalExceptionsLoading(false);
    setOperationalExceptionCreating(false);
    setOperationalExceptionDeletingId(null);
    setOpExceptionDate(new Date().toISOString().slice(0, 10));
    setOpExceptionType("blocked");
    setOpExceptionNote("");
  }, []);

  const loadCustomerOperationalExceptions = useCallback(async (customerId: string, authToken?: string) => {
    const activeToken = authToken ?? token;
    if (!activeToken || !customerId) return;
    setOperationalExceptionsLoading(true);
    try {
      const data = await listAdminCustomerOperationalExceptions(activeToken, customerId);
      setOperationalExceptions(data.items ?? []);
    } catch (e) {
      setError(formatError(e));
    } finally {
      setOperationalExceptionsLoading(false);
    }
  }, [token]);

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
      setViewMode("ops");
      setAutoLockResult(null);
      setWeightDrafts({});
      setSavingWeightOrderId(null);
      setVehicleDrafts({});
      setSavingVehiclePlanId(null);
      setSelectedConsolidationPlanId("");
      setPlanConsolidation(null);
      setPlanConsolidationLoading(false);
      resetOperationalProfileForm();
      resetOperationalExceptionsState();
      if (nextRole === "driver") {
        await refreshDriver(auth.access_token);
      } else {
        await refreshOps(auth.access_token);
        await refreshDispatcher(auth.access_token, nextRole);
      }
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
        setSelectedConsolidationPlanId("");
        setPlanConsolidation(null);
        setPlanConsolidationLoading(false);
        resetOperationalProfileForm();
        resetOperationalExceptionsState();
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
    setCustomers([]);
    setUsers([]);
    setTenantSettings(null);
    resetOperationalProfileForm();
    resetOperationalExceptionsState();
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
    setViewMode("ops");
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
    } catch (e) {
      setError(formatError(e));
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
    } catch (e) {
      setError(formatError(e));
    } finally {
      setDispatcherDispatchingRouteId(null);
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
    void loadCustomerOperationalProfile(customer.id);
    void loadCustomerOperationalExceptions(customer.id);
  }

  function cancelEditCustomer() {
    setEditingCustomerId("");
    resetOperationalProfileForm();
    resetOperationalExceptionsState();
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
      await loadCustomerOperationalProfile(editingCustomerId);
      await loadCustomerOperationalExceptions(editingCustomerId);
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
        resetOperationalProfileForm();
        resetOperationalExceptionsState();
      }
      await refreshCustomers();
    } catch (e) {
      setError(formatError(e));
    }
  }

  async function onSaveOperationalProfile() {
    if (!token || !isAdmin || !editingCustomerId) return;
    const parsedMinLead = Number.parseInt(opMinLeadHours, 10);
    if (Number.isNaN(parsedMinLead)) {
      setError("min_lead_hours debe ser un entero");
      return;
    }
    setOperationalProfileSaving(true);
    try {
      const updated = await putAdminCustomerOperationalProfile(token, editingCustomerId, {
        accept_orders: opAcceptOrders,
        window_start: opWindowStart.trim() || null,
        window_end: opWindowEnd.trim() || null,
        min_lead_hours: parsedMinLead,
        consolidate_by_default: opConsolidateByDefault,
        ops_note: opOpsNote.trim() || null,
      });
      fillOperationalProfileForm(updated);
    } catch (e) {
      setError(formatError(e));
    } finally {
      setOperationalProfileSaving(false);
    }
  }

  async function onCreateOperationalException() {
    if (!token || !isAdmin || !editingCustomerId) return;
    if (!opExceptionDate.trim()) {
      setError("date es obligatoria");
      return;
    }
    if (!opExceptionNote.trim()) {
      setError("note es obligatoria");
      return;
    }

    setOperationalExceptionCreating(true);
    try {
      await createAdminCustomerOperationalException(token, editingCustomerId, {
        date: opExceptionDate,
        type: opExceptionType,
        note: opExceptionNote.trim(),
      });
      setOpExceptionNote("");
      await loadCustomerOperationalExceptions(editingCustomerId);
    } catch (e) {
      setError(formatError(e));
    } finally {
      setOperationalExceptionCreating(false);
    }
  }

  async function onDeleteOperationalException(exceptionId: string) {
    if (!token || !isAdmin || !editingCustomerId) return;
    const confirmed = window.confirm("¿Eliminar esta excepción operativa?");
    if (!confirmed) return;

    setOperationalExceptionDeletingId(exceptionId);
    try {
      await deleteAdminCustomerOperationalException(token, editingCustomerId, exceptionId);
      await loadCustomerOperationalExceptions(editingCustomerId);
    } catch (e) {
      setError(formatError(e));
    } finally {
      setOperationalExceptionDeletingId(null);
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
        <div className="card grid cols-2">
          <input placeholder="tenant_slug" value={tenantSlug} onChange={(e) => setTenantSlug(e.target.value)} />
          <input placeholder="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <input placeholder="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <button onClick={onLogin}>Entrar</button>
        </div>
      )}

      {isAuthenticated && isDriver && (
        <DriverRoutingCard
          loading={driverLoading}
          routes={driverRoutes}
          selectedRouteId={selectedDriverRouteId}
          onSelectedRouteIdChange={(id) => void onSelectDriverRoute(id)}
          selectedRoute={selectedDriverRoute}
          nextStopResponse={driverNextStop}
          nextStopLoading={driverNextStopLoading}
          actionLoadingStopId={driverActionLoadingStopId}
          incidentLoading={driverIncidentLoading}
          errorMessage={driverError}
          successMessage={driverSuccess}
          onRefresh={() => void refreshDriver()}
          onArrive={(stopId) => void onDriverArrive(stopId)}
          onComplete={(stopId) => void onDriverComplete(stopId)}
          onFail={(stopId, reason) => void onDriverFail(stopId, reason)}
          onSkip={(stopId) => void onDriverSkip(stopId)}
          onReportIncident={(payload) => void onDriverReportIncident(payload)}
        />
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
                onMoveStop={() => void onMoveDispatcherStop()}
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
            <h2>Alertas de Capacidad</h2>
            <div className="row">
              <label>
                service_date{" "}
                <input type="date" value={serviceDate} onChange={(e) => setServiceDate(e.target.value)} />
              </label>
              <label>
                zone_id{" "}
                <select value={capacityAlertZoneId} onChange={(e) => setCapacityAlertZoneId(e.target.value)}>
                  <option value="all">all</option>
                  {pendingQueueZoneOptions.map((zoneId) => (
                    <option key={zoneId} value={zoneId}>
                      {zoneId}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                level{" "}
                <select
                  value={capacityAlertLevel}
                  onChange={(e) => setCapacityAlertLevel(e.target.value as "all" | CapacityAlertLevel)}
                >
                  <option value="all">all</option>
                  <option value="OVER_CAPACITY">OVER_CAPACITY</option>
                  <option value="NEAR_CAPACITY">NEAR_CAPACITY</option>
                </select>
              </label>
              <button className="secondary" onClick={() => void refreshOps()}>
                Aplicar filtros
              </button>
            </div>
            <table>
              <thead>
                <tr>
                  <th>plan_id</th>
                  <th>zone_id</th>
                  <th>vehículo</th>
                  <th>peso_kg</th>
                  <th>capacidad_kg</th>
                  <th>usage_ratio</th>
                  <th>alert_level</th>
                </tr>
              </thead>
              <tbody>
                {capacityAlerts.length === 0 && (
                  <tr>
                    <td colSpan={7} style={{ color: "#6b7280" }}>
                      Sin alertas para los filtros actuales.
                    </td>
                  </tr>
                )}
                {capacityAlerts.map((item) => (
                  <tr key={item.plan_id}>
                    <td>{shortId(item.plan_id)}</td>
                    <td>{shortId(item.zone_id)}</td>
                    <td>{item.vehicle_name ?? item.vehicle_code ?? shortId(item.vehicle_id)}</td>
                    <td>{item.total_weight_kg}</td>
                    <td>{item.vehicle_capacity_kg}</td>
                    <td>{item.usage_ratio.toFixed(2)}</td>
                    <td>
                      <span className={item.alert_level === "OVER_CAPACITY" ? "badge rejected" : "badge late"}>
                        {item.alert_level}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

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

          <OperationalQueueCard
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

          <OperationalResolutionQueueCard
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

          <OrderOperationalSnapshotsCard
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
                  className={adminSection === "products" ? "tab active" : "tab muted"}
                  onClick={() => setAdminSection("products")}
                >
                  Productos
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

                    <div className="card grid">
                      <h2>Perfil Operativo</h2>
                      {!editingCustomerId && (
                        <p style={{ margin: 0, color: "#6b7280" }}>
                          Selecciona un cliente (Editar) para ver y actualizar su perfil operativo.
                        </p>
                      )}
                      {editingCustomerId && (
                        <>
                          {operationalProfileLoading && <p style={{ margin: 0, color: "#6b7280" }}>Cargando perfil...</p>}
                          {operationalProfile && (
                            <div className="row" style={{ gap: 6 }}>
                              <span className="pill">window_mode: {operationalProfile.window_mode}</span>
                              <span className="pill">tz: {operationalProfile.evaluation_timezone}</span>
                              <span className="pill">customized: {operationalProfile.is_customized ? "true" : "false"}</span>
                            </div>
                          )}

                          <label className="row" style={{ gap: 6 }}>
                            <input
                              type="checkbox"
                              checked={opAcceptOrders}
                              onChange={(e) => setOpAcceptOrders(e.target.checked)}
                            />
                            accept_orders
                          </label>

                          <input
                            placeholder="window_start HH:MM:SS (opcional)"
                            value={opWindowStart}
                            onChange={(e) => setOpWindowStart(e.target.value)}
                          />
                          <input
                            placeholder="window_end HH:MM:SS (opcional)"
                            value={opWindowEnd}
                            onChange={(e) => setOpWindowEnd(e.target.value)}
                          />
                          <input
                            placeholder="min_lead_hours (entero >= 0)"
                            value={opMinLeadHours}
                            onChange={(e) => setOpMinLeadHours(e.target.value)}
                          />

                          <label className="row" style={{ gap: 6 }}>
                            <input
                              type="checkbox"
                              checked={opConsolidateByDefault}
                              onChange={(e) => setOpConsolidateByDefault(e.target.checked)}
                            />
                            consolidate_by_default
                          </label>

                          <textarea
                            placeholder="ops_note (opcional)"
                            value={opOpsNote}
                            onChange={(e) => setOpOpsNote(e.target.value)}
                            rows={4}
                          />

                          <div className="row">
                            <button onClick={onSaveOperationalProfile} disabled={operationalProfileSaving}>
                              {operationalProfileSaving ? "Guardando..." : "Guardar perfil"}
                            </button>
                            <button
                              className="secondary"
                              onClick={() => {
                                void loadCustomerOperationalProfile(editingCustomerId);
                              }}
                              disabled={operationalProfileLoading || operationalProfileSaving}
                            >
                              Recargar perfil
                            </button>
                          </div>
                        </>
                      )}
                    </div>

                    <div className="card grid">
                      <h2>Excepciones Operativas</h2>
                      {!editingCustomerId && (
                        <p style={{ margin: 0, color: "#6b7280" }}>
                          Selecciona un cliente (Editar) para gestionar excepciones por fecha.
                        </p>
                      )}
                      {editingCustomerId && (
                        <>
                          <div className="row">
                            <input type="date" value={opExceptionDate} onChange={(e) => setOpExceptionDate(e.target.value)} />
                            <select
                              value={opExceptionType}
                              onChange={(e) => setOpExceptionType(e.target.value as CustomerOperationalExceptionType)}
                            >
                              <option value="blocked">blocked</option>
                              <option value="restricted">restricted</option>
                            </select>
                          </div>
                          <input
                            placeholder="note (obligatoria)"
                            value={opExceptionNote}
                            onChange={(e) => setOpExceptionNote(e.target.value)}
                          />
                          <div className="row">
                            <button onClick={onCreateOperationalException} disabled={operationalExceptionCreating}>
                              {operationalExceptionCreating ? "Creando..." : "Crear excepción"}
                            </button>
                            <button
                              className="secondary"
                              onClick={() => {
                                void loadCustomerOperationalExceptions(editingCustomerId);
                              }}
                              disabled={operationalExceptionsLoading || operationalExceptionCreating}
                            >
                              Recargar excepciones
                            </button>
                          </div>

                          {operationalExceptionsLoading && (
                            <p style={{ margin: 0, color: "#6b7280" }}>Cargando excepciones...</p>
                          )}

                          <table>
                            <thead>
                              <tr>
                                <th>date</th>
                                <th>type</th>
                                <th>note</th>
                                <th>created_at</th>
                                <th>acción</th>
                              </tr>
                            </thead>
                            <tbody>
                              {operationalExceptions.length === 0 && (
                                <tr>
                                  <td colSpan={5} style={{ color: "#6b7280" }}>
                                    Sin excepciones operativas para este cliente.
                                  </td>
                                </tr>
                              )}
                              {operationalExceptions.map((item) => (
                                <tr key={item.id}>
                                  <td>{item.date}</td>
                                  <td>{item.type}</td>
                                  <td>{item.note}</td>
                                  <td>{new Date(item.created_at).toLocaleString("es-ES")}</td>
                                  <td>
                                    <button
                                      className="danger"
                                      onClick={() => {
                                        void onDeleteOperationalException(item.id);
                                      }}
                                      disabled={operationalExceptionDeletingId === item.id}
                                    >
                                      {operationalExceptionDeletingId === item.id ? "Eliminando..." : "Eliminar"}
                                    </button>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
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
            </>
          )}
        </>
      )}
    </AppShell>
  );
}
