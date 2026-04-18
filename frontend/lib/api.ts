export type UserRole = "office" | "logistics" | "admin" | "driver";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type QueryValue = string | number | boolean | null | undefined;

type RequestOptions = {
  token?: string;
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  headers?: Record<string, string>;
};

export class APIError extends Error {
  status: number;
  code?: string;
  detailMessage: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "APIError";
    this.status = status;
    this.code = code;
    this.detailMessage = message;
  }
}

export function formatError(error: unknown): string {
  if (error instanceof APIError) {
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return "Error inesperado";
}

function buildQuery(params: Record<string, QueryValue>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { token, method = "GET", body, headers = {} } = options;
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as
      | { detail?: { code?: string; message?: string } | string }
      | null;
    const detail = payload?.detail;
    const code = typeof detail === "object" && detail ? detail.code : undefined;
    const detailMessage =
      typeof detail === "object" && detail
        ? detail.message || "Error API"
        : typeof detail === "string"
          ? detail
          : `HTTP ${response.status}`;
    const message = code ? `${code}: ${detailMessage}` : detailMessage;
    throw new APIError(message, response.status, code);
  }

  return (await response.json()) as T;
}

export type LoginRequest = {
  tenant_slug: string;
  email: string;
  password: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
};

export type DashboardSummary = {
  service_date: string;
  total_orders: number;
  late_orders: number;
  plans_open: number;
  plans_locked: number;
  pending_exceptions: number;
  approved_exceptions: number;
  rejected_exceptions: number;
};

export type DashboardSourceMetricsItem = {
  source_channel: "sales" | "office" | "direct_customer" | "hotel_direct" | "other";
  total_orders: number;
  late_orders: number;
  late_rate: number;
  approved_exceptions: number;
  rejected_exceptions: number;
};

export type DashboardSourceMetrics = {
  date_from: string;
  date_to: string;
  zone_id: string | null;
  items: DashboardSourceMetricsItem[];
};

export type OrderOperationalState = "eligible" | "restricted";
export type OrderOperationalReason =
  | "CUSTOMER_DATE_BLOCKED"
  | "CUSTOMER_NOT_ACCEPTING_ORDERS"
  | "OUTSIDE_CUSTOMER_WINDOW"
  | "INSUFFICIENT_LEAD_TIME";
export type OrderOperationalSeverity = "low" | "medium" | "high" | "critical";
export type OrderOperationalTimezoneSource = "zone" | "tenant_default" | "utc_fallback";
export type OrderOperationalCatalogStatus = "active" | "inactive" | "missing" | "not_applicable";

export type OrderOperationalExplanation = {
  reason_code: OrderOperationalReason | string | null;
  reason_category: string | null;
  severity: OrderOperationalSeverity | null;
  timezone_used: string;
  timezone_source: OrderOperationalTimezoneSource | string;
  rule_version: string;
  catalog_status: OrderOperationalCatalogStatus | string;
};

export type Order = {
  id: string;
  customer_id: string;
  zone_id: string;
  external_ref: string;
  service_date: string;
  status: string;
  operational_state: OrderOperationalState | string;
  operational_reason: OrderOperationalReason | string | null;
  operational_explanation: OrderOperationalExplanation;
  is_late: boolean;
  effective_cutoff_at: string;
  intake_type: "new_order" | "same_customer_addon" | string;
  total_weight_kg: number | null;
};

export type PendingQueueReason =
  | "LATE_PENDING_EXCEPTION"
  | "LOCKED_PLAN_EXCEPTION_REQUIRED"
  | "EXCEPTION_REJECTED";
export type OperationalQueueReason = OrderOperationalReason;
export type OperationalResolutionQueueReason = OrderOperationalReason;
export type OperationalResolutionQueueSeverity = OrderOperationalSeverity;
export type CapacityAlertLevel = "OVER_CAPACITY" | "NEAR_CAPACITY";

export type PendingQueueItem = {
  order_id: string;
  external_ref: string;
  status: string;
  reason: PendingQueueReason;
  service_date: string;
  zone_id: string;
  created_at: string;
};

