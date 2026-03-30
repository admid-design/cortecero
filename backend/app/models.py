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
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UserRole(str, enum.Enum):
    office = "office"
    logistics = "logistics"
    admin = "admin"


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["zone_id", "tenant_id"], ["zones.id", "zones.tenant_id"], ondelete="RESTRICT"),
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
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "service_date", "zone_id", name="uq_plan_key"),
        ForeignKeyConstraint(["zone_id", "tenant_id"], ["zones.id", "zones.tenant_id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["locked_by", "tenant_id"], ["users.id", "users.tenant_id"], ondelete="SET NULL"),
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
