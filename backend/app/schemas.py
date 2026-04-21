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
OperationalResolutionQueueReason = OperationalReasonCode
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


class OperationalResolutionQueueItemOut(APIModel):
    order_id: uuid.UUID
    external_ref: str
    customer_id: uuid.UUID
    zone_id: uuid.UUID
    service_date: date
    status: str
    intake_type: Literal["new_order", "same_customer_addon"]
    operational_reason: OperationalResolutionQueueReason
    severity: OperationalReasonSeverity
    created_at: datetime


class OperationalResolutionQueueListResponse(BaseModel):
    items: list[OperationalResolutionQueueItemOut]
    total: int


class OperationalDatasetItemOut(APIModel):
    order_id: uuid.UUID
    external_ref: str
    service_date: date
    created_at: datetime
    order_status: str
    source_channel: str
    intake_type: Literal["new_order", "same_customer_addon"]
    is_late: bool
    customer_id: uuid.UUID
    customer_name: str
    zone_id: uuid.UUID
    zone_name: str
    operational_state: Literal["eligible", "restricted"]
    operational_reason: OperationalReasonCode | None
    operational_reason_category: str | None
    operational_severity: OperationalReasonSeverity | None
    operational_catalog_status: OperationalReasonCatalogStatus
    rule_version: str
    timezone_used: str
    timezone_source: OperationalTimezoneSource
    planned: bool
    plan_id: uuid.UUID | None
    plan_status: str | None
    plan_inclusion_type: Literal["normal", "exception"] | None
    plan_locked_at: datetime | None
    plan_vehicle_id: uuid.UUID | None
    total_weight_kg: Decimal | None
    plan_total_weight_kg: Decimal | None
    plan_orders_total: int | None
    plan_orders_with_weight: int | None
    plan_orders_missing_weight: int | None


class OperationalDatasetExportResponse(BaseModel):
    date_from: date
    date_to: date
    zone_id: uuid.UUID | None
    page: int
    page_size: int
    total: int
    total_pages: int
    anonymized: bool
    items: list[OperationalDatasetItemOut]


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


class OperationalSnapshotRunResponse(BaseModel):
    tenant_id: uuid.UUID
    service_date: date
    rule_version: str
    evaluation_ts_bucket: datetime
    considered_orders: int
    generated_snapshots: int
    skipped_existing: int
    generated_snapshot_ids: list[uuid.UUID]


class OrderOperationalSnapshotOut(APIModel):
    id: uuid.UUID
    order_id: uuid.UUID
    service_date: date
    operational_state: Literal["eligible", "restricted"]
    operational_reason: OperationalReasonCode | None
    evaluation_ts: datetime
    timezone_used: str
    rule_version: str
    evidence_json: dict[str, Any]


class OrderOperationalSnapshotsResponse(BaseModel):
    order_id: uuid.UUID
    service_date: date
    items: list[OrderOperationalSnapshotOut]
    total: int


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


class ProductCreateRequest(BaseModel):
    sku: str
    name: str
    barcode: str | None = None
    uom: str


class ProductUpdateRequest(BaseModel):
    sku: str | None = None
    name: str | None = None
    barcode: str | None = None
    uom: str | None = None


class ProductOut(APIModel):
    id: uuid.UUID
    sku: str
    name: str
    barcode: str | None
    uom: str
    active: bool
    created_at: datetime
    updated_at: datetime


class ProductsListResponse(BaseModel):
    items: list[ProductOut]
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
    lat: Decimal | None = None
    lng: Decimal | None = None
    delivery_address: str | None = Field(default=None, max_length=500)


class CustomerOut(APIModel):
    id: uuid.UUID
    zone_id: uuid.UUID
    name: str
    priority: int
    cutoff_override_time: time | None
    lat: float | None
    lng: float | None
    delivery_address: str | None
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
    role: Literal["office", "logistics", "admin", "driver"]
    password: str = Field(min_length=8, max_length=128)
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=160)
    role: Literal["office", "logistics", "admin", "driver"] | None = None
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


# ============================================================================
# ROUTING POC SCHEMAS
# ============================================================================


class DriverCreateRequest(BaseModel):
    vehicle_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=160)
    phone: str = Field(min_length=1, max_length=20)


class DriverUpdateRequest(BaseModel):
    vehicle_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)
    phone: str | None = Field(default=None, min_length=1, max_length=20)
    is_active: bool | None = None


class DriverOut(APIModel):
    id: uuid.UUID
    vehicle_id: uuid.UUID | None
    name: str
    phone: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DriversListResponse(BaseModel):
    items: list[DriverOut]
    total: int


