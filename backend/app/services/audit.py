from fastapi import Request
from sqlalchemy.orm import Session
from app.models.access import User
from app.models.audit import AuditLog

def add_audit(db: Session, user: User | None, action: str, entity_type: str, entity_id: str | None, after: dict | None = None, before: dict | None = None, request: Request | None = None, organization_id=None):
    ip = request.client.host if request and request.client else None
    log = AuditLog(
        organization_id=organization_id if organization_id is not None else (user.organization_id if user else None),
        user_id=user.id if user else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_value=before,
        after_value=after,
        ip_address=ip,
    )
    db.add(log)