export type OperationalQueueItem = {
  order_id: string;
  external_ref: string;
  customer_id: string;
  zone_id: string;
  service_date: string;
  status: string;
  intake_type: "new_order" | "same_customer_addon" | string;
  reason: OperationalQueueReason | string;
  created_at: string;
};

export type OperationalResolutionQueueItem = {
  order_id: string;
  external_ref: string;
  customer_id: string;
  zone_id: string;
  service_date: string;
  status: string;
  intake_type: "new_order" | "same_customer_addon" | string;
  operational_reason: OperationalResolutionQueueReason | string;
  severity: OperationalResolutionQueueSeverity | string;
  created_at: string;
};

export type OrderOperationalSnapshotItem = {
  id: string;
  order_id: string;
  service_date: string;
  operational_state: "eligible" | "restricted" | string;
  operational_reason: OrderOperationalReason | string | null;
  evaluation_ts: string;
  timezone_used: string;
  rule_version: string;
  evidence_json: Record<string, unknown>;
};

export type OrderOperationalSnapshotsResponse = {
  order_id: string;
  service_date: string;
  items: OrderOperationalSnapshotItem[];
  total: number;
};

export type PlanOrder = {
  id: string;
  plan_id: string;
  order_id: string;
  inclusion_type: "normal" | "exception";
  added_at: string;
  added_by: string | null;
};

export type Plan = {
  id: string;
  service_date: string;
  zone_id: string;
  status: "open" | "locked" | "dispatched";
  version: number;
  vehicle_id: string | null;
  vehicle_code: string | null;
  vehicle_name: string | null;
  vehicle_capacity_kg: number | null;
  locked_at: string | null;
  locked_by: string | null;
  total_weight_kg: number;
  orders_total: number;
  orders_with_weight: number;
  orders_missing_weight: number;
  orders: PlanOrder[];
};

export type RoutingRouteStatus = "draft" | "planned" | "dispatched" | "in_progress" | "completed" | "cancelled";
export type RouteStopStatus = "pending" | "en_route" | "arrived" | "completed" | "failed" | "skipped";
export type RouteEventActorType = "dispatcher" | "driver" | "system";

export type ReadyToDispatchItem = {
  id: string;
  customer_id: string;
  service_date: string;
  status: "planned";
  total_weight_kg: number | null;
  zone_id: string;
};

export type AvailableVehicleDriver = {
  id: string;
  name: string;
  phone: string;
};

export type AvailableVehicleItem = {
  id: string;
  code: string;
  name: string;
  capacity_kg: number | null;
  active: boolean;
  driver: AvailableVehicleDriver | null;
};

export type RoutingRouteStop = {
  id: string;
  route_id: string;
  order_id: string;
  sequence_number: number;
  estimated_arrival_at: string | null;
  estimated_service_minutes: number;
  status: RouteStopStatus;
  arrived_at: string | null;
  completed_at: string | null;
  failed_at: string | null;
  failure_reason: string | null;
  customer_lat: number | null;
  customer_lng: number | null;
  created_at: string;
  updated_at: string;
};

export type RoutingRouteGeometry = {
  provider: string;
  encoding: "google_encoded_polyline";
  transition_polylines: string[];
};

export type RoutingRoute = {
  id: string;
  plan_id: string;
  vehicle_id: string;
  driver_id: string | null;
  service_date: string;
  status: RoutingRouteStatus;
  version: number;
  optimization_request_id: string | null;
  optimization_response_json: Record<string, unknown> | null;
  route_geometry?: RoutingRouteGeometry | null;
  created_at: string;
  updated_at: string;
  dispatched_at: string | null;
  completed_at: string | null;
  stops: RoutingRouteStop[];
};

export type PlanRouteInput = {
  vehicle_id: string;
  driver_id?: string | null;
  order_ids: string[];
};

export type PlanRoutesRequest = {
  plan_id: string;
  service_date: string;
  routes: PlanRouteInput[];
};

