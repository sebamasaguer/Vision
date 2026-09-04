import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import ensure_org_access, is_superadmin, require_permission
from app.db.session import get_db
from app.models.access import User
from app.models.camera import Camera
from app.models.safety import PPEType, Zone, ZonePPERule
from app.schemas.safety import ZoneCreate, ZoneOut, ZoneRuleOut, ZoneRuleSet, ZoneUpdate
from app.services.audit import add_audit

router = APIRouter(prefix="/zones", tags=["Zonas y reglas EPP"])


def _get_zone(db: Session, zone_id: uuid.UUID, user: User) -> Zone:
    zone = db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(404, "Zona inexistente")
    ensure_org_access(user, zone.organization_id)
    return zone


def _serialize_rule(rule: ZonePPERule, ppe: PPEType) -> ZoneRuleOut:
    return ZoneRuleOut(
        id=rule.id, organization_id=rule.organization_id, zone_id=rule.zone_id, ppe_type_id=rule.ppe_type_id,
        ppe_code=ppe.code, ppe_name=ppe.name, requirement=rule.requirement, severity=rule.severity,
        min_confidence=rule.min_confidence, effective_min_confidence=rule.min_confidence if rule.min_confidence is not None else ppe.min_confidence,
        schedule_start=rule.schedule_start, schedule_end=rule.schedule_end, task=rule.task, risk_level=rule.risk_level,
        operation_type=rule.operation_type, active=rule.active, created_at=rule.created_at, updated_at=rule.updated_at,
    )


@router.get("", response_model=list[ZoneOut])
def list_zones(camera_id: uuid.UUID | None = None, include_inactive: bool = False, user: User = Depends(require_permission("zone.read")), db: Session = Depends(get_db)):
    stmt = select(Zone).order_by(Zone.name)
    if not is_superadmin(user):
        stmt = stmt.where(Zone.organization_id == user.organization_id)
    if camera_id:
        cam = db.get(Camera, camera_id)
        if not cam:
            raise HTTPException(404, "Cámara inexistente")
        ensure_org_access(user, cam.organization_id)
        stmt = stmt.where(Zone.camera_id == camera_id)
    if not include_inactive:
        stmt = stmt.where(Zone.active.is_(True))
    return list(db.scalars(stmt))


@router.get("/{zone_id}", response_model=ZoneOut)
def get_zone(zone_id: uuid.UUID, user: User = Depends(require_permission("zone.read")), db: Session = Depends(get_db)):
    return _get_zone(db, zone_id, user)


@router.post("", response_model=ZoneOut, status_code=status.HTTP_201_CREATED)
def create_zone(payload: ZoneCreate, request: Request, user: User = Depends(require_permission("zone.manage")), db: Session = Depends(get_db)):
    cam = db.get(Camera, payload.camera_id)
    if not cam:
        raise HTTPException(404, "Cámara inexistente")
    ensure_org_access(user, cam.organization_id)
    item = Zone(
        organization_id=cam.organization_id, site_id=cam.site_id, plant_id=cam.plant_id, sector_id=cam.sector_id,
        camera_id=cam.id, code=payload.code.strip().upper(), name=payload.name.strip(), description=payload.description,
        polygon_points=[p.model_dump() for p in payload.polygon_points], active=payload.active,
    )
    db.add(item)
    try:
        db.flush()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "Código de zona duplicado para la cámara")
    add_audit(db, user, "CREATE", "zone", str(item.id), after={"camera_id":str(item.camera_id),"code":item.code,"name":item.name,"points":len(item.polygon_points)}, request=request, organization_id=item.organization_id)
    db.commit(); db.refresh(item)
    return item


