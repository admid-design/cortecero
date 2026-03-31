import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class LoginRequest(BaseModel):
    tenant_slug: str
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class OrderLineInput(BaseModel):
    sku: str
    qty: Decimal
    weight_kg: Decimal | None = None
    volume_m3: Decimal | None = None


class OrderIngestionInput(BaseModel):
    customer_id: uuid.UUID
    external_ref: str
    requested_date: date | None = None
    service_date: date
    created_at: datetime
    source_channel: Literal["sales", "office", "direct_customer", "hotel_direct", "other"] = "other"
    lines: list[OrderLineInput]


class OrderIngestionBatchInput(BaseModel):
    orders: list[OrderIngestionInput]


class OrderIngestionItemResult(BaseModel):
    external_ref: str
    service_date: date
    result: Literal["created", "updated", "rejected"]
    order_id: uuid.UUID | None = None
    reason: str | None = None


class OrderIngestionResult(BaseModel):
    created: int
    updated: int
    rejected: int
    items: list[OrderIngestionItemResult]


class OrderLineOut(APIModel):
    id: uuid.UUID
    sku: str
    qty: Decimal
    weight_kg: Decimal | None
    volume_m3: Decimal | None


OperationalReasonCode = Literal[
    "CUSTOMER_DATE_BLOCKED",
    "CUSTOMER_NOT_ACCEPTING_ORDERS",
    "OUTSIDE_CUSTOMER_WINDOW",
    "INSUFFICIENT_LEAD_TIME",
]

OperationalReasonSeverity = Literal["low", "medium", "high", "critical"]
OperationalReasonCatalogStatus = Literal["active", "inactive", "missing", "not_applicable"]
OperationalTimezoneSource = Literal["zone", "tenant_default", "utc_fallback"]


class OperationalExplanationOut(APIModel):
    reason_code: OperationalReasonCode | None
    reason_category: str | None
    severity: OperationalReasonSeverity | None
    timezone_used: str
    timezone_source: OperationalTimezoneSource
    rule_version: str
    catalog_status: OperationalReasonCatalogStatus


class OrderOut(APIModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    zone_id: uuid.UUID
    external_ref: str
    requested_date: date | None
    service_date: date
    created_at: datetime
    status: str
    is_late: bool
    lateness_reason: str | None
    effective_cutoff_at: datetime
    source_channel: str
    intake_type: Literal["new_order", "same_customer_addon"]
    operational_state: Literal["eligible", "restricted"]
    operational_reason: OperationalReasonCode | None
    operational_explanation: OperationalExplanationOut
    total_weight_kg: Decimal | None
    lines: list[OrderLineOut]


class OrdersListResponse(BaseModel):
    items: list[OrderOut]
    total: int


class OrderWeightUpdateRequest(BaseModel):
    total_weight_kg: Decimal | None


PendingQueueReason = Literal["LATE_PENDING_EXCEPTION", "LOCKED_PLAN_EXCEPTION_REQUIRED", "EXCEPTION_REJECTED"]
OperationalQueueReason = OperationalReasonCode
CapacityAlertLevel = Literal["OVER_CAPACITY", "NEAR_CAPACITY"]


class PendingQueueItemOut(APIModel):
    order_id: uuid.UUID
    external_ref: str
    status: str
    reason: PendingQueueReason
    service_date: date
    zone_id: uuid.UUID
    created_at: datetime


class PendingQueueListResponse(BaseModel):
    items: list[PendingQueueItemOut]
    total: int


class OperationalQueueItemOut(APIModel):
    order_id: uuid.UUID
    external_ref: str
    customer_id: uuid.UUID
    zone_id: uuid.UUID
    service_date: date
    status: str
    intake_type: Literal["new_order", "same_customer_addon"]
    reason: OperationalQueueReason
    created_at: datetime


class OperationalQueueListResponse(BaseModel):
    items: list[OperationalQueueItemOut]
    total: int


class PlanCreateRequest(BaseModel):
    service_date: date
    zone_id: uuid.UUID


class PlanOrderCreateRequest(BaseModel):
    order_id: uuid.UUID


class PlanVehicleUpdateRequest(BaseModel):
    vehicle_id: uuid.UUID | None


class AutoLockRunResponse(BaseModel):
    tenant_id: uuid.UUID
    service_date: date
    auto_lock_enabled: bool
    window_reached: bool
    considered_open_plans: int
    locked_count: int
    locked_plan_ids: list[uuid.UUID]


class PlanOrderOut(APIModel):
    id: uuid.UUID
    plan_id: uuid.UUID
    order_id: uuid.UUID
    inclusion_type: str
    added_at: datetime
    added_by: uuid.UUID | None


class PlanOut(APIModel):
    id: uuid.UUID
    service_date: date
    zone_id: uuid.UUID
    status: str
    version: int
    vehicle_id: uuid.UUID | None
    vehicle_code: str | None
    vehicle_name: str | None
    vehicle_capacity_kg: Decimal | None
    locked_at: datetime | None
    locked_by: uuid.UUID | None
    total_weight_kg: Decimal
    orders_total: int
    orders_with_weight: int
    orders_missing_weight: int
    orders: list[PlanOrderOut] = Field(default_factory=list)


class PlansListResponse(BaseModel):
    items: list[PlanOut]
    total: int


class PlanCapacityAlertOut(APIModel):
    plan_id: uuid.UUID
    service_date: date
    zone_id: uuid.UUID
    vehicle_id: uuid.UUID
    vehicle_code: str | None
    vehicle_name: str | None
    total_weight_kg: Decimal
    vehicle_capacity_kg: Decimal
    usage_ratio: float
    alert_level: CapacityAlertLevel


class PlanCapacityAlertsResponse(BaseModel):
    service_date: date
    zone_id: uuid.UUID | None
    level: CapacityAlertLevel | None
    near_threshold_ratio: float
    items: list[PlanCapacityAlertOut]
    total: int


class PlanCustomerConsolidationItemOut(APIModel):
    customer_id: uuid.UUID
    customer_name: str
    total_orders: int
    order_refs: list[str]
    total_weight_kg: Decimal | None
    orders_with_weight: int
    orders_missing_weight: int


class PlanCustomerConsolidationResponse(BaseModel):
    plan_id: uuid.UUID
    service_date: date
    zone_id: uuid.UUID
    items: list[PlanCustomerConsolidationItemOut]
    total_customers: int


class ExceptionCreateRequest(BaseModel):
    order_id: uuid.UUID
    type: Literal["late_order"]
    note: str


class ExceptionRejectRequest(BaseModel):
    note: str


class ExceptionOut(APIModel):
    id: uuid.UUID
    order_id: uuid.UUID
    type: str
    status: str
    requested_by: uuid.UUID
    resolved_by: uuid.UUID | None
    resolved_at: datetime | None
    note: str
    created_at: datetime


class ExceptionsListResponse(BaseModel):
    items: list[ExceptionOut]
    total: int


class DashboardSummaryResponse(BaseModel):
    service_date: date
    total_orders: int
    late_orders: int
    plans_open: int
    plans_locked: int
    pending_exceptions: int
    approved_exceptions: int
    rejected_exceptions: int


class DashboardSourceMetricsItem(BaseModel):
    source_channel: Literal["sales", "office", "direct_customer", "hotel_direct", "other"]
    total_orders: int
    late_orders: int
    late_rate: float
    approved_exceptions: int
    rejected_exceptions: int


class DashboardSourceMetricsResponse(BaseModel):
    date_from: date
    date_to: date
    zone_id: uuid.UUID | None
    items: list[DashboardSourceMetricsItem]


class AuditLogOut(APIModel):
    id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    action: str
    actor_id: uuid.UUID | None
    ts: datetime
    metadata_json: dict[str, Any]


class AuditListResponse(BaseModel):
    items: list[AuditLogOut]
    total: int


class ZoneCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    default_cutoff_time: time
    timezone: str = Field(min_length=1, max_length=120)


class ZoneUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    default_cutoff_time: time | None = None
    timezone: str | None = Field(default=None, min_length=1, max_length=120)


class ZoneOut(APIModel):
    id: uuid.UUID
    name: str
    default_cutoff_time: time
    timezone: str
    active: bool
    created_at: datetime


class ZonesListResponse(BaseModel):
    items: list[ZoneOut]
    total: int


class CustomerCreateRequest(BaseModel):
    zone_id: uuid.UUID
    name: str = Field(min_length=1, max_length=160)
    priority: int = 0
    cutoff_override_time: time | None = None


class CustomerUpdateRequest(BaseModel):
    zone_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)
    priority: int | None = None
    cutoff_override_time: time | None = None


