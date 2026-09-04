from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.camera import Camera
from app.models.organization import Organization
from app.models.vision import CameraVisionSetting, VisionModelVersion
from app.models.ml import MLModelDeployment
from app.services.ml_registry import create_deployment


def main():
    with SessionLocal() as db:
        org=db.scalar(select(Organization).where(Organization.code=='DEMO-HYS'))
        if not org:
            print('BLOCK10_DEMO_SETUP_SKIP reason=DEMO-HYS-ausente');return
        cam=db.scalar(select(Camera).where(Camera.organization_id==org.id,Camera.code=='DEMO01'))
        if not cam:
            print('BLOCK10_DEMO_SETUP_SKIP reason=DEMO01-ausente');return
        cfg=db.scalar(select(CameraVisionSetting).where(CameraVisionSetting.camera_id==cam.id))
        if cfg:
            cfg.enabled=True;cfg.ppe_enabled=True;cfg.compliance_enabled=False
        cam.ai_enabled=True;cam.active=True
        intel=db.scalar(select(VisionModelVersion).where(VisionModelVersion.code=='INTEL_WORKER_SAFETY_BOOTSTRAP'))
        dep=None
        if intel and intel.active:
            dep=db.scalar(select(MLModelDeployment).where(MLModelDeployment.organization_id==org.id,MLModelDeployment.camera_id==cam.id,MLModelDeployment.mode=='SHADOW',MLModelDeployment.enabled.is_(True)))
            if not dep or dep.model_version_id!=intel.id:
                dep=create_deployment(db,org.id,intel,cam.id,'SHADOW',None)
        db.commit()
        print(f'BLOCK10_DEMO_SETUP_OK camera={cam.code} ai={cam.ai_enabled} ppe={bool(cfg and cfg.ppe_enabled)} compliance={bool(cfg and cfg.compliance_enabled)} shadow={str(dep.id) if dep else "none"}')

if __name__=='__main__': main()
