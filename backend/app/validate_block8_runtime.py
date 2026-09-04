from sqlalchemy import func, select
from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.safety import PilotCleanupRun, SafetyDetectionEvent
from app.models.vision import CameraVisionSetting

with SessionLocal() as db:
 org=db.scalar(select(Organization).where(Organization.code=='DEMO-HYS'))
 if not org: raise SystemExit('DEMO-HYS no existe')
 runs=int(db.scalar(select(func.count()).select_from(PilotCleanupRun).where(PilotCleanupRun.organization_id==org.id)) or 0)
 active=int(db.scalar(select(func.count()).select_from(SafetyDetectionEvent).where(SafetyDetectionEvent.organization_id==org.id,SafetyDetectionEvent.archived_at.is_(None),SafetyDetectionEvent.operational_status!='RESOLVED')) or 0)
 qa=int(db.scalar(select(func.count()).select_from(SafetyDetectionEvent).where(SafetyDetectionEvent.organization_id==org.id,SafetyDetectionEvent.data_origin=='QA_PILOT',SafetyDetectionEvent.archived_at.is_not(None))) or 0)
 comp=int(db.scalar(select(func.count()).select_from(CameraVisionSetting).where(CameraVisionSetting.organization_id==org.id,CameraVisionSetting.compliance_enabled.is_(True))) or 0)
 print(f'BLOCK8_CLEANUP_OK runs={runs} active_unarchived={active} archived_qa={qa} compliance_enabled={comp}')
 if runs<1 or active!=0 or comp!=0: raise SystemExit(2)
