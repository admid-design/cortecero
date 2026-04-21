import enum
import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UserRole(str, enum.Enum):
    office = "office"
    logistics = "logistics"
    admin = "admin"
    driver = "driver"


class PlanStatus(str, enum.Enum):
    open = "open"
    locked = "locked"
    dispatched = "dispatched"


class OrderStatus(str, enum.Enum):
    ingested = "ingested"
    late_pending_exception = "late_pending_exception"
    ready_for_planning = "ready_for_planning"
    planned = "planned"
    exception_rejected = "exception_rejected"
    assigned = "assigned"
    dispatched = "dispatched"
    delivered = "delivered"
    failed_delivery = "failed_delivery"


class OrderIntakeType(str, enum.Enum):
    new_order = "new_order"
    same_customer_addon = "same_customer_addon"


class ExceptionType(str, enum.Enum):
    late_order = "late_order"


class ExceptionStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class InclusionType(str, enum.Enum):
    normal = "normal"
    exception = "exception"


class EntityType(str, enum.Enum):
    order = "order"
    exception = "exception"
    plan = "plan"
    plan_order = "plan_order"
    tenant = "tenant"


class SourceChannel(str, enum.Enum):
    sales = "sales"
    office = "office"
    direct_customer = "direct_customer"
    hotel_direct = "hotel_direct"
    other = "other"


class CustomerOperationalExceptionType(str, enum.Enum):
    blocked = "blocked"
    restricted = "restricted"


class OperationalReasonCatalog(Base):
    __tablename__ = "operational_reason_catalog"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    default_cutoff_time: Mapped[time] = mapped_column(Time, nullable=False)
    default_timezone: Mapped[str] = mapped_column(Text, nullable=False)
    auto_lock_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    default_cutoff_time: Mapped[time] = mapped_column(Time, nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    zone_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cutoff_override_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    lat: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    lng: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    # F6 — ZBE-001: el cliente está en zona de bajas emisiones (requiere vehículo autorizado ZBE)
    in_zbe_zone: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["zone_id", "tenant_id"], ["zones.id", "zones.tenant_id"], ondelete="RESTRICT"),
    )


class CustomerOperationalProfile(Base):
    __tablename__ = "customer_operational_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    accept_orders: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    window_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    window_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    min_lead_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consolidate_by_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ops_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "customer_id", name="uq_customer_operational_profile"),
        ForeignKeyConstraint(
            ["customer_id", "tenant_id"],
            ["customers.id", "customers.tenant_id"],
            ondelete="CASCADE",
        ),
    )