@router.patch("/{zone_id}", response_model=ZoneOut)
def update_zone(zone_id: uuid.UUID, payload: ZoneUpdate, request: Request, user: User = Depends(require_permission("zone.manage")), db: Session = Depends(get_db)):
    zone = _get_zone(db, zone_id, user)
    before = {"name":zone.name,"active":zone.active,"points":len(zone.polygon_points)}
    data = payload.model_dump(exclude_unset=True)
    if "polygon_points" in data and data["polygon_points"] is not None:
        zone.polygon_points = [{"x":p["x"],"y":p["y"]} if isinstance(p,dict) else p.model_dump() for p in data.pop("polygon_points")]
    for field, value in data.items():
        setattr(zone, field, value)
    zone.updated_at = datetime.now(timezone.utc)
    add_audit(db, user, "UPDATE", "zone", str(zone.id), before=before, after={"name":zone.name,"active":zone.active,"points":len(zone.polygon_points)}, request=request, organization_id=zone.organization_id)
    db.commit(); db.refresh(zone)
    return zone


@router.delete("/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_zone(zone_id: uuid.UUID, request: Request, user: User = Depends(require_permission("zone.manage")), db: Session = Depends(get_db)):
    zone = _get_zone(db, zone_id, user)
    zone.active = False; zone.updated_at = datetime.now(timezone.utc)
    db.query(ZonePPERule).filter(ZonePPERule.zone_id == zone.id).update({ZonePPERule.active: False}, synchronize_session=False)
    add_audit(db, user, "DEACTIVATE", "zone", str(zone.id), after={"active":False}, request=request, organization_id=zone.organization_id)
    db.commit()
    return Response(status_code=204)


@router.get("/{zone_id}/rules", response_model=list[ZoneRuleOut])
def list_zone_rules(zone_id: uuid.UUID, user: User = Depends(require_permission("zone.read")), db: Session = Depends(get_db)):
    zone = _get_zone(db, zone_id, user)
    rows = db.execute(
        select(ZonePPERule, PPEType).join(PPEType, PPEType.id == ZonePPERule.ppe_type_id)
        .where(ZonePPERule.zone_id == zone.id).order_by(PPEType.name)
    ).all()
    return [_serialize_rule(rule, ppe) for rule, ppe in rows]


@router.put("/{zone_id}/rules", response_model=list[ZoneRuleOut])
def replace_zone_rules(zone_id: uuid.UUID, payload: ZoneRuleSet, request: Request, user: User = Depends(require_permission("zone.manage")), db: Session = Depends(get_db)):
    zone = _get_zone(db, zone_id, user)
    ppe_ids = [r.ppe_type_id for r in payload.rules]
    ppes = {p.id:p for p in db.scalars(select(PPEType).where(PPEType.id.in_(ppe_ids)))} if ppe_ids else {}
    missing = [str(x) for x in ppe_ids if x not in ppes]
    if missing:
        raise HTTPException(422, {"message":"EPP inexistente","ids":missing})

    before_count = db.scalar(select(func.count()).select_from(ZonePPERule).where(ZonePPERule.zone_id == zone.id)) or 0
    db.execute(delete(ZonePPERule).where(ZonePPERule.zone_id == zone.id))
    created: list[ZonePPERule] = []
    now = datetime.now(timezone.utc)
    for rule in payload.rules:
        item = ZonePPERule(
            organization_id=zone.organization_id, zone_id=zone.id, ppe_type_id=rule.ppe_type_id,
            requirement=rule.requirement, severity=rule.severity, min_confidence=rule.min_confidence,
            schedule_start=rule.schedule_start, schedule_end=rule.schedule_end, task=rule.task,
            risk_level=rule.risk_level, operation_type=rule.operation_type, active=rule.active,
            created_at=now, updated_at=now,
        )
        db.add(item); created.append(item)
    db.flush()
    add_audit(db, user, "REPLACE_RULES", "zone", str(zone.id), before={"rule_count":before_count}, after={"rule_count":len(created),"ppe_codes":[ppes[x.ppe_type_id].code for x in created]}, request=request, organization_id=zone.organization_id)
    db.commit()
    for item in created: db.refresh(item)
    return [_serialize_rule(item, ppes[item.ppe_type_id]) for item in sorted(created, key=lambda x: ppes[x.ppe_type_id].name)]
