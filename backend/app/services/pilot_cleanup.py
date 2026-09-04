from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.access import User
from app.models.organization import Organization
from app.models.safety import AlertPolicy, PilotCleanupRun, SafetyDetectionEvent, SafetyEventAction, SafetyEventEvidence
from app.models.vision import CameraVisionSetting
from app.services.alerting import SEVERITY_POLICY_DEFAULTS

def cleanup_pilot(db:Session,organization:Organization,actor:User|None=None,reason='Limpieza controlada del piloto antes de analytics v0.9.0'):
    now=datetime.now(timezone.utc)
    events=list(db.scalars(select(SafetyDetectionEvent).where(SafetyDetectionEvent.organization_id==organization.id,SafetyDetectionEvent.archived_at.is_(None))))
    evidence=int(db.scalar(select(func.count()).select_from(SafetyEventEvidence).where(SafetyEventEvidence.organization_id==organization.id)) or 0)
    actions=int(db.scalar(select(func.count()).select_from(SafetyEventAction).where(SafetyEventAction.organization_id==organization.id)) or 0)
    run=PilotCleanupRun(organization_id=organization.id,actor_user_id=actor.id if actor else None,status='RUNNING',reason=reason,archived_events=0,closed_technical_events=0,resolved_operational_events=0,disabled_compliance_cameras=0,restored_sla_policies=0,preserved_evidence=evidence,preserved_actions=actions,snapshot_json={'pre_cleanup_events':len(events),'preserved_evidence':evidence,'preserved_actions':actions},started_at=now)
    db.add(run); db.flush()
    closed=resolved=0
    for e in events:
      e.data_origin='QA_PILOT'; e.analytics_excluded=True; e.archived_at=now; e.archived_by_user_id=actor.id if actor else None; e.archive_reason=reason; e.next_escalation_at=None
      if e.status=='OPEN': e.status='CLOSED'; e.ended_at=now; e.close_reason='PILOT_CLEANUP_ARCHIVE'; closed+=1
      if e.operational_status!='RESOLVED': e.operational_status='RESOLVED'; e.resolved_at=now; e.resolved_by_user_id=actor.id if actor else None; e.resolution_note=reason; resolved+=1
      db.add(SafetyEventAction(organization_id=e.organization_id,event_id=e.id,actor_user_id=actor.id if actor else None,action='PILOT_ARCHIVED',from_status=None,to_status='RESOLVED',details={'reason':reason,'analytics_excluded':True},created_at=now))
    configs=list(db.scalars(select(CameraVisionSetting).where(CameraVisionSetting.organization_id==organization.id,CameraVisionSetting.compliance_enabled.is_(True))))
    for c in configs:c.compliance_enabled=False
    policies=list(db.scalars(select(AlertPolicy).where(AlertPolicy.organization_id==organization.id)))
    restored=0
    for p in policies:
      cfg=SEVERITY_POLICY_DEFAULTS.get(p.severity)
      if not cfg: continue
      for k in ('acknowledge_sla_seconds','resolve_sla_seconds','escalation_after_seconds','escalation_repeat_seconds','max_escalation_level'):setattr(p,k,cfg[k])
      p.updated_at=now; restored+=1
    run.archived_events=len(events);run.closed_technical_events=closed;run.resolved_operational_events=resolved;run.disabled_compliance_cameras=len(configs);run.restored_sla_policies=restored;run.status='COMPLETED';run.completed_at=now;run.snapshot_json={**run.snapshot_json,'post_active_events':0,'sla_defaults_restored':restored,'compliance_disabled':len(configs)}
    db.commit();db.refresh(run);return run