class CustomerOperationalException(Base):
    __tablename__ = "customer_operational_exceptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    type: Mapped[CustomerOperationalExceptionType] = mapped_column(
        Enum(CustomerOperationalExceptionType, name="customer_operational_exception_type"),
        nullable=False,
    )
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "customer_id",
            "date",
            "type",
            name="uq_customer_operational_exception_per_day_type",
        ),
        ForeignKeyConstraint(
            ["customer_id", "tenant_id"],
            ["customers.id", "customers.tenant_id"],
            ondelete="CASCADE",
        ),
    )


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    zone_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    external_ref: Mapped[str] = mapped_column(Text, nullable=False)
    requested_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    service_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus, name="order_status"), nullable=False)
    is_late: Mapped[bool] = mapped_column(Boolean, nullable=False)
    lateness_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_channel: Mapped[SourceChannel] = mapped_column(Enum(SourceChannel, name="source_channel"), nullable=False)
    intake_type: Mapped[OrderIntakeType] = mapped_column(
        Enum(OrderIntakeType, name="order_intake_type"),
        nullable=False,
        default=OrderIntakeType.new_order,
    )
    total_weight_kg: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    # F5 — ADR-001: el pedido contiene mercancías peligrosas (requiere vehículo ADR certificado)
    requires_adr: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "external_ref", "service_date", name="uq_order_business_key"),
        ForeignKeyConstraint(["customer_id", "tenant_id"], ["customers.id", "customers.tenant_id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["zone_id", "tenant_id"], ["zones.id", "zones.tenant_id"], ondelete="RESTRICT"),
    )


class OrderLine(Base):
    __tablename__ = "order_lines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    sku: Mapped[str] = mapped_column(Text, nullable=False)
    qty: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    weight_kg: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    volume_m3: Mapped[float | None] = mapped_column(Numeric(14, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["order_id", "tenant_id"], ["orders.id", "orders.tenant_id"], ondelete="CASCADE"),
    )


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    service_date: Mapped[date] = mapped_column(Date, nullable=False)
    zone_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[PlanStatus] = mapped_column(Enum(PlanStatus, name="plan_status"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "service_date", "zone_id", name="uq_plan_key"),
        ForeignKeyConstraint(["zone_id", "tenant_id"], ["zones.id", "zones.tenant_id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["locked_by", "tenant_id"], ["users.id", "users.tenant_id"], ondelete="SET NULL"),
        ForeignKeyConstraint(["vehicle_id", "tenant_id"], ["vehicles.id", "vehicles.tenant_id"], ondelete="SET NULL"),
    )


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    capacity_kg: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    # F5 — ADR-001: el vehículo está habilitado para transportar mercancías peligrosas
    is_adr_certified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # F6 — ZBE-001: el vehículo puede circular por zona de bajas emisiones
    is_zbe_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_vehicle_code"),
        UniqueConstraint("id", "tenant_id", name="uq_vehicle_tenant_scope"),
    )


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    sku: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    barcode: Mapped[str | None] = mapped_column(Text, nullable=True)
    uom: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "sku", name="uq_products_tenant_sku"),
    )


class PlanOrder(Base):
    __tablename__ = "plan_orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    inclusion_type: Mapped[InclusionType] = mapped_column(Enum(InclusionType, name="inclusion_type"), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    added_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("plan_id", "order_id", name="uq_plan_order"),
        UniqueConstraint("order_id", name="uq_order_only_once"),
        ForeignKeyConstraint(["plan_id", "tenant_id"], ["plans.id", "plans.tenant_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["order_id", "tenant_id"], ["orders.id", "orders.tenant_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["added_by", "tenant_id"], ["users.id", "users.tenant_id"], ondelete="SET NULL"),
    )


class ExceptionItem(Base):
    __tablename__ = "exceptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    type: Mapped[ExceptionType] = mapped_column(Enum(ExceptionType, name="exception_type"), nullable=False)
    status: Mapped[ExceptionStatus] = mapped_column(Enum(ExceptionStatus, name="exception_status"), nullable=False)
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["order_id", "tenant_id"], ["orders.id", "orders.tenant_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["requested_by", "tenant_id"], ["users.id", "users.tenant_id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["resolved_by", "tenant_id"], ["users.id", "users.tenant_id"], ondelete="SET NULL"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    entity_type: Mapped[EntityType] = mapped_column(Enum(EntityType, name="entity_type"), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["actor_id", "tenant_id"], ["users.id", "users.tenant_id"], ondelete="SET NULL"),
    )


class OrderOperationalSnapshot(Base):
    __tablename__ = "order_operational_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    service_date: Mapped[date] = mapped_column(Date, nullable=False)
    operational_state: Mapped[str] = mapped_column(Text, nullable=False)
    operational_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluation_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone_used: Mapped[str] = mapped_column(Text, nullable=False)
    rule_version: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["order_id", "tenant_id"], ["orders.id", "orders.tenant_id"], ondelete="CASCADE"),
    )


# ============================================================================
# ROUTING POC ENTITIES: Driver, Route, RouteStop, Incident, RouteEvent
# ============================================================================


class RouteStatus(str, enum.Enum):
    draft = "draft"
    planned = "planned"
    dispatched = "dispatched"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class RouteStopStatus(str, enum.Enum):
    pending = "pending"
    en_route = "en_route"
    arrived = "arrived"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class IncidentType(str, enum.Enum):
    access_blocked = "access_blocked"
    customer_absent = "customer_absent"
    customer_rejected = "customer_rejected"
    vehicle_issue = "vehicle_issue"
    wrong_address = "wrong_address"
    damaged_goods = "damaged_goods"
    other = "other"


class IncidentSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class IncidentStatus(str, enum.Enum):
    open = "open"
    reviewed = "reviewed"
    resolved = "resolved"


class RouteEventType(str, enum.Enum):
    route_created = "route.created"
    route_planned = "route.planned"
    route_dispatched = "route.dispatched"
    route_started = "route.started"
    route_completed = "route.completed"
    route_cancelled = "route.cancelled"
    stop_en_route = "stop.en_route"
    stop_arrived = "stop.arrived"
    stop_completed = "stop.completed"
    stop_failed = "stop.failed"
    stop_skipped = "stop.skipped"
    incident_reported = "incident.reported"
    incident_reviewed = "incident.reviewed"
    incident_resolved = "incident.resolved"
    order_returned_to_planning = "order.returned_to_planning"
    delay_alert = "delay_alert"


class RouteEventActorType(str, enum.Enum):
    dispatcher = "dispatcher"
    driver = "driver"
    system = "system"


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    # user_id: vínculo explícito hacia la cuenta de acceso del conductor.
    # Nullable: conductores demo/seed no tienen cuenta PWA.
    # DEFERRABLE INITIALLY DEFERRED: User y Driver pueden crearse en la misma tx.
    # ON DELETE SET NULL: borrar el User no borra el historial operativo del Driver.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL", deferrable=True, initially="DEFERRED"),
        nullable=True,
        unique=True,
    )
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "phone", name="uq_drivers_tenant_phone"),
        ForeignKeyConstraint(["vehicle_id", "tenant_id"], ["vehicles.id", "vehicles.tenant_id"], ondelete="SET NULL"),
    )


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    driver_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    service_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[RouteStatus] = mapped_column(Enum(RouteStatus, name="route_status"), nullable=False, default=RouteStatus.draft)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    optimization_request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    optimization_response_json: Mapped[dict | None] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)
    # F4 — DOUBLE-TRIP-001: número de viaje del vehículo en el día (1 = primero, 2 = segundo).
    trip_number: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(["plan_id", "tenant_id"], ["plans.id", "plans.tenant_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["vehicle_id", "tenant_id"], ["vehicles.id", "vehicles.tenant_id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["driver_id", "tenant_id"], ["drivers.id", "drivers.tenant_id"], ondelete="SET NULL"),
    )


