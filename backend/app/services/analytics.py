from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import csv, io
from sqlalchemy import case, distinct, func, select
from sqlalchemy.orm import Session
from app.models.camera import Camera
from app.models.safety import ComplianceEvaluation, SafetyDetectionEvent, Zone

def utc_now(): return datetime.now(timezone.utc)

def normalize_range(date_from=None,date_to=None):
    end=date_to or utc_now(); start=date_from or (end-timedelta(days=30))
    if start.tzinfo is None:start=start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:end=end.replace(tzinfo=timezone.utc)
    return start,end

def event_filters(org_id,start,end,include_qa=False):
    f=[SafetyDetectionEvent.organization_id==org_id,SafetyDetectionEvent.confirmed_at>=start,SafetyDetectionEvent.confirmed_at<end]
    if not include_qa:f += [SafetyDetectionEvent.analytics_excluded.is_(False)]
    return f

def executive_kpis(db:Session,org_id,start,end,include_qa=False):
    f=event_filters(org_id,start,end,include_qa)
    rows=list(db.scalars(select(SafetyDetectionEvent).where(*f)))
    total=len(rows); denom=max(total,1)
    ack=[(e.acknowledged_at-e.confirmed_at).total_seconds() for e in rows if e.acknowledged_at]
    res=[(e.resolved_at-e.confirmed_at).total_seconds() for e in rows if e.resolved_at]
    ack_eligible=[e for e in rows if e.acknowledged_at or e.ack_sla_status in ('MET','BREACHED')]
    res_eligible=[e for e in rows if e.resolved_at or e.resolve_sla_status in ('MET','BREACHED')]
    evals=list(db.scalars(select(ComplianceEvaluation).where(ComplianceEvaluation.organization_id==org_id,ComplianceEvaluation.evaluated_at>=start,ComplianceEvaluation.evaluated_at<end)))
    evaluable=[x for x in evals if x.compliance_status in ('COMPLIANT','NON_COMPLIANT')]
    return dict(
      period_from=start,period_to=end,total_events=total,active_events=sum(e.operational_status!='RESOLVED' and e.archived_at is None for e in rows),
      critical_events=sum(e.severity=='CRITICA' for e in rows),high_events=sum(e.severity=='ALTA' for e in rows),warning_events=sum(e.severity=='ADVERTENCIA' for e in rows),
      unique_tracks=len({(e.camera_id,e.track_id) for e in rows}),false_positive_rate=round(100*sum(e.review_outcome=='FALSE_POSITIVE' for e in rows)/denom,2),
      evidence_coverage_rate=round(100*sum((e.evidence_count or 0)>0 for e in rows)/denom,2),
      ack_sla_met_rate=round(100*sum(e.ack_sla_status=='MET' for e in ack_eligible)/max(len(ack_eligible),1),2),
      resolution_sla_met_rate=round(100*sum(e.resolve_sla_status=='MET' for e in res_eligible)/max(len(res_eligible),1),2),
      escalation_rate=round(100*sum((e.escalation_level or 0)>0 for e in rows)/denom,2),
      avg_ack_seconds=round(sum(ack)/len(ack),2) if ack else None,avg_resolution_seconds=round(sum(res)/len(res),2) if res else None,
      compliance_rate=round(100*sum(x.compliance_status=='COMPLIANT' for x in evaluable)/len(evaluable),2) if evaluable else None,
      archived_qa_events=int(db.scalar(select(func.count()).select_from(SafetyDetectionEvent).where(SafetyDetectionEvent.organization_id==org_id,SafetyDetectionEvent.data_origin=='QA_PILOT',SafetyDetectionEvent.archived_at.is_not(None))) or 0))

