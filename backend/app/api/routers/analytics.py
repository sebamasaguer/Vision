from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.deps import is_superadmin, require_permission
from app.db.session import get_db
from app.models.access import User
from app.models.organization import Organization
from app.models.safety import PilotCleanupRun, SafetyDetectionEvent
from app.models.vision import CameraVisionSetting
from app.schemas.analytics import CleanupStatus, ExecutiveKPI, ExecutiveReport, HeatmapZone, RiskItem, TrendPoint
from app.services.analytics import csv_export, executive_kpis, heatmap, normalize_range, top_risks, trend

router=APIRouter(prefix='/analytics',tags=['Analytics'])

def org_id(db,user,organization_id):
 if not is_superadmin(user):
  if not user.organization_id: raise HTTPException(403,'Usuario sin organización')
  return user.organization_id
 if organization_id:
  if not db.get(Organization,organization_id):raise HTTPException(404,'Organización inexistente')
  return organization_id
 v=db.scalar(select(SafetyDetectionEvent.organization_id).where(SafetyDetectionEvent.analytics_excluded.is_(False)).order_by(SafetyDetectionEvent.confirmed_at.desc()).limit(1))
 if v:return v
 v=db.scalar(select(Organization.id).order_by(Organization.created_at).limit(1))
 if not v:raise HTTPException(404,'No existen organizaciones')
 return v

def rng(date_from,date_to):return normalize_range(date_from,date_to)

@router.get('/executive',response_model=ExecutiveKPI)
def executive(date_from:datetime|None=Query(None),date_to:datetime|None=Query(None),organization_id:uuid.UUID|None=Query(None),include_qa:bool=False,user:User=Depends(require_permission('analytics.read')),db:Session=Depends(get_db)):
 oid=org_id(db,user,organization_id);a,b=rng(date_from,date_to);return ExecutiveKPI(**executive_kpis(db,oid,a,b,include_qa))

@router.get('/trend',response_model=list[TrendPoint])
def trends(date_from:datetime|None=Query(None),date_to:datetime|None=Query(None),organization_id:uuid.UUID|None=Query(None),include_qa:bool=False,user:User=Depends(require_permission('analytics.read')),db:Session=Depends(get_db)):
 oid=org_id(db,user,organization_id);a,b=rng(date_from,date_to);return [TrendPoint(**x) for x in trend(db,oid,a,b,include_qa)]

@router.get('/top-risks',response_model=list[RiskItem])
def risks(dimension:str='ppe',date_from:datetime|None=Query(None),date_to:datetime|None=Query(None),organization_id:uuid.UUID|None=Query(None),include_qa:bool=False,user:User=Depends(require_permission('analytics.read')),db:Session=Depends(get_db)):
 oid=org_id(db,user,organization_id);a,b=rng(date_from,date_to)
 try:return [RiskItem(**x) for x in top_risks(db,oid,a,b,dimension,include_qa)]
 except ValueError as e:raise HTTPException(422,str(e))

@router.get('/heatmap',response_model=list[HeatmapZone])
def heat(camera_id:uuid.UUID|None=Query(None),date_from:datetime|None=Query(None),date_to:datetime|None=Query(None),organization_id:uuid.UUID|None=Query(None),include_qa:bool=False,user:User=Depends(require_permission('analytics.read')),db:Session=Depends(get_db)):
 oid=org_id(db,user,organization_id);a,b=rng(date_from,date_to);return [HeatmapZone(**x) for x in heatmap(db,oid,a,b,camera_id,include_qa)]

@router.get('/report',response_model=ExecutiveReport)
def report(date_from:datetime|None=Query(None),date_to:datetime|None=Query(None),organization_id:uuid.UUID|None=Query(None),include_qa:bool=False,user:User=Depends(require_permission('analytics.read')),db:Session=Depends(get_db)):
 oid=org_id(db,user,organization_id);a,b=rng(date_from,date_to);k=ExecutiveKPI(**executive_kpis(db,oid,a,b,include_qa));ppe=[RiskItem(**x) for x in top_risks(db,oid,a,b,'ppe',include_qa,5)];zones=[RiskItem(**x) for x in top_risks(db,oid,a,b,'zone',include_qa,5)];cams=[RiskItem(**x) for x in top_risks(db,oid,a,b,'camera',include_qa,5)];recs=[]
 if k.ack_sla_met_rate<90:recs.append('Revisar capacidad de reconocimiento de alertas: SLA ACK por debajo de 90%.')
 if k.resolution_sla_met_rate<90:recs.append('Reforzar responsables y tiempos de resolución operativa.')
 if k.false_positive_rate>10:recs.append('Calibrar modelo y reglas: tasa de falsos positivos superior a 10%.')
 if not recs:recs.append('Mantener seguimiento semanal de tendencias, zonas críticas y cumplimiento de SLA.')
 return ExecutiveReport(generated_at=datetime.now(timezone.utc),title='Informe Ejecutivo de Higiene y Seguridad',summary=k,top_ppe=ppe,top_zones=zones,top_cameras=cams,recommendations=recs)

@router.get('/export.csv')
def export_csv(date_from:datetime|None=Query(None),date_to:datetime|None=Query(None),organization_id:uuid.UUID|None=Query(None),include_qa:bool=False,user:User=Depends(require_permission('analytics.export')),db:Session=Depends(get_db)):
 oid=org_id(db,user,organization_id);a,b=rng(date_from,date_to);content=csv_export(db,oid,a,b,include_qa);return Response(content,media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename=hys_vision_analytics.csv'})

@router.get('/cleanup-status',response_model=CleanupStatus)
def cleanup_status(organization_id:uuid.UUID|None=Query(None),user:User=Depends(require_permission('analytics.read')),db:Session=Depends(get_db)):
 oid=org_id(db,user,organization_id);runs=list(db.scalars(select(PilotCleanupRun).where(PilotCleanupRun.organization_id==oid).order_by(PilotCleanupRun.started_at.desc())));active=int(db.scalar(select(func.count()).select_from(SafetyDetectionEvent).where(SafetyDetectionEvent.organization_id==oid,SafetyDetectionEvent.data_origin=='QA_PILOT',SafetyDetectionEvent.archived_at.is_(None))) or 0);comp=int(db.scalar(select(func.count()).select_from(CameraVisionSetting).where(CameraVisionSetting.organization_id==oid,CameraVisionSetting.compliance_enabled.is_(True))) or 0);return CleanupStatus(total_runs=len(runs),last_run_at=runs[0].completed_at if runs else None,archived_events=sum(r.archived_events for r in runs),compliance_enabled_cameras=comp,qa_active_events=active)