class RouteStop(Base):
    __tablename__ = "route_stops"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    route_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_arrival_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recalculated_eta_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    estimated_service_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    status: Mapped[RouteStopStatus] = mapped_column(Enum(RouteStopStatus, name="route_stop_status"), nullable=False, default=RouteStopStatus.pending)
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        # Unicidad solo cuando order_id IS NOT NULL (índice parcial — ver migration 029)
        Index(
            "uq_route_stops_route_order_nonnull",
            "route_id", "order_id",
            unique=True,
            postgresql_where=text("order_id IS NOT NULL"),
        ),
        UniqueConstraint("route_id", "sequence_number", name="uq_route_stops_route_sequence"),
        ForeignKeyConstraint(["route_id", "tenant_id"], ["routes.id", "routes.tenant_id"], ondelete="CASCADE"),
        # FK nullable: PostgreSQL no comprueba la FK cuando order_id IS NULL
        ForeignKeyConstraint(["order_id", "tenant_id"], ["orders.id", "orders.tenant_id"], ondelete="RESTRICT"),
    )


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    route_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    route_stop_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    driver_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    type: Mapped[IncidentType] = mapped_column(Enum(IncidentType, name="incident_type"), nullable=False)
    severity: Mapped[IncidentSeverity] = mapped_column(Enum(IncidentSeverity, name="incident_severity"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[IncidentStatus] = mapped_column(Enum(IncidentStatus, name="incident_status"), nullable=False, default=IncidentStatus.open)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["route_id", "tenant_id"], ["routes.id", "routes.tenant_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["route_stop_id", "tenant_id"], ["route_stops.id", "route_stops.tenant_id"], ondelete="SET NULL"),
        ForeignKeyConstraint(["driver_id", "tenant_id"], ["drivers.id", "drivers.tenant_id"], ondelete="RESTRICT"),
    )


class RouteEvent(Base):
    __tablename__ = "route_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    route_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    route_stop_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    event_type: Mapped[RouteEventType] = mapped_column(Enum(RouteEventType, name="route_event_type"), nullable=False)
    actor_type: Mapped[RouteEventActorType] = mapped_column(Enum(RouteEventActorType, name="route_event_actor_type"), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=False, default={})

    __table_args__ = (
        ForeignKeyConstraint(["route_id", "tenant_id"], ["routes.id", "routes.tenant_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["route_stop_id", "tenant_id"], ["route_stops.id", "route_stops.tenant_id"], ondelete="CASCADE"),
    )


class StopProof(Base):
    """Prueba de entrega: firma digital del receptor.  Bloque A2 (POD-001)."""

    __tablename__ = "stop_proofs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    route_stop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    route_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    proof_type: Mapped[str] = mapped_column(Text, nullable=False)
    signature_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    signed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        # FK + CASCADE declarados en migration 027 — aquí para consistencia con RouteMessage/RouteEvent.
        ForeignKeyConstraint(["route_stop_id", "tenant_id"], ["route_stops.id", "route_stops.tenant_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["route_id", "tenant_id"], ["routes.id", "routes.tenant_id"], ondelete="CASCADE"),
    )


class DriverPosition(Base):
    """Posición GPS del conductor enviada periódicamente.  Bloque A3 (GPS-001)."""

    __tablename__ = "driver_positions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    driver_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    route_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    lat: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    lng: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    accuracy_m: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    speed_kmh: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    heading: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RouteMessage(Base):
    """Mensaje de chat interno en una ruta.  Bloque B3 (CHAT-001).

    Tabla append-only: dispatcher ↔ conductor.
    author_role: 'dispatcher' | 'driver'  (denormalizado para lectura eficiente)
    """

    __tablename__ = "route_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    route_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    author_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    author_role: Mapped[str] = mapped_column(Text, nullable=False)  # 'dispatcher' | 'driver'
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["route_id", "tenant_id"], ["routes.id", "routes.tenant_id"], ondelete="CASCADE"),
    )


# ============================================================================
# XLSX IMPORT ENTITIES: RouteTemplate, RouteTemplateStop
# ROUTE-TEMPLATE-MODEL-001
# ============================================================================


class RouteTemplate(Base):
    """Plantilla de ruta estacional importada desde XLSX.

    Una plantilla representa la ruta fija de un vehículo en un día de la semana
    para una temporada dada (verano/invierno).  Puede generarse una ruta operativa
    real (Route + RouteStops) mediante POST /routes/from-template.
    """

    __tablename__ = "route_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # Temporada libre: 'verano' | 'invierno' | cualquier etiqueta definida por el usuario
    season: Mapped[str | None] = mapped_column(Text, nullable=True)
    # vehicle_id: nullable — puede quedar sin vincular si la matrícula no se resuelve en la importación
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True)
    # day_of_week: 1=Lunes … 7=Domingo (ISO 8601); nullable = plantilla sin día fijo
    day_of_week: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    shift_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    shift_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RouteTemplateStop(Base):
    """Parada dentro de una plantilla de ruta estacional.

    sequence_number determina el orden de visita.  customer_id es nullable
    para permitir paradas cuyo cliente no existe aún en la DB al importar.
    """

    __tablename__ = "route_template_stops"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("route_templates.id", ondelete="CASCADE"), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # customer_id: nullable — puede quedar sin vincular si el nombre no se resuelve al importar
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    lat: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    lng: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("template_id", "sequence_number", name="uq_route_template_stops_seq"),
    )