export type PlanRoutesCreatedItem = {
  id: string;
  vehicle_id: string;
  driver_id: string | null;
  status: string;
  version: number;
};

export type PlanRoutesResponse = {
  plan_id: string;
  service_date: string;
  routes_created: PlanRoutesCreatedItem[];
};

export type RouteMoveStopRequest = {
  stop_id: string;
  target_route_id: string;
};

export type RouteMoveStopResponse = {
  order_id: string;
  from_route_id: string;
  to_route_id: string;
  new_sequence_number: number;
};

export type RouteEventItem = {
  id: string;
  route_id: string;
  route_stop_id: string | null;
  event_type: string;
  actor_type: RouteEventActorType;
  actor_id: string | null;
  ts: string;
  metadata_json: Record<string, unknown>;
};

export type RouteNextStopResponse = {
  route_id: string;
  next_stop: RoutingRouteStop | null;
  remaining_stops: number;
};

// ── Driver stop actions ─────────────────────────────────────────────────────
export type RouteStopArriveRequest = { idempotency_key?: string | null };
export type RouteStopCompleteRequest = { idempotency_key?: string | null };
export type RouteStopFailRequest = { failure_reason: string; idempotency_key?: string | null };
export type RouteStopSkipRequest = { reason?: string | null; idempotency_key?: string | null };

// ── Incidents ───────────────────────────────────────────────────────────────
export type IncidentType =
  | "access_blocked"
  | "customer_absent"
  | "customer_rejected"
  | "vehicle_issue"
  | "wrong_address"
  | "damaged_goods"
  | "other";

export type IncidentSeverity = "low" | "medium" | "high" | "critical";
export type IncidentStatus = "open" | "reviewed" | "resolved";

export type IncidentCreateRequest = {
  route_id: string;
  route_stop_id?: string | null;
  type: IncidentType;
  severity: IncidentSeverity;
  description: string;
  idempotency_key?: string | null;
};

export type IncidentOut = {
  id: string;
  route_id: string;
  route_stop_id: string | null;
  driver_id: string;
  type: IncidentType;
  severity: IncidentSeverity;
  description: string;
  status: IncidentStatus;
  reported_at: string;
  reviewed_at: string | null;
  resolved_at: string | null;
  resolution_note: string | null;
  created_at: string;
  updated_at: string;
};

export type IncidentsListResponse = {
  items: IncidentOut[];
  total: number;
};

export type PlanCapacityAlert = {
  plan_id: string;
  service_date: string;
  zone_id: string;
  vehicle_id: string;
  vehicle_code: string | null;
  vehicle_name: string | null;
  total_weight_kg: number;
  vehicle_capacity_kg: number;
  usage_ratio: number;
  alert_level: CapacityAlertLevel;
};

export type PlanCapacityAlertsResponse = {
  service_date: string;
  zone_id: string | null;
  level: CapacityAlertLevel | null;
  near_threshold_ratio: number;
  items: PlanCapacityAlert[];
  total: number;
};

export type PlanCustomerConsolidationItem = {
  customer_id: string;
  customer_name: string;
  total_orders: number;
  order_refs: string[];
  total_weight_kg: number | null;
  orders_with_weight: number;
  orders_missing_weight: number;
};

export type PlanCustomerConsolidationResponse = {
  plan_id: string;
  service_date: string;
  zone_id: string;
  items: PlanCustomerConsolidationItem[];
  total_customers: number;
};

export type AutoLockRunResponse = {
  tenant_id: string;
  service_date: string;
  auto_lock_enabled: boolean;
  window_reached: boolean;
  considered_open_plans: number;
  locked_count: number;
  locked_plan_ids: string[];
};

export type ExceptionItem = {
  id: string;
  order_id: string;
  type: "late_order";
  status: "pending" | "approved" | "rejected";
  requested_by: string;
  resolved_by: string | null;
  resolved_at: string | null;
  note: string;
  created_at: string;
};

export type ListResponse<T> = {
  items: T[];
  total: number;
};

