export type UserRole = "office" | "logistics" | "admin";

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

export type Order = {
  id: string;
  customer_id: string;
  zone_id: string;
  external_ref: string;
  service_date: string;
  status: string;
  operational_state: OrderOperationalState | string;
  operational_reason: OrderOperationalReason | string | null;
  is_late: boolean;
  effective_cutoff_at: string;
  intake_type: "new_order" | "same_customer_addon" | string;
  total_weight_kg: number | null;
};

export type PendingQueueReason =
  | "LATE_PENDING_EXCEPTION"
  | "LOCKED_PLAN_EXCEPTION_REQUIRED"
  | "EXCEPTION_REJECTED";
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

export async function getPlanCapacityAlerts(
  token: string,
  params: { service_date: string; zone_id?: string; level?: CapacityAlertLevel },
): Promise<PlanCapacityAlertsResponse> {
  return request<PlanCapacityAlertsResponse>(`/plans/capacity-alerts${buildQuery(params)}`, { token });
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

export async function getAdminTenantSettings(token: string): Promise<TenantSettings> {
  return request<TenantSettings>("/admin/tenant-settings", { token });
}

export async function updateAdminTenantSettings(
  token: string,
  payload: TenantSettingsUpdateRequest,
): Promise<TenantSettings> {
  return request<TenantSettings>("/admin/tenant-settings", { token, method: "PATCH", body: payload });
}
