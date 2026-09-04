from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

HEARTBEAT_KEY = "hys:alert-worker:heartbeat"
from app.api.deps import is_superadmin, require_permission
from app.core.config import settings
from app.db.session import get_db
from app.models.access import User
from app.models.camera import Camera
from app.models.organization import Organization
from app.models.safety import (
    AlertEscalation,
    AlertPolicy,
    NotificationChannel,
    NotificationDelivery,
    SafetyDetectionEvent,
    Zone,
)
from app.schemas.alerts import (
    AlertEscalationOut,
    AlertPolicyOut,
    AlertPolicyUpdate,
    ChannelListResponse,
    DeliveryListResponse,
    EscalationListResponse,
    InboxResponse,
    MonitoringInboxItem,
    MonitoringSummary,
    NotificationChannelOut,
    NotificationChannelUpdate,
    NotificationDeliveryOut,
    PolicyListResponse,
    WorkerStatus,
)
from app.services.alerting import (
    DEFAULT_CHANNELS,
    ensure_alert_policies,
    ensure_notification_channels,
    process_alerts,
    recompute_event_sla,
    utc,
)
from app.services.audit import add_audit

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


def _org_scope_stmt(stmt, model, user: User):
    if not is_superadmin(user):
        stmt = stmt.where(model.organization_id == user.organization_id)
    return stmt


def _resolve_org(db: Session, user: User, organization_id: uuid.UUID | None) -> uuid.UUID:
    if not is_superadmin(user):
        if not user.organization_id:
            raise HTTPException(403, "Usuario sin organización")
        if organization_id and organization_id != user.organization_id:
            raise HTTPException(403, "Fuera del alcance de su organización")
        return user.organization_id
    if organization_id:
        if not db.get(Organization, organization_id):
            raise HTTPException(404, "Organización inexistente")
        return organization_id
    event_org = db.scalar(select(SafetyDetectionEvent.organization_id).order_by(desc(SafetyDetectionEvent.confirmed_at)).limit(1))
    if event_org:
        return event_org
    org = db.scalar(select(Organization.id).order_by(Organization.created_at).limit(1))
    if not org:
        raise HTTPException(404, "No existen organizaciones")
    return org


def _name_map(db: Session, ids):
    ids = [x for x in ids if x]
    if not ids:
        return {}
    return {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(ids)))}


def _sla_seconds(due, now):
    due = utc(due)
    return (due - now).total_seconds() if due else None


@router.get("/worker", response_model=WorkerStatus)
def worker_status(user: User = Depends(require_permission("monitoring.read"))):
    try:
        from redis import Redis
        raw = Redis.from_url(settings.redis_url, socket_timeout=2).get(HEARTBEAT_KEY)
        if not raw:
            return WorkerStatus(status="OFFLINE")
        text = raw.decode() if isinstance(raw, bytes) else str(raw)
        ts = datetime.fromisoformat(text)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds()
        return WorkerStatus(status="ONLINE" if age <= max(20, settings.alert_poll_interval_seconds * 4) else "STALE", age_seconds=age, heartbeat=text)
    except Exception:
        return WorkerStatus(status="ERROR")


@router.get("/summary", response_model=MonitoringSummary)
def summary(user: User = Depends(require_permission("monitoring.read")), db: Session = Depends(get_db)):
    base = [SafetyDetectionEvent.operational_status != "RESOLVED", SafetyDetectionEvent.archived_at.is_(None)]
    if not is_superadmin(user):
        base.append(SafetyDetectionEvent.organization_id == user.organization_id)
    def count(*extra):
        return int(db.scalar(select(func.count()).select_from(SafetyDetectionEvent).where(*base, *extra)) or 0)
    notif_stmt = select(func.count()).select_from(NotificationDelivery).where(NotificationDelivery.status == "FAILED")
    if not is_superadmin(user):
        notif_stmt = notif_stmt.where(NotificationDelivery.organization_id == user.organization_id)
    assigned = count(SafetyDetectionEvent.assigned_to_user_id == user.id)
    return MonitoringSummary(
        active=count(),
        unacknowledged=count(SafetyDetectionEvent.acknowledged_at.is_(None)),
        ack_overdue=count(SafetyDetectionEvent.ack_sla_status == "BREACHED", SafetyDetectionEvent.acknowledged_at.is_(None)),
        resolution_overdue=count(SafetyDetectionEvent.resolve_sla_status == "BREACHED"),
        escalated=count(SafetyDetectionEvent.escalation_level > 0),
        critical=count(SafetyDetectionEvent.severity == "CRITICA"),
        assigned_to_me=assigned,
        notifications_failed=int(db.scalar(notif_stmt) or 0),
    )


