from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import is_superadmin, require_permission
from app.db.session import get_db
from app.models.access import User
from app.models.audit import AuditLog

router = APIRouter(tags=["Auditoría"])

@router.get("/audit")
def list_audit(limit: int = 100, user: User = Depends(require_permission("audit.read")), db: Session = Depends(get_db)):
    limit = max(1, min(limit, 500))
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if not is_superadmin(user): stmt = stmt.where(AuditLog.organization_id == user.organization_id)
    return [{"id": str(x.id), "organization_id": str(x.organization_id) if x.organization_id else None, "user_id": str(x.user_id) if x.user_id else None, "action": x.action, "entity_type": x.entity_type, "entity_id": x.entity_id, "created_at": x.created_at, "ip_address": x.ip_address} for x in db.scalars(stmt)]