export type Zone = {
  id: string;
  name: string;
  default_cutoff_time: string;
  timezone: string;
  active: boolean;
  created_at: string;
};

export type ZoneCreateRequest = {
  name: string;
  default_cutoff_time: string;
  timezone: string;
};

export type ZoneUpdateRequest = Partial<ZoneCreateRequest>;

export type Customer = {
  id: string;
  zone_id: string;
  name: string;
  priority: number;
  cutoff_override_time: string | null;
  active: boolean;
  created_at: string;
};

export type CustomerCreateRequest = {
  zone_id: string;
  name: string;
  priority: number;
  cutoff_override_time: string | null;
};

export type CustomerUpdateRequest = Partial<CustomerCreateRequest>;

export type CustomerOperationalProfileWindowMode = "none" | "same_day" | "cross_midnight";

export type CustomerOperationalProfile = {
  customer_id: string;
  accept_orders: boolean;
  window_start: string | null;
  window_end: string | null;
  min_lead_hours: number;
  consolidate_by_default: boolean;
  ops_note: string | null;
  evaluation_timezone: string;
  window_mode: CustomerOperationalProfileWindowMode;
  is_customized: boolean;
};

export type CustomerOperationalProfilePutRequest = {
  accept_orders: boolean;
  window_start: string | null;
  window_end: string | null;
  min_lead_hours: number;
  consolidate_by_default: boolean;
  ops_note: string | null;
};

export type CustomerOperationalExceptionType = "blocked" | "restricted";

export type CustomerOperationalException = {
  id: string;
  customer_id: string;
  date: string;
  type: CustomerOperationalExceptionType;
  note: string;
  created_at: string;
};

export type CustomerOperationalExceptionCreateRequest = {
  date: string;
  type: CustomerOperationalExceptionType;
  note: string;
};

export type AdminUser = {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
};

export type AdminUserCreateRequest = {
  email: string;
  full_name: string;
  role: UserRole;
  password: string;
  is_active: boolean;
};

export type AdminUserUpdateRequest = Partial<AdminUserCreateRequest>;

export type Product = {
  id: string;
  sku: string;
  name: string;
  barcode: string | null;
  uom: string;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type ProductCreateRequest = {
  sku: string;
  name: string;
  barcode?: string | null;
  uom: string;
};

export type ProductUpdateRequest = Partial<ProductCreateRequest>;

export type TenantSettings = {
  id: string;
  name: string;
  slug: string;
  default_cutoff_time: string;
  default_timezone: string;
  auto_lock_enabled: boolean;
};

export type TenantSettingsUpdateRequest = Partial<{
  default_cutoff_time: string;
  default_timezone: string;
  auto_lock_enabled: boolean;
}>;

export async function login(payload: LoginRequest): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/login", {
    method: "POST",
    body: payload,
  });
}

export async function getDailySummary(token: string, serviceDate: string): Promise<DashboardSummary> {
  return request<DashboardSummary>(`/dashboard/daily-summary${buildQuery({ service_date: serviceDate })}`, { token });
}

export async function getSourceMetrics(
  token: string,
  params: { date_from: string; date_to: string; zone_id?: string },
): Promise<DashboardSourceMetrics> {
  return request<DashboardSourceMetrics>(`/dashboard/source-metrics${buildQuery(params)}`, { token });
}

export async function listOrders(token: string, serviceDate: string): Promise<ListResponse<Order>> {
  return request<ListResponse<Order>>(`/orders${buildQuery({ service_date: serviceDate })}`, { token });
}

export async function listPlans(token: string, serviceDate: string): Promise<ListResponse<Plan>> {
  return request<ListResponse<Plan>>(`/plans${buildQuery({ service_date: serviceDate })}`, { token });
}

export async function listReadyToDispatchOrders(
  token: string,
  params: { service_date?: string } = {},
): Promise<ListResponse<ReadyToDispatchItem>> {
  return request<ListResponse<ReadyToDispatchItem>>(`/planning/orders/ready-to-dispatch${buildQuery(params)}`, { token });
}