@router.get("/inbox", response_model=InboxResponse)
def inbox(
    severity: str | None = Query(default=None),
    sla: str | None = Query(default=None),
    operational_status: str | None = Query(default=None),
    assigned_to_me: bool = Query(default=False),
    include_resolved: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    user: User = Depends(require_permission("monitoring.read")),
    db: Session = Depends(get_db),
):
    stmt = select(SafetyDetectionEvent).where(SafetyDetectionEvent.archived_at.is_(None))
    if not is_superadmin(user):
        stmt = stmt.where(SafetyDetectionEvent.organization_id == user.organization_id)
    if not include_resolved:
        stmt = stmt.where(SafetyDetectionEvent.operational_status != "RESOLVED")
    if severity:
        stmt = stmt.where(SafetyDetectionEvent.severity == severity.upper())
    if operational_status:
        stmt = stmt.where(SafetyDetectionEvent.operational_status == operational_status.upper())
    if assigned_to_me:
        stmt = stmt.where(SafetyDetectionEvent.assigned_to_user_id == user.id)
    if sla:
        sla = sla.upper()
        if sla == "ACK_OVERDUE":
            stmt = stmt.where(SafetyDetectionEvent.ack_sla_status == "BREACHED", SafetyDetectionEvent.acknowledged_at.is_(None))
        elif sla == "RESOLUTION_OVERDUE":
            stmt = stmt.where(SafetyDetectionEvent.resolve_sla_status == "BREACHED")
        elif sla == "ESCALATED":
            stmt = stmt.where(SafetyDetectionEvent.escalation_level > 0)
        elif sla == "ON_TIME":
            stmt = stmt.where(SafetyDetectionEvent.ack_sla_status != "BREACHED", SafetyDetectionEvent.resolve_sla_status != "BREACHED", SafetyDetectionEvent.escalation_level == 0)
    rows = list(db.scalars(stmt.order_by(desc(SafetyDetectionEvent.confirmed_at)).limit(limit)))
    now = datetime.now(timezone.utc)
    names = _name_map(db, [x.assigned_to_user_id for x in rows])
    camera_map = {x.id: x.code for x in db.scalars(select(Camera).where(Camera.id.in_([r.camera_id for r in rows])))} if rows else {}
    zone_ids = [r.zone_id for r in rows if r.zone_id]
    zone_map = {x.id: x.code for x in db.scalars(select(Zone).where(Zone.id.in_(zone_ids)))} if zone_ids else {}
    notif_counts = {}
    if rows:
        for eid, cnt in db.execute(select(NotificationDelivery.event_id, func.count()).where(NotificationDelivery.event_id.in_([r.id for r in rows])).group_by(NotificationDelivery.event_id)):
            notif_counts[eid] = int(cnt)
    items=[]
    for e in rows:
        recompute_event_sla(e, now)
        items.append(MonitoringInboxItem(
            event_id=e.id,event_number=e.event_number,organization_id=e.organization_id,camera_code=camera_map.get(e.camera_id),zone_code=zone_map.get(e.zone_id),
            track_id=e.track_id,ppe_code=e.ppe_code,ppe_name=e.ppe_name,severity=e.severity,priority=e.alert_priority,technical_status=e.status,
            operational_status=e.operational_status,review_outcome=e.review_outcome,assigned_to_user_id=e.assigned_to_user_id,assigned_to_name=names.get(e.assigned_to_user_id),
            confirmed_at=e.confirmed_at,last_seen_at=e.last_seen_at,acknowledged_at=e.acknowledged_at,resolved_at=e.resolved_at,
            sla_ack_due_at=e.sla_ack_due_at,sla_resolve_due_at=e.sla_resolve_due_at,ack_sla_status=e.ack_sla_status,resolve_sla_status=e.resolve_sla_status,
            escalation_level=e.escalation_level,next_escalation_at=e.next_escalation_at,seconds_to_ack_due=_sla_seconds(e.sla_ack_due_at,now),seconds_to_resolve_due=_sla_seconds(e.sla_resolve_due_at,now),
            notification_count=notif_counts.get(e.id,0),evidence_count=e.evidence_count,
        ))
    rank={"P0_CRITICA":0,"P1_ALTA":1,"P2_ADVERTENCIA":2,"P3_INFO":3}
    items.sort(key=lambda x:(0 if x.resolve_sla_status=="BREACHED" else 1 if x.ack_sla_status=="BREACHED" else 2, rank.get(x.priority,9), -x.escalation_level, x.confirmed_at))
    return InboxResponse(total=len(items),items=items)