class RouteCreateRequest(BaseModel):
    plan_id: uuid.UUID
    vehicle_id: uuid.UUID
    service_date: date


class RouteStopOut(APIModel):
    id: uuid.UUID
    route_id: uuid.UUID
    order_id: uuid.UUID | None  # null para paradas creadas desde plantilla (sin pedido)
    sequence_number: int
    estimated_arrival_at: datetime | None
    recalculated_eta_at: datetime | None = None
    estimated_service_minutes: int
    status: Literal["pending", "en_route", "arrived", "completed", "failed", "skipped"]
    arrived_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    failure_reason: str | None
    customer_lat: float | None = None
    customer_lng: float | None = None
    customer_name: str | None = None
    created_at: datetime
    updated_at: datetime


class RouteGeometryOut(APIModel):
    provider: str
    encoding: Literal["google_encoded_polyline"]
    transition_polylines: list[str] = Field(default_factory=list)


class RouteTemplateListItem(APIModel):
    id: uuid.UUID
    name: str
    season: str | None
    vehicle_id: uuid.UUID | None
    has_vehicle: bool
    day_of_week: int | None
    stop_count: int
    created_at: datetime


class CreateRouteFromTemplateInput(APIModel):
    template_id: uuid.UUID
    service_date: date
    vehicle_id: uuid.UUID | None = None  # override de template.vehicle_id
    driver_id: uuid.UUID | None = None


class RouteOut(APIModel):
    id: uuid.UUID
    plan_id: uuid.UUID | None  # null para rutas creadas desde plantilla
    vehicle_id: uuid.UUID
    driver_id: uuid.UUID | None
    service_date: date
    status: Literal["draft", "planned", "dispatched", "in_progress", "completed", "cancelled"]
    version: int
    # F4 — DOUBLE-TRIP-001
    trip_number: int = 1
    optimization_request_id: str | None
    optimization_response_json: dict | None
    route_geometry: RouteGeometryOut | None = None
    created_at: datetime
    updated_at: datetime
    dispatched_at: datetime | None
    completed_at: datetime | None
    stops: list[RouteStopOut] = Field(default_factory=list)


class RoutesListResponse(BaseModel):
    items: list[RouteOut]
    total: int


class RouteStopArriveRequest(BaseModel):
    idempotency_key: str | None = None


class RouteStopCompleteRequest(BaseModel):
    idempotency_key: str | None = None


class RouteStopFailRequest(BaseModel):
    failure_reason: str = Field(min_length=1, max_length=500)
    idempotency_key: str | None = None


class RouteStopSkipRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
    idempotency_key: str | None = None


class RouteStopScheduledArrivalRequest(BaseModel):
    scheduled_arrival_at: datetime


class RouteNextStopResponse(BaseModel):
    route_id: uuid.UUID
    next_stop: RouteStopOut | None = None
    remaining_stops: int


class IncidentCreateRequest(BaseModel):
    route_id: uuid.UUID
    route_stop_id: uuid.UUID | None = None
    type: Literal["access_blocked", "customer_absent", "customer_rejected", "vehicle_issue", "wrong_address", "damaged_goods", "other"]
    severity: Literal["low", "medium", "high", "critical"]
    description: str = Field(min_length=1, max_length=500)
    idempotency_key: str | None = None


class IncidentResolveRequest(BaseModel):
    resolution_note: str = Field(min_length=1, max_length=1000)


class IncidentOut(APIModel):
    id: uuid.UUID
    route_id: uuid.UUID
    route_stop_id: uuid.UUID | None
    driver_id: uuid.UUID
    type: str
    severity: str
    description: str
    status: Literal["open", "reviewed", "resolved"]
    reported_at: datetime
    reviewed_at: datetime | None
    resolved_at: datetime | None
    resolution_note: str | None
    created_at: datetime
    updated_at: datetime


class IncidentsListResponse(BaseModel):
    items: list[IncidentOut]
    total: int


class RouteEventOut(APIModel):
    id: uuid.UUID
    route_id: uuid.UUID
    route_stop_id: uuid.UUID | None
    event_type: str
    actor_type: Literal["dispatcher", "driver", "system"]
    actor_id: uuid.UUID | None
    ts: datetime
    metadata_json: dict


class RouteEventsListResponse(BaseModel):
    items: list[RouteEventOut]
    total: int


# ── Stop Proof (A2 — POD-001) ─────────────────────────────────────────────────

class StopProofCreateRequest(BaseModel):
    proof_type: Literal["signature", "photo", "both"] = "signature"
    signature_data: str | None = None   # base64 PNG
    signed_by: str | None = None
    captured_at: datetime | None = None  # si None, se usa now() en backend