def trend(db,org_id,start,end,include_qa=False):
    rows=list(db.scalars(select(SafetyDetectionEvent).where(*event_filters(org_id,start,end,include_qa)).order_by(SafetyDetectionEvent.confirmed_at)))
    buckets=defaultdict(lambda:dict(events=0,critical=0,high=0,warning=0,false_positive=0,escalated=0))
    for e in rows:
      k=e.confirmed_at.date().isoformat(); b=buckets[k]; b['events']+=1; b['critical']+=e.severity=='CRITICA'; b['high']+=e.severity=='ALTA'; b['warning']+=e.severity=='ADVERTENCIA'; b['false_positive']+=e.review_outcome=='FALSE_POSITIVE'; b['escalated']+=(e.escalation_level or 0)>0
    return [dict(bucket=k,**v) for k,v in sorted(buckets.items())]

def top_risks(db,org_id,start,end,dimension='ppe',include_qa=False,limit=10):
    rows=list(db.scalars(select(SafetyDetectionEvent).where(*event_filters(org_id,start,end,include_qa))))
    if dimension=='ppe': pairs=[(e.ppe_code,e.ppe_name) for e in rows]
    elif dimension=='camera':
      ids={e.camera_id for e in rows}; names={c.id:(c.code,c.name) for c in db.scalars(select(Camera).where(Camera.id.in_(ids)))} if ids else {}; pairs=[names.get(e.camera_id,(str(e.camera_id),'Cámara')) for e in rows]
    elif dimension=='zone':
      ids={e.zone_id for e in rows if e.zone_id}; names={z.id:(z.code,z.name) for z in db.scalars(select(Zone).where(Zone.id.in_(ids)))} if ids else {}; pairs=[names.get(e.zone_id,('SIN_ZONA','Sin zona')) for e in rows]
    else: raise ValueError('dimension inválida')
    counts=defaultdict(int); labels={}
    for k,l in pairs: counts[str(k)]+=1; labels[str(k)]=l
    total=max(len(rows),1)
    return [dict(key=k,label=labels[k],count=n,share=round(100*n/total,2)) for k,n in sorted(counts.items(),key=lambda x:x[1],reverse=True)[:limit]]

def heatmap(db,org_id,start,end,camera_id=None,include_qa=False):
    ef=event_filters(org_id,start,end,include_qa)
    if camera_id: ef.append(SafetyDetectionEvent.camera_id==camera_id)
    events=list(db.scalars(select(SafetyDetectionEvent).where(*ef)))
    counts=defaultdict(int); crit=defaultdict(int)
    for e in events:
      if e.zone_id: counts[e.zone_id]+=1; crit[e.zone_id]+=e.severity=='CRITICA'
    stmt=select(Zone).where(Zone.organization_id==org_id,Zone.active.is_(True))
    if camera_id: stmt=stmt.where(Zone.camera_id==camera_id)
    zones=list(db.scalars(stmt)); cams={c.id:c for c in db.scalars(select(Camera).where(Camera.id.in_([z.camera_id for z in zones])))} if zones else {}; mx=max(counts.values(),default=1)
    return [dict(zone_id=str(z.id),zone_code=z.code,zone_name=z.name,camera_id=str(z.camera_id),camera_code=cams[z.camera_id].code if z.camera_id in cams else '',polygon_points=z.polygon_points,event_count=counts[z.id],critical_count=crit[z.id],intensity=round(counts[z.id]/mx,4)) for z in zones]

def csv_export(db,org_id,start,end,include_qa=False):
    rows=list(db.scalars(select(SafetyDetectionEvent).where(*event_filters(org_id,start,end,include_qa)).order_by(SafetyDetectionEvent.confirmed_at.desc())))
    out=io.StringIO(); w=csv.writer(out); w.writerow(['event_number','confirmed_at','ppe_code','ppe_name','severity','technical_status','operational_status','review_outcome','alert_priority','ack_sla_status','resolve_sla_status','escalation_level','evidence_count','duration_seconds','data_origin','archived_at'])
    for e in rows:w.writerow([e.event_number,e.confirmed_at.isoformat(),e.ppe_code,e.ppe_name,e.severity,e.status,e.operational_status,e.review_outcome,e.alert_priority,e.ack_sla_status,e.resolve_sla_status,e.escalation_level,e.evidence_count,e.duration_seconds,e.data_origin,e.archived_at.isoformat() if e.archived_at else ''])
    return out.getvalue()