class CustomerOut(APIModel):
    id: uuid.UUID
    zone_id: uuid.UUID
    name: str
    priority: int
    cutoff_override_time: time | None
    active: bool
    created_at: datetime


class CustomersListResponse(BaseModel):
    items: list[CustomerOut]
    total: int


CustomerOperationalWindowMode = Literal["none", "same_day", "cross_midnight"]
CustomerOperationalExceptionType = Literal["blocked", "restricted"]


class CustomerOperationalProfilePutRequest(BaseModel):
    accept_orders: bool
    window_start: time | None
    window_end: time | None
    min_lead_hours: int
    consolidate_by_default: bool
    ops_note: str | None = Field(max_length=2000)


class CustomerOperationalProfileOut(BaseModel):
    customer_id: uuid.UUID
    accept_orders: bool
    window_start: time | None
    window_end: time | None
    min_lead_hours: int
    consolidate_by_default: bool
    ops_note: str | None
    evaluation_timezone: str
    window_mode: CustomerOperationalWindowMode
    is_customized: bool


class CustomerOperationalExceptionCreateRequest(BaseModel):
    date: date
    type: CustomerOperationalExceptionType
    note: str = Field(min_length=1, max_length=2000)


class CustomerOperationalExceptionOut(APIModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    date: date
    type: CustomerOperationalExceptionType
    note: str
    created_at: datetime


class CustomerOperationalExceptionsListResponse(BaseModel):
    items: list[CustomerOperationalExceptionOut]
    total: int


class UserCreateRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=160)
    role: Literal["office", "logistics", "admin"]
    password: str = Field(min_length=8, max_length=128)
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=160)
    role: Literal["office", "logistics", "admin"] | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    is_active: bool | None = None


class UserOut(APIModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class UsersListResponse(BaseModel):
    items: list[UserOut]
    total: int


class TenantSettingsOut(APIModel):
    id: uuid.UUID
    name: str
    slug: str
    default_cutoff_time: time
    default_timezone: str
    auto_lock_enabled: bool


class TenantSettingsUpdateRequest(BaseModel):
    default_cutoff_time: time | None = None
    default_timezone: str | None = Field(default=None, min_length=1, max_length=120)
    auto_lock_enabled: bool | None = None
