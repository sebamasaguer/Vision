from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.access import User
from app.models.safety import SafetyDetectionEvent, SafetyEventAction, SafetyEventNote

VALID_OUTCOMES={'CONFIRMED','FALSE_POSITIVE'}

def _utc(dt):
    if dt is None: return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)

def add_action(db:Session,event:SafetyDetectionEvent,actor:User|None,action:str,from_status:str|None,to_status:str|None,details:dict|None=None):
    row=SafetyEventAction(organization_id=event.organization_id,event_id=event.id,actor_user_id=actor.id if actor else None,action=action,from_status=from_status,to_status=to_status,details=details or {},created_at=datetime.now(timezone.utc)); db.add(row); return row

def acknowledge(db:Session,event:SafetyDetectionEvent,user:User):
    before=event.operational_status
    if not event.acknowledged_at:
        event.acknowledged_at=datetime.now(timezone.utc); event.acknowledged_by_user_id=user.id
    if event.operational_status=='NEW': event.operational_status='ACKNOWLEDGED'
    add_action(db,event,user,'ACKNOWLEDGE',before,event.operational_status,{'response_seconds':max(0,(_utc(event.acknowledged_at)-_utc(event.confirmed_at)).total_seconds())})
    from app.services.alerting import recompute_event_sla
    recompute_event_sla(event, event.acknowledged_at)
    return event

def assign(db:Session,event:SafetyDetectionEvent,user:User,target:User|None):
    before=str(event.assigned_to_user_id) if event.assigned_to_user_id else None
    event.assigned_to_user_id=target.id if target else None
    add_action(db,event,user,'ASSIGN',event.operational_status,event.operational_status,{'from_user_id':before,'to_user_id':str(target.id) if target else None,'to_name':target.full_name if target else None})
    return event

def add_note(db:Session,event:SafetyDetectionEvent,user:User,body:str,note_type='COMMENT'):
    row=SafetyEventNote(organization_id=event.organization_id,event_id=event.id,author_user_id=user.id,note_type=note_type,body=body.strip(),created_at=datetime.now(timezone.utc)); db.add(row)
    add_action(db,event,user,'ADD_NOTE',event.operational_status,event.operational_status,{'note_type':note_type})
    return row

def review(db:Session,event:SafetyDetectionEvent,user:User,outcome:str,notes:str|None):
    outcome=outcome.upper()
    if outcome not in VALID_OUTCOMES: raise ValueError('Resultado de revisión inválido')
    before=event.operational_status; now=datetime.now(timezone.utc)
    event.review_outcome=outcome; event.reviewed_at=now; event.reviewed_by_user_id=user.id; event.review_notes=notes.strip() if notes else None
    if not event.acknowledged_at:
        event.acknowledged_at=now; event.acknowledged_by_user_id=user.id
    if outcome=='FALSE_POSITIVE':
        event.operational_status='RESOLVED'; event.resolved_at=now; event.resolved_by_user_id=user.id; event.resolution_note=notes or 'Clasificado como falso positivo'
    else:
        event.operational_status='IN_REVIEW'
    add_action(db,event,user,'REVIEW_'+outcome,before,event.operational_status,{'outcome':outcome,'notes':notes})
    if notes: add_note(db,event,user,notes,'REVIEW')
    from app.services.alerting import recompute_event_sla
    recompute_event_sla(event, now)
    if event.operational_status=='RESOLVED': event.next_escalation_at=None
    return event

def resolve(db:Session,event:SafetyDetectionEvent,user:User,note:str):
    before=event.operational_status; now=datetime.now(timezone.utc)
    if not event.acknowledged_at:
        event.acknowledged_at=now; event.acknowledged_by_user_id=user.id
    if event.review_outcome=='PENDING': event.review_outcome='CONFIRMED'; event.reviewed_at=now; event.reviewed_by_user_id=user.id
    event.operational_status='RESOLVED'; event.resolved_at=now; event.resolved_by_user_id=user.id; event.resolution_note=note.strip()
    add_note(db,event,user,note,'RESOLUTION'); add_action(db,event,user,'RESOLVE',before,'RESOLVED',{'note':note})
    from app.services.alerting import recompute_event_sla
    recompute_event_sla(event, now); event.next_escalation_at=None
    return event