class StopProofOut(APIModel):
    id: uuid.UUID
    route_stop_id: uuid.UUID
    route_id: uuid.UUID
    proof_type: str
    signature_data: str | None
    photo_url: str | None
    signed_by: str | None
    captured_at: datetime
    created_at: datetime


# ── Stop Proof Photo (R8-POD-FOTO) ───────────────────────────────────────────

class ProofUploadUrlResponse(BaseModel):
    upload_url: str        # presigned PUT URL para subir directo a R2
    object_key: str        # key a usar en PATCH /proof/photo tras el upload
    expires_in: int        # segundos hasta que expira el presigned URL


class ProofPhotoConfirmRequest(BaseModel):
    object_key: str        # key devuelto por proof-upload-url


# ── Driver Position (A3 — GPS-001) ────────────────────────────────────────────

class DriverLocationUpdateRequest(BaseModel):
    route_id: uuid.UUID
    lat: float
    lng: float
    accuracy_m: float | None = None
    speed_kmh: float | None = None
    heading: float | None = None
    recorded_at: datetime | None = None  # si None, se usa now() en backend


class DriverPositionOut(BaseModel):
    driver_id: uuid.UUID
    route_id: uuid.UUID
    lat: float
    lng: float
    accuracy_m: float | None
    speed_kmh: float | None
    heading: float | None
    recorded_at: datetime


# ── ETA Recalculation (B2 — ETA-001) ─────────────────────────────────────────

class EtaStopResult(BaseModel):
    stop_id: uuid.UUID
    sequence_number: int
    original_eta: datetime | None
    recalculated_eta: datetime
    delay_minutes: float
    delay_alert: bool


class RecalculateEtaResponse(BaseModel):
    route_id: uuid.UUID
    stops_updated: int
    delay_alerts_created: int
    results: list[EtaStopResult]


class DelayAlertOut(BaseModel):
    event_id: uuid.UUID
    route_id: uuid.UUID
    stop_id: uuid.UUID | None
    original_eta: datetime | None
    recalculated_eta: datetime | None
    delay_minutes: float | None
    ts: datetime


# ── Chat interno (B3 — CHAT-001) ──────────────────────────────────────────────

class RouteMessageIn(BaseModel):
    body: str = Field(..., min_length=1, max_length=2000)


class RouteMessageOut(APIModel):
    id: uuid.UUID
    route_id: uuid.UUID
    author_user_id: uuid.UUID
    author_role: str
    body: str
    created_at: datetime


# ── Live-edit de ruta (B4 — LIVE-EDIT-001) ────────────────────────────────────

class AddStopRequest(BaseModel):
    order_id: uuid.UUID


class AddStopResponse(BaseModel):
    order_id: uuid.UUID
    route_id: uuid.UUID
    stop_id: uuid.UUID
    sequence_number: int


class RemoveStopResponse(BaseModel):
    order_id: uuid.UUID
    route_id: uuid.UUID
    removed_stop_id: uuid.UUID


class ReturnToPlanningResponse(BaseModel):
    order_id: uuid.UUID
    previous_status: str
    new_status: str
    returned_at: datetime


# ── Route Templates — XLSX import (ROUTE-TEMPLATE-MODEL-001) ─────────────────

class RouteTemplateStopOut(APIModel):
    id: uuid.UUID
    template_id: uuid.UUID
    sequence_number: int
    customer_id: uuid.UUID | None
    lat: float | None
    lng: float | None
    address: str | None
    duration_min: int
    notes: str | None
    created_at: datetime


class RouteTemplateOut(APIModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    season: str | None
    vehicle_id: uuid.UUID | None
    day_of_week: int | None
    shift_start: time | None
    shift_end: time | None
    created_at: datetime
    stops: list[RouteTemplateStopOut] = []


class RouteTemplateImportResult(BaseModel):
    templates_created: int
    stops_total: int
    errors: list[str] = []
    warnings: list[str] = []


class RouteFromTemplateRequest(BaseModel):
    template_id: uuid.UUID
    service_date: date
    plan_id: uuid.UUID


class RouteFromTemplateResponse(BaseModel):
    route_id: uuid.UUID
    template_id: uuid.UUID
    service_date: date
    stops_count: int


# ---------------------------------------------------------------------------
# XLSX-ORDERS-001 — Importación de pedidos desde XLSX/CSV
# ---------------------------------------------------------------------------

class OrderImportRowError(BaseModel):
    """Error o warning asociado a una fila concreta del archivo importado."""
    row: int
    reason: str


class OrderImportResult(BaseModel):
    """Resultado de POST /orders/import-xlsx."""
    imported: int
    skipped: int
    errors: list[OrderImportRowError]
    warnings: list[OrderImportRowError]
