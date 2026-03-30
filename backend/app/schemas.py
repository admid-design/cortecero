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
    lines: list[OrderLineOut]


class OrdersListResponse(BaseModel):
    items: list[OrderOut]
    total: int


PendingQueueReason = Literal["LATE_PENDING_EXCEPTION", "LOCKED_PLAN_EXCEPTION_REQUIRED", "EXCEPTION_REJECTED"]


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


class PlanCreateRequest(BaseModel):
    service_date: date
    zone_id: uuid.UUID


class PlanOrderCreateRequest(BaseModel):
    order_id: uuid.UUID


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
    locked_at: datetime | None
    locked_by: uuid.UUID | None
    orders: list[PlanOrderOut] = Field(default_factory=list)


class PlansListResponse(BaseModel):
    items: list[PlanOut]
    total: int


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