export async function listAvailableVehicles(
  token: string,
  params: { service_date?: string } = {},
): Promise<ListResponse<AvailableVehicleItem>> {
  return request<ListResponse<AvailableVehicleItem>>(`/vehicles/available${buildQuery(params)}`, { token });
}

export async function planRoutes(token: string, payload: PlanRoutesRequest): Promise<PlanRoutesResponse> {
  return request<PlanRoutesResponse>("/routes/plan", { token, method: "POST", body: payload });
}

export async function listRoutes(
  token: string,
  params: {
    plan_id?: string;
    vehicle_id?: string;
    driver_id?: string;
    service_date?: string;
    status?: RoutingRouteStatus;
  } = {},
): Promise<ListResponse<RoutingRoute>> {
  return request<ListResponse<RoutingRoute>>(`/routes${buildQuery(params)}`, { token });
}

export async function getRoute(token: string, routeId: string): Promise<RoutingRoute> {
  return request<RoutingRoute>(`/routes/${routeId}`, { token });
}

export async function listRouteEvents(token: string, routeId: string): Promise<ListResponse<RouteEventItem>> {
  return request<ListResponse<RouteEventItem>>(`/routes/${routeId}/events`, { token });
}

export async function getRouteNextStop(token: string, routeId: string): Promise<RouteNextStopResponse> {
  return request<RouteNextStopResponse>(`/routes/${routeId}/next-stop`, { token });
}

// ── Driver-scoped route listing ─────────────────────────────────────────────
export async function getDriverRoutes(
  token: string,
  params: { service_date?: string; status?: RoutingRouteStatus } = {},
): Promise<ListResponse<RoutingRoute>> {
  return request<ListResponse<RoutingRoute>>(`/driver/routes${buildQuery(params)}`, { token });
}

// ── Stop execution actions ──────────────────────────────────────────────────
export async function arriveStop(
  token: string,
  stopId: string,
  payload: RouteStopArriveRequest = {},
): Promise<RoutingRouteStop> {
  return request<RoutingRouteStop>(`/stops/${stopId}/arrive`, { token, method: "POST", body: payload });
}

export async function completeStop(
  token: string,
  stopId: string,
  payload: RouteStopCompleteRequest = {},
): Promise<RoutingRouteStop> {
  return request<RoutingRouteStop>(`/stops/${stopId}/complete`, { token, method: "POST", body: payload });
}

export async function failStop(
  token: string,
  stopId: string,
  payload: RouteStopFailRequest,
): Promise<RoutingRouteStop> {
  return request<RoutingRouteStop>(`/stops/${stopId}/fail`, { token, method: "POST", body: payload });
}

export async function skipStop(
  token: string,
  stopId: string,
  payload: RouteStopSkipRequest = {},
): Promise<RoutingRouteStop> {
  return request<RoutingRouteStop>(`/stops/${stopId}/skip`, { token, method: "POST", body: payload });
}

// ── Incidents ───────────────────────────────────────────────────────────────
export async function createIncident(token: string, payload: IncidentCreateRequest): Promise<IncidentOut> {
  return request<IncidentOut>("/incidents", { token, method: "POST", body: payload });
}

export async function optimizeRoute(token: string, routeId: string): Promise<RoutingRoute> {
  return request<RoutingRoute>(`/routes/${routeId}/optimize`, { token, method: "POST" });
}

export async function dispatchRoute(token: string, routeId: string): Promise<RoutingRoute> {
  return request<RoutingRoute>(`/routes/${routeId}/dispatch`, { token, method: "POST" });
}

export async function moveRouteStop(
  token: string,
  routeId: string,
  payload: RouteMoveStopRequest,
): Promise<RouteMoveStopResponse> {
  return request<RouteMoveStopResponse>(`/routes/${routeId}/move-stop`, {
    token,
    method: "POST",
    body: payload,
  });
}

