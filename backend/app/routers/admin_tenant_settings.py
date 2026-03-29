from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.audit import write_audit
from app.db import get_db
from app.deps import CurrentUser, require_roles
from app.errors import not_found, unprocessable
from app.models import EntityType, Tenant, UserRole
from app.schemas import TenantSettingsOut, TenantSettingsUpdateRequest


router = APIRouter(prefix="/admin/tenant-settings", tags=["Admin Tenant Settings"])


@router.get("", response_model=TenantSettingsOut)
def get_tenant_settings(
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.admin)),
) -> TenantSettingsOut:
    tenant = db.get(Tenant, current.tenant_id)
    if not tenant:
        raise not_found("ENTITY_NOT_FOUND", "Tenant no encontrado")
    return TenantSettingsOut.model_validate(tenant)


@router.patch("", response_model=TenantSettingsOut)
def update_tenant_settings(
    payload: TenantSettingsUpdateRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.admin)),
) -> TenantSettingsOut:
    tenant = db.get(Tenant, current.tenant_id)
    if not tenant:
        raise not_found("ENTITY_NOT_FOUND", "Tenant no encontrado")
    if not payload.model_fields_set:
        raise unprocessable("INVALID_STATE_TRANSITION", "No hay cambios para aplicar")

    before = {
        "default_cutoff_time": tenant.default_cutoff_time.isoformat(),
        "default_timezone": tenant.default_timezone,
        "auto_lock_enabled": tenant.auto_lock_enabled,
    }
    changed_fields: list[str] = []

    if "default_cutoff_time" in payload.model_fields_set:
        if payload.default_cutoff_time is None:
            raise unprocessable("INVALID_STATE_TRANSITION", "default_cutoff_time no puede ser null")
        tenant.default_cutoff_time = payload.default_cutoff_time
        changed_fields.append("default_cutoff_time")

    if "default_timezone" in payload.model_fields_set:
        if payload.default_timezone is None:
            raise unprocessable("INVALID_STATE_TRANSITION", "default_timezone no puede ser null")
        tenant.default_timezone = payload.default_timezone
        changed_fields.append("default_timezone")

    if "auto_lock_enabled" in payload.model_fields_set:
        if payload.auto_lock_enabled is None:
            raise unprocessable("INVALID_STATE_TRANSITION", "auto_lock_enabled no puede ser null")
        tenant.auto_lock_enabled = payload.auto_lock_enabled
        changed_fields.append("auto_lock_enabled")

    if not changed_fields:
        raise unprocessable("INVALID_STATE_TRANSITION", "No hay cambios para aplicar")

    after = {
        "default_cutoff_time": tenant.default_cutoff_time.isoformat(),
        "default_timezone": tenant.default_timezone,
        "auto_lock_enabled": tenant.auto_lock_enabled,
    }

    write_audit(
        db,
        tenant_id=current.tenant_id,
        entity_type=EntityType.tenant,
        entity_id=tenant.id,
        action="tenant_settings.updated",
        actor_id=current.id,
        metadata={
            "changed_fields": changed_fields,
            "before": before,
            "after": after,
        },
    )

    db.commit()
    db.refresh(tenant)
    return TenantSettingsOut.model_validate(tenant)
