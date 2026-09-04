import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.camera import Camera
from app.models.ml import MLDataset, MLDatasetVersion, MLTrainingRun, MLModelDeployment, MLShadowObservation
from app.models.vision import VisionModelVersion, CameraVisionSetting


def utcnow(): return datetime.now(timezone.utc)


def file_sha256(path: Path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()


def artifact_path(uri: str | None):
    if not uri: return None
    p=Path(uri)
    if not p.is_absolute(): p=Path(settings.hys_model_root)/p
    return p


def model_available(model: VisionModelVersion):
    p=artifact_path(model.artifact_uri)
    if not p or not p.exists(): return False
    if model.artifact_sha256:
        try: return file_sha256(p)==model.artifact_sha256
        except Exception: return False
    return True


def serialize_model(m: VisionModelVersion):
    return {
        'id':str(m.id),'code':m.code,'name':m.name,'provider':m.provider,'backend':m.backend,
        'detector_type':m.detector_type,'version':m.version,'license_name':m.license_name,
        'commercial_use':bool(m.commercial_use),'active':bool(m.active),'stage':m.model_stage,
        'artifact_uri':m.artifact_uri,'artifact_sha256':m.artifact_sha256,'available':model_available(m),
        'framework':m.framework,'input_width':m.input_width,'input_height':m.input_height,
        'class_map':m.class_map or {},'metrics':m.metrics_json or {},'metadata':m.model_metadata or {},
    }


def build_training_command(run: MLTrainingRun, version: MLDatasetVersion):
    data_path=version.storage_path or f'{version.dataset_id}/{version.version}/COCO'
    return (
        'docker compose --profile training run --rm trainer '
        f'python /workspace/train_and_export.py --dataset "/datasets/{data_path}" '
        f'--run-id {run.id} --base {run.base_model} --epochs {run.epochs} '
        f'--img-size {run.image_size} --batch {run.batch_size} --device {run.device}'
    )


def create_deployment(db: Session, organization_id, model: VisionModelVersion, camera_id, mode, actor_id=None):
    if model.detector_type != 'PPE': raise ValueError('Sólo modelos PPE pueden desplegarse aquí')
    if mode not in {'SHADOW','PRODUCTION'}: raise ValueError('mode inválido')
    if mode=='PRODUCTION' and (model.model_metadata or {}).get('production_certified_for_hys') is False:
        raise ValueError('Modelo no certificado para producción HYS; usar SHADOW primero')
    if camera_id:
        cam=db.get(Camera,camera_id)
        if not cam or cam.organization_id!=organization_id: raise ValueError('Cámara fuera de organización')
    existing=list(db.scalars(select(MLModelDeployment).where(
        MLModelDeployment.organization_id==organization_id,
        MLModelDeployment.camera_id==camera_id,
        MLModelDeployment.mode==mode,
        MLModelDeployment.enabled.is_(True),
    )))
    now=utcnow()
    for d in existing:
        d.enabled=False; d.ended_at=now
    dep=MLModelDeployment(organization_id=organization_id,camera_id=camera_id,model_version_id=model.id,mode=mode,enabled=True,started_at=now,created_by_user_id=actor_id)
    db.add(dep); db.flush()
    if mode=='PRODUCTION' and camera_id:
        cfg=db.scalar(select(CameraVisionSetting).where(CameraVisionSetting.camera_id==camera_id))
        if cfg:
            cfg.ppe_model_version_id=model.id
            cfg.ppe_enabled=True
    db.commit(); db.refresh(dep)
    return dep


def shadow_summary(db: Session, organization_id, camera_id=None, deployment_id=None):
    q=select(MLShadowObservation).where(MLShadowObservation.organization_id==organization_id)
    if camera_id: q=q.where(MLShadowObservation.camera_id==camera_id)
    if deployment_id: q=q.where(MLShadowObservation.deployment_id==deployment_id)
    rows=list(db.scalars(q.order_by(MLShadowObservation.observed_at.desc()).limit(5000)))
    by={}
    for x in rows:
        b=by.setdefault(x.ppe_code,{'samples':0,'agreements':0})
        b['samples']+=1; b['agreements']+=int(bool(x.agreement))
    for b in by.values(): b['agreement_ratio']=round(b['agreements']/max(b['samples'],1),4)
    agree=sum(int(x.agreement) for x in rows)
    return {'samples':len(rows),'agreements':agree,'agreement_ratio':round(agree/max(len(rows),1),4),'by_ppe':by}
