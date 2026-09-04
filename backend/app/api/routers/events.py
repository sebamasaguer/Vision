import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import is_superadmin, require_permission
from app.db.session import get_db
from app.models.access import Role, User
from app.models.camera import Camera
from app.models.safety import ComplianceEvaluation, PPEType, SafetyDetectionEvent, SafetyEventAction, SafetyEventEvidence, SafetyEventNote, Zone
from app.schemas.event_ops import AssigneeOut, EventAssignIn, EventNoteIn, EventResolveIn, EventReviewIn, EvidenceOut, TimelineItem
from app.schemas.events import SafetyEventOut, SafetyEventSummary
from app.services.audit import add_audit
from app.services.event_evidence import browser_preview_bytes, read_evidence_bytes
from app.services.event_operations import acknowledge, add_note, assign, resolve, review

router=APIRouter(prefix='/safety-events',tags=['Safety Events'])

def _utc(dt):
    if dt is None:return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _name_map(db:Session, ids):
    ids=[x for x in ids if x]
    if not ids:return {}
    return {u.id:u.full_name for u in db.scalars(select(User).where(User.id.in_(ids)))}

def _event_out(db,event):
    cam=db.get(Camera,event.camera_id); zone=db.get(Zone,event.zone_id) if event.zone_id else None
    names=_name_map(db,[event.assigned_to_user_id,event.acknowledged_by_user_id,event.reviewed_by_user_id,event.resolved_by_user_id])
    response_seconds=(_utc(event.acknowledged_at)-_utc(event.confirmed_at)).total_seconds() if event.acknowledged_at else None
    resolution_seconds=(_utc(event.resolved_at)-_utc(event.confirmed_at)).total_seconds() if event.resolved_at else None
    return SafetyEventOut(
        id=event.id,event_number=event.event_number,organization_id=event.organization_id,camera_id=event.camera_id,
        camera_code=cam.code if cam else None,camera_name=cam.name if cam else None,zone_id=event.zone_id,
        zone_code=zone.code if zone else None,zone_name=zone.name if zone else None,track_id=event.track_id,
        ppe_code=event.ppe_code,ppe_name=event.ppe_name,severity=event.severity,status=event.status,detection_status=event.detection_status,
        first_observed_at=event.first_observed_at,confirmed_at=event.confirmed_at,last_seen_at=event.last_seen_at,ended_at=event.ended_at,
        duration_seconds=event.duration_seconds,last_confidence=event.last_confidence,consensus_ratio=event.consensus_ratio,
        missing_observations=event.missing_observations,evaluable_observations=event.evaluable_observations,close_reason=event.close_reason,
        rule_snapshot=event.rule_snapshot,model_snapshot=event.model_snapshot,operational_status=event.operational_status,review_outcome=event.review_outcome,
        assigned_to_user_id=event.assigned_to_user_id,assigned_to_name=names.get(event.assigned_to_user_id),
        acknowledged_by_user_id=event.acknowledged_by_user_id,acknowledged_by_name=names.get(event.acknowledged_by_user_id),acknowledged_at=event.acknowledged_at,
        reviewed_by_user_id=event.reviewed_by_user_id,reviewed_by_name=names.get(event.reviewed_by_user_id),reviewed_at=event.reviewed_at,
        resolved_by_user_id=event.resolved_by_user_id,resolved_by_name=names.get(event.resolved_by_user_id),resolved_at=event.resolved_at,
        review_notes=event.review_notes,resolution_note=event.resolution_note,evidence_status=event.evidence_status,evidence_count=event.evidence_count,
        evidence_captured_at=event.evidence_captured_at,evidence_error=event.evidence_error,response_seconds=response_seconds,resolution_seconds=resolution_seconds,alert_priority=event.alert_priority,sla_ack_due_at=event.sla_ack_due_at,sla_resolve_due_at=event.sla_resolve_due_at,ack_sla_status=event.ack_sla_status,resolve_sla_status=event.resolve_sla_status,escalation_level=event.escalation_level,next_escalation_at=event.next_escalation_at,last_escalated_at=event.last_escalated_at,last_notification_at=event.last_notification_at)

