from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.models import OrderStatus, Tenant, Zone, Customer


def ensure_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def resolve_cutoff(customer: Customer, zone: Zone, tenant: Tenant) -> tuple[time, str]:
    cutoff_time = customer.cutoff_override_time or zone.default_cutoff_time or tenant.default_cutoff_time
    timezone = zone.timezone or tenant.default_timezone
    return cutoff_time, timezone


def build_effective_cutoff_at(service_date: date, cutoff_time: time, timezone: str) -> datetime:
    tz = ZoneInfo(timezone)
    cutoff_date = service_date - timedelta(days=1)
    local_dt = datetime.combine(cutoff_date, cutoff_time, tzinfo=tz)
    return local_dt.astimezone(UTC)


def compute_lateness(created_at: datetime, effective_cutoff_at: datetime) -> tuple[bool, str | None]:
    created = ensure_aware_utc(created_at)
    is_late = created > effective_cutoff_at
    if not is_late:
        return False, None
    return True, "created_after_cutoff"


def initial_order_status(is_late: bool) -> OrderStatus:
    return OrderStatus.late_pending_exception if is_late else OrderStatus.ready_for_planning
