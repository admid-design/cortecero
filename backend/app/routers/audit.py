import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentUser, require_roles
from app.models import AuditLog, EntityType, UserRole
from app.schemas import AuditListResponse, AuditLogOut


router = APIRouter(tags=["Audit"])


@router.get("/audit", response_model=AuditListResponse)
def get_audit(
    entity_type: str,
    entity_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_roles(UserRole.logistics, UserRole.admin)),
) -> AuditListResponse:
    rows = list(
        db.scalars(
            select(AuditLog)
            .where(
                AuditLog.tenant_id == current.tenant_id,
                AuditLog.entity_type == EntityType(entity_type),
                AuditLog.entity_id == entity_id,
            )
            .order_by(AuditLog.ts.desc())
        )
    )
    return AuditListResponse(items=[AuditLogOut.model_validate(row) for row in rows], total=len(rows))