def _get_event(db,event_id,user):
    event=db.get(SafetyDetectionEvent,event_id)
    if not event: raise HTTPException(404,'Safety Event inexistente')
    if not is_superadmin(user) and event.organization_id!=user.organization_id: raise HTTPException(403,'Fuera del alcance de su organización')
    return event

@router.get('',response_model=list[SafetyEventOut])
def list_events(status:str|None=Query(default=None),operational_status:str|None=Query(default=None),camera_id:uuid.UUID|None=Query(default=None),limit:int=Query(default=100,ge=1,le=500),user:User=Depends(require_permission('safety_event.read')),db:Session=Depends(get_db)):
    stmt=select(SafetyDetectionEvent).order_by(desc(SafetyDetectionEvent.confirmed_at)).limit(limit)
    if not is_superadmin(user): stmt=stmt.where(SafetyDetectionEvent.organization_id==user.organization_id)
    if status:
        stmt=stmt.where(SafetyDetectionEvent.status==status.upper())
        if status.upper()=='OPEN' and not operational_status:
            stmt=stmt.where(SafetyDetectionEvent.operational_status!='RESOLVED')
    if operational_status: stmt=stmt.where(SafetyDetectionEvent.operational_status==operational_status.upper())
    if camera_id: stmt=stmt.where(SafetyDetectionEvent.camera_id==camera_id)
    return [_event_out(db,e) for e in db.scalars(stmt)]

@router.get('/summary',response_model=SafetyEventSummary)
def summary(user:User=Depends(require_permission('safety_event.read')),db:Session=Depends(get_db)):
    base=[] if is_superadmin(user) else [SafetyDetectionEvent.organization_id==user.organization_id]
    def count(*extra): return int(db.scalar(select(func.count()).select_from(SafetyDetectionEvent).where(*(base+list(extra)))) or 0)
    now=datetime.now(timezone.utc); day_start=now.replace(hour=0,minute=0,second=0,microsecond=0); next_day=day_start+timedelta(days=1)
    active_filter=[SafetyDetectionEvent.status=='OPEN',SafetyDetectionEvent.operational_status!='RESOLVED']
    return SafetyEventSummary(active=count(*active_filter),critical_active=count(*active_filter,SafetyDetectionEvent.severity=='CRITICA'),high_active=count(*active_filter,SafetyDetectionEvent.severity=='ALTA'),closed_today=count(SafetyDetectionEvent.status=='CLOSED',SafetyDetectionEvent.ended_at>=day_start,SafetyDetectionEvent.ended_at<next_day),total=count())

@router.get('/assignees',response_model=list[AssigneeOut])
def assignees(event_id:uuid.UUID|None=Query(default=None),user:User=Depends(require_permission('safety_event.manage')),db:Session=Depends(get_db)):
    target_org=user.organization_id
    if event_id:
        event=_get_event(db,event_id,user); target_org=event.organization_id

    # Tenant operators may only assign active users from their own organization.
    # A system SUPERADMIN may additionally assign any active SUPERADMIN, even if
    # legacy data has that account attached to an organization instead of NULL.
    # We compose and de-duplicate the two sets in Python to avoid depending on
    # dialect-specific relationship EXISTS behavior in production PostgreSQL.
    tenant_stmt=select(User).where(User.is_active.is_(True),User.organization_id==target_org).order_by(User.full_name)
    rows=list(db.scalars(tenant_stmt).unique())
    if is_superadmin(user):
        system_stmt=(select(User)
            .join(User.roles)
            .where(User.is_active.is_(True),Role.code=='SUPERADMIN')
            .order_by(User.full_name))
        rows.extend(list(db.scalars(system_stmt).unique()))
        if user.is_active:
            rows.append(user)  # deterministic fallback for legacy bootstrap data

    unique={x.id:x for x in rows}
    ordered=sorted(unique.values(),key=lambda x:((x.full_name or '').lower(),(x.email or '').lower()))
    return [AssigneeOut(id=x.id,full_name=x.full_name,email=x.email) for x in ordered]