export async function getPlanCapacityAlerts(
  token: string,
  params: { service_date: string; zone_id?: string; level?: CapacityAlertLevel },
): Promise<PlanCapacityAlertsResponse> {
  return request<PlanCapacityAlertsResponse>(`/plans/capacity-alerts${buildQuery(params)}`, { token });
}

export async function getPlanCustomerConsolidation(
  token: string,
  planId: string,
): Promise<PlanCustomerConsolidationResponse> {
  return request<PlanCustomerConsolidationResponse>(`/plans/${planId}/customer-consolidation`, { token });
}

export async function listExceptions(token: string): Promise<ListResponse<ExceptionItem>> {
  return request<ListResponse<ExceptionItem>>("/exceptions", { token });
}

export async function listPendingQueue(
  token: string,
  params: { service_date: string; zone_id?: string; reason?: PendingQueueReason },
): Promise<ListResponse<PendingQueueItem>> {
  return request<ListResponse<PendingQueueItem>>(`/orders/pending-queue${buildQuery(params)}`, { token });
}

export async function listOperationalQueue(
  token: string,
  params: { service_date: string; zone_id?: string; reason?: OperationalQueueReason | string },
): Promise<ListResponse<OperationalQueueItem>> {
  return request<ListResponse<OperationalQueueItem>>(`/orders/operational-queue${buildQuery(params)}`, { token });
}

export async function listOperationalResolutionQueue(
  token: string,
  params: {
    service_date: string;
    zone_id?: string;
    reason?: OperationalResolutionQueueReason | string;
    severity?: OperationalResolutionQueueSeverity | string;
  },
): Promise<ListResponse<OperationalResolutionQueueItem>> {
  return request<ListResponse<OperationalResolutionQueueItem>>(`/orders/operational-resolution-queue${buildQuery(params)}`, {
    token,
  });
}

export async function listOrderOperationalSnapshots(
  token: string,
  orderId: string,
  params: { limit?: number } = {},
): Promise<OrderOperationalSnapshotsResponse> {
  return request<OrderOperationalSnapshotsResponse>(
    `/orders/${orderId}/operational-snapshots${buildQuery(params)}`,
    { token },
  );
}

export async function createPlan(token: string, payload: { service_date: string; zone_id: string }): Promise<Plan> {
  return request<Plan>("/plans", { token, method: "POST", body: payload });
}

export async function lockPlan(token: string, planId: string): Promise<Plan> {
  return request<Plan>(`/plans/${planId}/lock`, { token, method: "POST" });
}

export async function runAutoLock(token: string): Promise<AutoLockRunResponse> {
  return request<AutoLockRunResponse>("/plans/auto-lock/run", { token, method: "POST" });
}

export async function updatePlanVehicle(
  token: string,
  planId: string,
  payload: { vehicle_id: string | null },
): Promise<Plan> {
  return request<Plan>(`/plans/${planId}/vehicle`, {
    token,
    method: "PATCH",
    body: payload,
  });
}

export async function includeOrderInPlan(token: string, planId: string, orderId: string): Promise<PlanOrder> {
  return request<PlanOrder>(`/plans/${planId}/orders`, {
    token,
    method: "POST",
    body: { order_id: orderId },
  });
}

export async function updateOrderWeight(
  token: string,
  orderId: string,
  payload: { total_weight_kg: number | null },
): Promise<Order> {
  return request<Order>(`/orders/${orderId}/weight`, {
    token,
    method: "PATCH",
    body: payload,
  });
}

export async function createException(
  token: string,
  payload: { order_id: string; type: "late_order"; note: string },
): Promise<ExceptionItem> {
  return request<ExceptionItem>("/exceptions", { token, method: "POST", body: payload });
}

export async function approveException(token: string, exceptionId: string): Promise<ExceptionItem> {
  return request<ExceptionItem>(`/exceptions/${exceptionId}/approve`, { token, method: "POST" });
}

export async function rejectException(token: string, exceptionId: string, note: string): Promise<ExceptionItem> {
  return request<ExceptionItem>(`/exceptions/${exceptionId}/reject`, {
    token,
    method: "POST",
    body: { note },
  });
}