@router.get("/policies", response_model=PolicyListResponse)
def policies(organization_id: uuid.UUID | None = Query(default=None), user: User = Depends(require_permission("monitoring.read")), db: Session = Depends(get_db)):
    org_id = _resolve_org(db,user,organization_id)
    rows = ensure_alert_policies(db,org_id); db.commit()
    return PolicyListResponse(organization_id=org_id,items=[AlertPolicyOut.model_validate(x,from_attributes=True) for x in rows])


@router.patch("/policies/{policy_id}", response_model=AlertPolicyOut)
def update_policy(policy_id: uuid.UUID, body: AlertPolicyUpdate, request: Request, user: User = Depends(require_permission("monitoring.manage")), db: Session = Depends(get_db)):
    row=db.get(AlertPolicy,policy_id)
    if not row: raise HTTPException(404,"Política inexistente")
    if not is_superadmin(user) and row.organization_id!=user.organization_id: raise HTTPException(403,"Fuera del alcance de su organización")
    before={k:getattr(row,k) for k in ['acknowledge_sla_seconds','resolve_sla_seconds','escalation_after_seconds','escalation_repeat_seconds','max_escalation_level','notification_channels','active']}
    data=body.model_dump(exclude_none=True)
    if 'notification_channels' in data:
        channels=[x.upper() for x in data['notification_channels']]
        invalid=[x for x in channels if x not in DEFAULT_CHANNELS]
        if invalid: raise HTTPException(422,f"Canales inválidos: {', '.join(invalid)}")
        data['notification_channels']=channels
    for k,v in data.items(): setattr(row,k,v)
    row.updated_at=datetime.now(timezone.utc)
    add_audit(db,user,'ALERT_POLICY_UPDATE','AlertPolicy',str(row.id),before=before,after=data,request=request,organization_id=row.organization_id)
    db.commit();db.refresh(row)
    return AlertPolicyOut.model_validate(row,from_attributes=True)


@router.get("/channels", response_model=ChannelListResponse)
def channels(organization_id: uuid.UUID | None = Query(default=None), user: User = Depends(require_permission("monitoring.read")), db: Session = Depends(get_db)):
    org_id=_resolve_org(db,user,organization_id)
    rows=ensure_notification_channels(db,org_id);db.commit()
    return ChannelListResponse(organization_id=org_id,items=[NotificationChannelOut.model_validate(x,from_attributes=True) for x in rows])