@router.get('/evidence/{evidence_id}/content')
def evidence_content(evidence_id:uuid.UUID,user:User=Depends(require_permission('safety_event.read')),db:Session=Depends(get_db)):
    evd=db.get(SafetyEventEvidence,evidence_id)
    if not evd: raise HTTPException(404,'Evidencia inexistente')
    if not is_superadmin(user) and evd.organization_id!=user.organization_id: raise HTTPException(403,'Fuera del alcance de su organización')
    data=read_evidence_bytes(evd)
    filename=f"{evd.kind.lower()}-{str(evd.id)[:8]}.{'mp4' if evd.mime_type.startswith('video/') else 'jpg'}"
    return Response(content=data,media_type=evd.mime_type,headers={'X-Evidence-SHA256':evd.sha256,'Cache-Control':'private, max-age=60','Content-Disposition':f'attachment; filename="{filename}"'})

@router.get('/evidence/{evidence_id}/preview')
def evidence_preview(evidence_id:uuid.UUID,user:User=Depends(require_permission('safety_event.read')),db:Session=Depends(get_db)):
    evd=db.get(SafetyEventEvidence,evidence_id)
    if not evd: raise HTTPException(404,'Evidencia inexistente')
    if not is_superadmin(user) and evd.organization_id!=user.organization_id: raise HTTPException(403,'Fuera del alcance de su organización')
    source=read_evidence_bytes(evd)
    try:
        data,mime,transcoded=browser_preview_bytes(source,evd.mime_type)
    except Exception as exc:
        raise HTTPException(500,f'No se pudo generar preview browser-compatible: {exc}')
    headers={'X-Source-Evidence-SHA256':evd.sha256,'X-Evidence-Preview-Transcoded':'true' if transcoded else 'false','Cache-Control':'private, max-age=60','Content-Disposition':'inline'}
    return Response(content=data,media_type=mime,headers=headers)

@router.get('/evaluations')
def evaluations(camera_id:uuid.UUID|None=Query(default=None),track_id:str|None=Query(default=None),limit:int=Query(default=100,ge=1,le=500),user:User=Depends(require_permission('safety_event.read')),db:Session=Depends(get_db)):
    stmt=select(ComplianceEvaluation).order_by(desc(ComplianceEvaluation.evaluated_at)).limit(limit)
    if not is_superadmin(user):stmt=stmt.where(ComplianceEvaluation.organization_id==user.organization_id)
    if camera_id:stmt=stmt.where(ComplianceEvaluation.camera_id==camera_id)
    if track_id:stmt=stmt.where(ComplianceEvaluation.track_id==track_id)
    return [{'id':str(x.id),'camera_id':str(x.camera_id),'zone_id':str(x.zone_id) if x.zone_id else None,'event_id':str(x.event_id) if x.event_id else None,'track_id':x.track_id,'ppe_code':x.ppe_code,'observed_status':x.observed_status,'compliance_status':x.compliance_status,'confidence':x.confidence,'consensus_ratio':x.consensus_ratio,'missing_observations':x.missing_observations,'evaluable_observations':x.evaluable_observations,'details':x.details,'evaluated_at':x.evaluated_at} for x in db.scalars(stmt)]

@router.get('/{event_id}/evidence',response_model=list[EvidenceOut])
def evidence_list(event_id:uuid.UUID,user:User=Depends(require_permission('safety_event.read')),db:Session=Depends(get_db)):
    event=_get_event(db,event_id,user)
    rows=db.scalars(select(SafetyEventEvidence).where(SafetyEventEvidence.event_id==event.id).order_by(SafetyEventEvidence.captured_at)).all()
    return [EvidenceOut.model_validate({'id':x.id,'kind':x.kind,'mime_type':x.mime_type,'sha256':x.sha256,'size_bytes':x.size_bytes,'captured_at':x.captured_at,'source_frame_at':x.source_frame_at,'immutable':x.immutable,'metadata_json':x.metadata_json}) for x in rows]

@router.get('/{event_id}/timeline',response_model=list[TimelineItem])
def timeline(event_id:uuid.UUID,user:User=Depends(require_permission('safety_event.read')),db:Session=Depends(get_db)):
    event=_get_event(db,event_id,user); actions=list(db.scalars(select(SafetyEventAction).where(SafetyEventAction.event_id==event.id).order_by(SafetyEventAction.created_at))); notes=list(db.scalars(select(SafetyEventNote).where(SafetyEventNote.event_id==event.id).order_by(SafetyEventNote.created_at)))
    names=_name_map(db,[x.actor_user_id for x in actions]+[x.author_user_id for x in notes]); out=[]
    for x in actions: out.append(TimelineItem(id=x.id,type='ACTION',action=x.action,actor_user_id=x.actor_user_id,actor_name=names.get(x.actor_user_id),from_status=x.from_status,to_status=x.to_status,details=x.details,created_at=x.created_at))
    for x in notes: out.append(TimelineItem(id=x.id,type='NOTE',action=x.note_type,body=x.body,actor_user_id=x.author_user_id,actor_name=names.get(x.author_user_id),details={},created_at=x.created_at))
    return sorted(out,key=lambda x:x.created_at)