export async function listAdminZones(
  token: string,
  params: { active?: boolean; zone_id?: string } = {},
): Promise<ListResponse<Zone>> {
  return request<ListResponse<Zone>>(`/admin/zones${buildQuery(params)}`, { token });
}

export async function createAdminZone(token: string, payload: ZoneCreateRequest): Promise<Zone> {
  return request<Zone>("/admin/zones", { token, method: "POST", body: payload });
}

export async function updateAdminZone(token: string, zoneId: string, payload: ZoneUpdateRequest): Promise<Zone> {
  return request<Zone>(`/admin/zones/${zoneId}`, { token, method: "PATCH", body: payload });
}

export async function deactivateAdminZone(token: string, zoneId: string): Promise<Zone> {
  return request<Zone>(`/admin/zones/${zoneId}/deactivate`, { token, method: "POST" });
}

export async function listAdminCustomers(
  token: string,
  params: { active?: boolean; zone_id?: string } = {},
): Promise<ListResponse<Customer>> {
  return request<ListResponse<Customer>>(`/admin/customers${buildQuery(params)}`, { token });
}

export async function createAdminCustomer(token: string, payload: CustomerCreateRequest): Promise<Customer> {
  return request<Customer>("/admin/customers", { token, method: "POST", body: payload });
}

export async function updateAdminCustomer(
  token: string,
  customerId: string,
  payload: CustomerUpdateRequest,
): Promise<Customer> {
  return request<Customer>(`/admin/customers/${customerId}`, { token, method: "PATCH", body: payload });
}

export async function deactivateAdminCustomer(token: string, customerId: string): Promise<Customer> {
  return request<Customer>(`/admin/customers/${customerId}/deactivate`, { token, method: "POST" });
}

export async function getAdminCustomerOperationalProfile(
  token: string,
  customerId: string,
): Promise<CustomerOperationalProfile> {
  return request<CustomerOperationalProfile>(`/admin/customers/${customerId}/operational-profile`, { token });
}

export async function putAdminCustomerOperationalProfile(
  token: string,
  customerId: string,
  payload: CustomerOperationalProfilePutRequest,
): Promise<CustomerOperationalProfile> {
  return request<CustomerOperationalProfile>(`/admin/customers/${customerId}/operational-profile`, {
    token,
    method: "PUT",
    body: payload,
  });
}

export async function listAdminCustomerOperationalExceptions(
  token: string,
  customerId: string,
): Promise<ListResponse<CustomerOperationalException>> {
  return request<ListResponse<CustomerOperationalException>>(
    `/admin/customers/${customerId}/operational-exceptions`,
    { token },
  );
}

export async function createAdminCustomerOperationalException(
  token: string,
  customerId: string,
  payload: CustomerOperationalExceptionCreateRequest,
): Promise<CustomerOperationalException> {
  return request<CustomerOperationalException>(
    `/admin/customers/${customerId}/operational-exceptions`,
    {
      token,
      method: "POST",
      body: payload,
    },
  );
}

export async function deleteAdminCustomerOperationalException(
  token: string,
  customerId: string,
  exceptionId: string,
): Promise<CustomerOperationalException> {
  return request<CustomerOperationalException>(
    `/admin/customers/${customerId}/operational-exceptions/${exceptionId}`,
    {
      token,
      method: "DELETE",
    },
  );
}

export async function listAdminUsers(
  token: string,
  params: { is_active?: boolean; role?: UserRole } = {},
): Promise<ListResponse<AdminUser>> {
  return request<ListResponse<AdminUser>>(`/admin/users${buildQuery(params)}`, { token });
}

export async function createAdminUser(token: string, payload: AdminUserCreateRequest): Promise<AdminUser> {
  return request<AdminUser>("/admin/users", { token, method: "POST", body: payload });
}

export async function updateAdminUser(
  token: string,
  userId: string,
  payload: AdminUserUpdateRequest,
): Promise<AdminUser> {
  return request<AdminUser>(`/admin/users/${userId}`, { token, method: "PATCH", body: payload });
}

