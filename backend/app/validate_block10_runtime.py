from pathlib import Path
from sqlalchemy import inspect, select
from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.models.camera import Camera
from app.models.organization import Organization
from app.models.vision import CameraVisionSetting, VisionModelVersion
from app.models.ml import MLDataset, MLModelDeployment


def main():
    names=set(inspect(engine).get_table_names())
    required={'ml_dataset_frames','ml_ground_truth_annotations','ml_evaluation_runs'}
    missing=required-names
    if missing: raise SystemExit(f'BLOCK10_SCHEMA_FAIL missing={sorted(missing)}')
    print('BLOCK10_SCHEMA_OK '+','.join(sorted(required)))
    with SessionLocal() as db:
        org=db.scalar(select(Organization).where(Organization.code=='DEMO-HYS'))
        if not org: raise SystemExit('BLOCK10_DEMO_FAIL org')
        ds=db.scalar(select(MLDataset).where(MLDataset.organization_id==org.id,MLDataset.code=='HYS-PPE-REAL'))
        if not ds: raise SystemExit('BLOCK10_DATASET_FAIL')
        cam=db.scalar(select(Camera).where(Camera.organization_id==org.id,Camera.code=='DEMO01'))
        if not cam: raise SystemExit('BLOCK10_DEMO_FAIL camera')
        cfg=db.scalar(select(CameraVisionSetting).where(CameraVisionSetting.camera_id==cam.id))
        if not cfg or not cfg.enabled or not cfg.ppe_enabled or cfg.compliance_enabled:
            raise SystemExit(f'BLOCK10_DEMO_FAIL vision enabled={getattr(cfg,"enabled",None)} ppe={getattr(cfg,"ppe_enabled",None)} compliance={getattr(cfg,"compliance_enabled",None)}')
        intel=db.scalar(select(VisionModelVersion).where(VisionModelVersion.code=='INTEL_WORKER_SAFETY_BOOTSTRAP'))
        dep=db.scalar(select(MLModelDeployment).where(MLModelDeployment.organization_id==org.id,MLModelDeployment.camera_id==cam.id,MLModelDeployment.mode=='SHADOW',MLModelDeployment.enabled.is_(True)))
        if not intel or not dep or dep.model_version_id!=intel.id: raise SystemExit('BLOCK10_SHADOW_FAIL')
        print(f'BLOCK10_DATASET_OK id={ds.id} code={ds.code}')
        print(f'BLOCK10_DEMO_OK camera={cam.code} ai={cam.ai_enabled} ppe={cfg.ppe_enabled} compliance={cfg.compliance_enabled} shadow={dep.id}')
    demo=Path(settings.demo_video_path)
    if not demo.exists(): raise SystemExit(f'BLOCK10_VIDEO_FAIL path={demo}')
    print(f'BLOCK10_VIDEO_OK path={demo} size={demo.stat().st_size}')

if __name__=='__main__': main()
