import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.access import User
from app.models.safety import PPEType
from app.schemas.safety import PPETypeCreate, PPETypeOut, PPETypeUpdate
from app.services.audit import add_audit

router = APIRouter(prefix="/ppe", tags=["EPP"])


@router.get("", response_model=list[PPETypeOut])
def list_ppe(include_inactive: bool = False, user: User = Depends(require_permission("ppe.read")), db: Session = Depends(get_db)):
    stmt = select(PPEType).order_by(PPEType.name)
    if not include_inactive:
        stmt = stmt.where(PPEType.active.is_(True))
    return list(db.scalars(stmt))


@router.post("", response_model=PPETypeOut, status_code=status.HTTP_201_CREATED)
def create_ppe(payload: PPETypeCreate, request: Request, user: User = Depends(require_permission("ppe.manage")), db: Session = Depends(get_db)):
    item = PPEType(
        code=payload.code.strip().upper(), name=payload.name.strip(), description=payload.description,
        icon=payload.icon, active=payload.active, criticality=payload.criticality, color=payload.color.upper(),
        detector_class=payload.detector_class, min_confidence=payload.min_confidence, notes=payload.notes,
    )
    db.add(item)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Código EPP duplicado")
    add_audit(db, user, "CREATE", "ppe_type", str(item.id), after={"code":item.code,"name":item.name,"criticality":item.criticality}, request=request)
    db.commit(); db.refresh(item)
    return item


@router.patch("/{ppe_id}", response_model=PPETypeOut)
def update_ppe(ppe_id: uuid.UUID, payload: PPETypeUpdate, request: Request, user: User = Depends(require_permission("ppe.manage")), db: Session = Depends(get_db)):
    item = db.get(PPEType, ppe_id)
    if not item:
        raise HTTPException(404, "EPP inexistente")
    before = {"name":item.name,"active":item.active,"criticality":item.criticality,"min_confidence":item.min_confidence}
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        if field == "color" and value:
            value = value.upper()
        setattr(item, field, value)
    item.updated_at = datetime.now(timezone.utc)
    add_audit(db, user, "UPDATE", "ppe_type", str(item.id), before=before, after={"name":item.name,"active":item.active,"criticality":item.criticality,"min_confidence":item.min_confidence}, request=request)
    db.commit(); db.refresh(item)
    return item


@router.delete("/{ppe_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_ppe(ppe_id: uuid.UUID, request: Request, user: User = Depends(require_permission("ppe.manage")), db: Session = Depends(get_db)):
    item = db.get(PPEType, ppe_id)
    if not item:
        raise HTTPException(404, "EPP inexistente")
    item.active = False; item.updated_at = datetime.now(timezone.utc)
    add_audit(db, user, "DEACTIVATE", "ppe_type", str(item.id), after={"active":False}, request=request)
    db.commit()
    return Response(status_code=204)