export async function listAdminProducts(
  token: string,
  params: { active?: boolean } = {},
): Promise<ListResponse<Product>> {
  return request<ListResponse<Product>>(`/admin/products${buildQuery(params)}`, { token });
}

export async function createAdminProduct(token: string, payload: ProductCreateRequest): Promise<Product> {
  return request<Product>("/admin/products", { token, method: "POST", body: payload });
}

export async function updateAdminProduct(
  token: string,
  productId: string,
  payload: ProductUpdateRequest,
): Promise<Product> {
  return request<Product>(`/admin/products/${productId}`, { token, method: "PATCH", body: payload });
}

export async function deactivateAdminProduct(token: string, productId: string): Promise<Product> {
  return request<Product>(`/admin/products/${productId}/deactivate`, { token, method: "POST" });
}

export async function getAdminTenantSettings(token: string): Promise<TenantSettings> {
  return request<TenantSettings>("/admin/tenant-settings", { token });
}

export async function updateAdminTenantSettings(
  token: string,
  payload: TenantSettingsUpdateRequest,
): Promise<TenantSettings> {
  return request<TenantSettings>("/admin/tenant-settings", { token, method: "PATCH", body: payload });
}

// ── Stop Proof — A2 (POD-001) ────────────────────────────────────────────────

export type StopProofType = "signature" | "photo" | "both";

export type StopProofOut = {
  id: string;
  route_stop_id: string;
  route_id: string;
  proof_type: StopProofType;
  signature_data: string | null;
  photo_url: string | null;
  signed_by: string | null;
  captured_at: string;
  created_at: string;
};

export type StopProofCreateRequest = {
  proof_type: StopProofType;
  signature_data?: string | null;
  signed_by?: string | null;
  captured_at?: string | null;
};

export async function createStopProof(
  token: string,
  stopId: string,
  payload: StopProofCreateRequest,
): Promise<StopProofOut> {
  return request<StopProofOut>(`/stops/${stopId}/proof`, { token, method: "POST", body: payload });
}

export async function getStopProof(token: string, stopId: string): Promise<StopProofOut> {
  return request<StopProofOut>(`/stops/${stopId}/proof`, { token });
}

// ── Stop Proof Photo — R8-POD-FOTO ────────────────────────────────────────────

export type ProofUploadUrlOut = {
  upload_url: string;
  object_key: string;
  expires_in: number;
};

export async function getProofUploadUrl(
  token: string,
  stopId: string,
): Promise<ProofUploadUrlOut> {
  return request<ProofUploadUrlOut>(`/stops/${stopId}/proof-upload-url`, { token, method: "POST" });
}

export async function confirmProofPhoto(
  token: string,
  stopId: string,
  objectKey: string,
): Promise<StopProofOut> {
  return request<StopProofOut>(`/stops/${stopId}/proof/photo`, {
    token,
    method: "PATCH",
    body: { object_key: objectKey },
  });
}

// ── Driver Position — A3 (GPS-001) ───────────────────────────────────────────

export type DriverPositionOut = {
  driver_id: string;
  route_id: string;
  lat: number;
  lng: number;
  accuracy_m: number | null;
  speed_kmh: number | null;
  heading: number | null;
  recorded_at: string;
};

export type DriverLocationUpdateRequest = {
  route_id: string;
  lat: number;
  lng: number;
  accuracy_m?: number | null;
  speed_kmh?: number | null;
  heading?: number | null;
  recorded_at?: string | null;
};

export async function updateDriverLocation(
  token: string,
  payload: DriverLocationUpdateRequest,
): Promise<void> {
  await request<void>("/driver/location", { token, method: "POST", body: payload });
}

export async function getDriverPosition(
  token: string,
  routeId: string,
): Promise<DriverPositionOut> {
  return request<DriverPositionOut>(`/routes/${routeId}/driver-position`, { token });
}

export async function getActivePositions(token: string): Promise<DriverPositionOut[]> {
  return request<DriverPositionOut[]>("/driver/active-positions", { token });
}