@router.post('/{event_id}/acknowledge',response_model=SafetyEventOut)
def acknowledge_event(event_id:uuid.UUID,request:Request,user:User=Depends(require_permission('safety_event.manage')),db:Session=Depends(get_db)):
    event=_get_event(db,event_id,user); before={'operational_status':event.operational_status}; acknowledge(db,event,user); add_audit(db,user,'SAFETY_EVENT_ACKNOWLEDGE','SafetyDetectionEvent',str(event.id),before=before,after={'operational_status':event.operational_status},request=request,organization_id=event.organization_id); db.commit(); return _event_out(db,event)

@router.post('/{event_id}/assign',response_model=SafetyEventOut)
def assign_event(event_id:uuid.UUID,body:EventAssignIn,request:Request,user:User=Depends(require_permission('safety_event.manage')),db:Session=Depends(get_db)):
    event=_get_event(db,event_id,user); target=db.get(User,body.user_id) if body.user_id else None
    if target:
        system_superadmin_target=any(r.code=='SUPERADMIN' for r in target.roles)
        allowed_target=target.is_active and (
            target.organization_id==event.organization_id
            or (is_superadmin(user) and system_superadmin_target)
        )
        if not allowed_target: raise HTTPException(400,'Responsable inválido para la organización')
    assign(db,event,user,target); add_audit(db,user,'SAFETY_EVENT_ASSIGN','SafetyDetectionEvent',str(event.id),after={'assigned_to_user_id':str(target.id) if target else None},request=request,organization_id=event.organization_id); db.commit(); return _event_out(db,event)

@router.post('/{event_id}/notes',status_code=201)
def note_event(event_id:uuid.UUID,body:EventNoteIn,request:Request,user:User=Depends(require_permission('safety_event.manage')),db:Session=Depends(get_db)):
    event=_get_event(db,event_id,user); row=add_note(db,event,user,body.body); add_audit(db,user,'SAFETY_EVENT_NOTE','SafetyDetectionEvent',str(event.id),after={'note_id':str(row.id)},request=request,organization_id=event.organization_id); db.commit(); return {'id':str(row.id),'status':'created'}

@router.post('/{event_id}/review',response_model=SafetyEventOut)
def review_event(event_id:uuid.UUID,body:EventReviewIn,request:Request,user:User=Depends(require_permission('safety_event.manage')),db:Session=Depends(get_db)):
    event=_get_event(db,event_id,user)
    try: review(db,event,user,body.outcome,body.notes)
    except ValueError as exc: raise HTTPException(422,str(exc))
    add_audit(db,user,'SAFETY_EVENT_REVIEW','SafetyDetectionEvent',str(event.id),after={'outcome':event.review_outcome,'operational_status':event.operational_status},request=request,organization_id=event.organization_id); db.commit(); return _event_out(db,event)

@router.post('/{event_id}/resolve',response_model=SafetyEventOut)
def resolve_event(event_id:uuid.UUID,body:EventResolveIn,request:Request,user:User=Depends(require_permission('safety_event.manage')),db:Session=Depends(get_db)):
    event=_get_event(db,event_id,user); resolve(db,event,user,body.note); add_audit(db,user,'SAFETY_EVENT_RESOLVE','SafetyDetectionEvent',str(event.id),after={'operational_status':'RESOLVED'},request=request,organization_id=event.organization_id); db.commit(); return _event_out(db,event)

@router.get('/{event_id}',response_model=SafetyEventOut)
def get_event(event_id:uuid.UUID,user:User=Depends(require_permission('safety_event.read')),db:Session=Depends(get_db)):
    return _event_out(db,_get_event(db,event_id,user))