@router.patch("/channels/{channel_id}", response_model=NotificationChannelOut)
def update_channel(channel_id: uuid.UUID, body: NotificationChannelUpdate, request: Request, user: User = Depends(require_permission("monitoring.manage")), db: Session = Depends(get_db)):
    row=db.get(NotificationChannel,channel_id)
    if not row: raise HTTPException(404,"Canal inexistente")
    if not is_superadmin(user) and row.organization_id!=user.organization_id: raise HTTPException(403,"Fuera del alcance de su organización")
    data=body.model_dump(exclude_unset=True)
    if row.channel=='IN_APP' and data.get('enabled') is False: raise HTTPException(422,"IN_APP no puede deshabilitarse")
    for k,v in data.items(): setattr(row,k,v)
    if row.channel=='IN_APP':
        row.enabled=True;row.configuration_status='READY';row.destination='Bandeja de Monitoreo'
    elif row.enabled:
        if row.channel=='WHATSAPP':
            ready=bool(row.destination and settings.alert_whatsapp_webhook_url)
        elif row.channel=='EMAIL':
            ready=bool(row.destination and settings.alert_smtp_host and settings.alert_smtp_from)
        else:
            ready=bool(row.destination)
        row.configuration_status='READY' if ready else 'CONFIG_REQUIRED'
    else:
        row.configuration_status='DISABLED'
    row.updated_at=datetime.now(timezone.utc)
    add_audit(db,user,'NOTIFICATION_CHANNEL_UPDATE','NotificationChannel',str(row.id),after={'channel':row.channel,'enabled':row.enabled,'configuration_status':row.configuration_status,'destination':row.destination},request=request,organization_id=row.organization_id)
    db.commit();db.refresh(row)
    return NotificationChannelOut.model_validate(row,from_attributes=True)


@router.get("/deliveries", response_model=DeliveryListResponse)
def deliveries(limit:int=Query(default=100,ge=1,le=500), status:str|None=Query(default=None), include_archived:bool=Query(default=False), user:User=Depends(require_permission("monitoring.read")), db:Session=Depends(get_db)):
    stmt=select(NotificationDelivery).join(SafetyDetectionEvent, SafetyDetectionEvent.id==NotificationDelivery.event_id).order_by(desc(NotificationDelivery.created_at)).limit(limit)
    if not include_archived:stmt=stmt.where(SafetyDetectionEvent.archived_at.is_(None))
    if not is_superadmin(user):stmt=stmt.where(NotificationDelivery.organization_id==user.organization_id)
    if status:stmt=stmt.where(NotificationDelivery.status==status.upper())
    rows=list(db.scalars(stmt)); event_numbers={e.id:e.event_number for e in db.scalars(select(SafetyDetectionEvent).where(SafetyDetectionEvent.id.in_([x.event_id for x in rows])))} if rows else {}
    items=[NotificationDeliveryOut(id=x.id,event_id=x.event_id,event_number=event_numbers.get(x.event_id),channel=x.channel,trigger_type=x.trigger_type,escalation_level=x.escalation_level,recipient=x.recipient,status=x.status,attempt_count=x.attempt_count,external_reference=x.external_reference,error_message=x.error_message,created_at=x.created_at,sent_at=x.sent_at) for x in rows]
    return DeliveryListResponse(total=len(items),items=items)


@router.get("/events/{event_id}/escalations", response_model=EscalationListResponse)
def escalations(event_id:uuid.UUID,user:User=Depends(require_permission("monitoring.read")),db:Session=Depends(get_db)):
    event=db.get(SafetyDetectionEvent,event_id)
    if not event:raise HTTPException(404,"Evento inexistente")
    if not is_superadmin(user) and event.organization_id!=user.organization_id:raise HTTPException(403,"Fuera del alcance de su organización")
    rows=list(db.scalars(select(AlertEscalation).where(AlertEscalation.event_id==event_id).order_by(AlertEscalation.level)))
    return EscalationListResponse(total=len(rows),items=[AlertEscalationOut.model_validate(x,from_attributes=True) for x in rows])


@router.post("/process-once")
def process_once(user:User=Depends(require_permission("monitoring.manage")),db:Session=Depends(get_db)):
    # QA / operación manual: no dispara red externa; el worker es quien entrega canales externos configurados.
    return process_alerts(db,send_external=False)
