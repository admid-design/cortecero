import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import AuditLog, EntityType


def write_audit(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    entity_type: EntityType,
    entity_id: uuid.UUID,
    action: str,
    actor_id: uuid.UUID | None,
    metadata: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_id=actor_id,
            ts=datetime.now(UTC),
            request_id=None,
            metadata_json=metadata or {},
        )
    )
