from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.deps import is_superadmin, require_permission
from app.core.config import settings
from app.db.session import get_db
from app.models.access import User
from app.models.organization import Organization, Site, Plant, Sector

router = APIRouter(tags=["Sistema"])

@router.get("/system/info")
def system_info(user: User = Depends(require_permission("system.read"))):
    return {"name": settings.app_name, "version": settings.app_version, "environment": settings.app_env, "block": 1}

@router.get("/dashboard/foundation-summary")
def foundation_summary(user: User = Depends(require_permission("structure.read")), db: Session = Depends(get_db)):
    def count(model):
        stmt = select(func.count()).select_from(model)
        if hasattr(model, "organization_id") and not is_superadmin(user): stmt = stmt.where(model.organization_id == user.organization_id)
        if model is Organization and not is_superadmin(user): stmt = stmt.where(Organization.id == user.organization_id)
        return db.scalar(stmt) or 0
    return {"organizations": count(Organization), "sites": count(Site), "plants": count(Plant), "sectors": count(Sector), "foundation_status": "OPERATIVO"}
