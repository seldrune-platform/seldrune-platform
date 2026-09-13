from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.models.audit import AuditLog


def record_audit(
    session: Session,
    *,
    action: str,
    resource_type: str,
    organization_id: UUID | None = None,
    actor_user_id: UUID | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    event = AuditLog(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
    )
    session.add(event)
    return event
