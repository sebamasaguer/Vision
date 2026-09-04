import uuid
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import time
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import ensure_org_access, get_current_user, is_superadmin, require_permission
from app.core.config import settings
from app.db.session import get_db
from app.models.access import User
from app.models.camera import Camera
from app.models.ml import MLDataset, MLDatasetVersion, MLTrainingRun, MLModelDeployment, MLShadowObservation
from app.models.ml_dataset_visual import MLDatasetFrame, MLGroundTruthAnnotation, MLEvaluationRun
from app.models.vision import VisionModelVersion
from app.schemas.ml import DatasetCreate, DatasetVersionCreate, TrainingRunCreate, ModelRegisterRequest, DeploymentRequest, BootstrapActivateRequest
from app.services.ml_registry import artifact_path, build_training_command, create_deployment, file_sha256, model_available, serialize_model, shadow_summary
from app.services.dataset_visual import CLASSES, evaluate_model, frame_path, freeze_dataset, ingest_jpeg, ingest_video, replace_annotations, serialize_frame, workspace
from app.services.camera_runtime import redis_client, frame_key

router=APIRouter(prefix='/ml',tags=['ML / Model Registry'])


class CameraCaptureRequest(BaseModel):
    count: int = Field(default=1, ge=1, le=30)
    interval_ms: int = Field(default=350, ge=0, le=5000)

class AnnotationItem(BaseModel):
    class_code: str
    x: float
    y: float
    width: float
    height: float

class AnnotationReplaceRequest(BaseModel):
    annotations: list[AnnotationItem]
    verified: bool = False

class CurationRequest(BaseModel):
    status: str = Field(pattern='^(PENDING|ACCEPTED|REJECTED)$')

class FreezeVisualRequest(BaseModel):
    version: str = Field(min_length=1,max_length=50)
    classes: list[str] = ['HELMET','VEST','SAFETY_SHOES']
    notes: str | None = None

class EvaluationRequest(BaseModel):
    dataset_id: uuid.UUID
    model_version_id: uuid.UUID
    camera_id: uuid.UUID | None = None
    iou_threshold: float = Field(default=.5, ge=.1, le=.95)
    confidence_threshold: float = Field(default=.35, ge=.01, le=.99)

class PromotionRequest(BaseModel):
    camera_id: uuid.UUID
    confirm: bool = False
    min_precision: float = Field(default=.80, ge=0, le=1)
    min_recall: float = Field(default=.80, ge=0, le=1)
    min_shadow_samples: int = Field(default=100, ge=1)
    min_shadow_agreement: float = Field(default=.80, ge=0, le=1)


def org_for(user:User, requested=None):
    if requested:
        ensure_org_access(user,requested); return requested
    if user.organization_id: return user.organization_id
    if is_superadmin(user): return None
    raise HTTPException(400,'Organización requerida')


@router.get('/overview')
def overview(organization_id:uuid.UUID|None=None,user:User=Depends(require_permission('ml.read')),db:Session=Depends(get_db)):
    oid=org_for(user,organization_id)
    mq=select(VisionModelVersion).where(VisionModelVersion.detector_type=='PPE').order_by(VisionModelVersion.created_at.desc())
    models=list(db.scalars(mq))
    datasets=[]
    if oid:
        datasets=list(db.scalars(select(MLDataset).where(MLDataset.organization_id==oid).order_by(MLDataset.created_at.desc())))
    runs=[] if not oid else list(db.scalars(select(MLTrainingRun).where(MLTrainingRun.organization_id==oid).order_by(MLTrainingRun.created_at.desc()).limit(30)))
    deps=[] if not oid else list(db.scalars(select(MLModelDeployment).where(MLModelDeployment.organization_id==oid,MLModelDeployment.enabled.is_(True)).order_by(MLModelDeployment.started_at.desc())))
    return {
        'models':[serialize_model(m) for m in models],
        'datasets':[{'id':str(d.id),'code':d.code,'name':d.name,'license_name':d.license_name,'source_url':d.source_url,'active':d.active,'created_at':d.created_at} for d in datasets],
        'training_runs':[{'id':str(r.id),'status':r.status,'base_model':r.base_model,'epochs':r.epochs,'image_size':r.image_size,'device':r.device,'metrics':r.metrics or {},'command_line':r.command_line,'created_at':r.created_at} for r in runs],
        'deployments':[{'id':str(d.id),'model_version_id':str(d.model_version_id),'camera_id':str(d.camera_id) if d.camera_id else None,'mode':d.mode,'enabled':d.enabled,'started_at':d.started_at} for d in deps],
        'shadow': shadow_summary(db,oid) if oid else {'samples':0,'agreements':0,'agreement_ratio':0.0,'by_ppe':{}},
        'policy':{'ultralytics_used':False,'training_stack':'YOLOX 0.3.0 / Apache-2.0','runtime':'ONNX Runtime CPU','bootstrap':'Intel Worker Safety / MIT'},
    }


@router.post('/datasets')
def create_dataset(body:DatasetCreate,user:User=Depends(require_permission('ml.manage')),db:Session=Depends(get_db)):
    oid=org_for(user,body.organization_id)
    if not oid: raise HTTPException(400,'organization_id requerido para SUPERADMIN')
    if db.scalar(select(MLDataset).where(MLDataset.organization_id==oid,MLDataset.code==body.code)):
        raise HTTPException(409,'Código de dataset ya existe')
    d=MLDataset(organization_id=oid,code=body.code,name=body.name,description=body.description,license_name=body.license_name,source_url=body.source_url,created_by_user_id=user.id)
    db.add(d); db.commit(); db.refresh(d)
    return {'id':str(d.id),'code':d.code,'name':d.name}


@router.post('/datasets/{dataset_id}/versions')
def create_version(dataset_id:uuid.UUID,body:DatasetVersionCreate,user:User=Depends(require_permission('ml.manage')),db:Session=Depends(get_db)):
    d=db.get(MLDataset,dataset_id)
    if not d: raise HTTPException(404,'Dataset inexistente')
    ensure_org_access(user,d.organization_id)
    if db.scalar(select(MLDatasetVersion).where(MLDatasetVersion.dataset_id==dataset_id,MLDatasetVersion.version==body.version)):
        raise HTTPException(409,'Versión ya existe')
    v=MLDatasetVersion(dataset_id=dataset_id,version=body.version,status='FROZEN' if body.freeze else 'DRAFT',classes=body.classes,image_count=body.image_count,annotation_count=body.annotation_count,train_count=body.train_count,val_count=body.val_count,test_count=body.test_count,manifest_sha256=body.manifest_sha256,storage_path=body.storage_path,notes=body.notes,frozen_at=datetime.now(timezone.utc) if body.freeze else None)
    db.add(v);db.commit();db.refresh(v)
    return {'id':str(v.id),'version':v.version,'status':v.status}


@router.post('/training-runs')
def create_training(body:TrainingRunCreate,user:User=Depends(require_permission('ml.train')),db:Session=Depends(get_db)):
    v=db.get(MLDatasetVersion,body.dataset_version_id)
    if not v: raise HTTPException(404,'Dataset version inexistente')
    d=db.get(MLDataset,v.dataset_id); ensure_org_access(user,d.organization_id)
    if v.status!='FROZEN': raise HTTPException(409,'Dataset version debe estar FROZEN')
    r=MLTrainingRun(organization_id=d.organization_id,dataset_version_id=v.id,base_model=body.base_model,epochs=body.epochs,image_size=body.image_size,batch_size=body.batch_size,device=body.device,created_by_user_id=user.id)
    db.add(r);db.flush();r.command_line=build_training_command(r,v);db.commit();db.refresh(r)
    return {'id':str(r.id),'status':r.status,'command_line':r.command_line}


@router.post('/models/register')
def register_model(body:ModelRegisterRequest,user:User=Depends(require_permission('ml.manage')),db:Session=Depends(get_db)):
    oid=org_for(user,body.organization_id)
    if not oid: raise HTTPException(400,'organization_id requerido')
    path=artifact_path(body.artifact_uri)
    if not path or not path.exists(): raise HTTPException(400,f'Artifact no existe: {path}')
    actual=file_sha256(path)
    if actual.lower()!=body.artifact_sha256.lower(): raise HTTPException(400,'SHA-256 del artifact no coincide')
    if db.scalar(select(VisionModelVersion).where(VisionModelVersion.code==body.code)):
        raise HTTPException(409,'Código de modelo ya registrado')
    m=VisionModelVersion(code=body.code,name=body.name,provider='HYS Vision IA',backend=body.backend,detector_type='PPE',version=body.version,license_name=body.license_name,license_url=body.license_url,commercial_use=True,active=True,is_default=False,notes='Modelo HYS registrado en Bloque 9.',model_metadata={'class_map':body.class_map,'input_width':body.input_width,'input_height':body.input_height,'decode_grid':True,'dataset_version_id':str(body.dataset_version_id) if body.dataset_version_id else None},artifact_uri=body.artifact_uri,artifact_sha256=actual,framework='YOLOX/ONNX',model_stage='REGISTERED',input_width=body.input_width,input_height=body.input_height,class_map=body.class_map,metrics_json=body.metrics or {})
    db.add(m);db.commit();db.refresh(m)
    return serialize_model(m)


@router.post('/deployments')
def deploy(body:DeploymentRequest,user:User=Depends(require_permission('ml.manage')),db:Session=Depends(get_db)):
    model=db.get(VisionModelVersion,body.model_version_id)
    if not model: raise HTTPException(404,'Modelo inexistente')
    if not model_available(model): raise HTTPException(409,'Artifact del modelo no disponible o SHA inválido')
    if body.camera_id:
        cam=db.get(Camera,body.camera_id)
        if not cam: raise HTTPException(404,'Cámara inexistente')
        ensure_org_access(user,cam.organization_id); oid=cam.organization_id
    else:
        oid=user.organization_id
        if not oid: raise HTTPException(400,'camera_id requerido para SUPERADMIN')
    try: dep=create_deployment(db,oid,model,body.camera_id,body.mode,user.id)
    except ValueError as e: raise HTTPException(400,str(e))
    if body.mode=='PRODUCTION':
        model.model_stage='PRODUCTION'; model.approved_at=datetime.now(timezone.utc); model.approved_by_user_id=user.id; db.commit()
    elif model.model_stage=='REGISTERED':
        model.model_stage='SHADOW'; db.commit()
    return {'id':str(dep.id),'mode':dep.mode,'camera_id':str(dep.camera_id) if dep.camera_id else None,'model_code':model.code}


@router.get('/shadow/summary')
def get_shadow(camera_id:uuid.UUID|None=None,organization_id:uuid.UUID|None=None,user:User=Depends(require_permission('ml.read')),db:Session=Depends(get_db)):
    oid=org_for(user,organization_id)
    if not oid and camera_id:
        cam=db.get(Camera,camera_id); oid=cam.organization_id if cam else None
    if not oid: raise HTTPException(400,'Organización requerida')
    return shadow_summary(db,oid,camera_id=camera_id)


@router.post('/bootstrap/intel/activate')
def activate_intel(body:BootstrapActivateRequest,user:User=Depends(require_permission('ml.manage')),db:Session=Depends(get_db)):
    m=db.scalar(select(VisionModelVersion).where(VisionModelVersion.code=='INTEL_WORKER_SAFETY_BOOTSTRAP'))
    if not m: raise HTTPException(404,'Modelo bootstrap no seed')
    path=artifact_path(body.artifact_uri)
    if not path or not path.exists(): raise HTTPException(400,f'Artifact no existe: {path}')
    m.artifact_uri=body.artifact_uri
    m.artifact_sha256=body.artifact_sha256 or file_sha256(path)
    m.active=True; m.model_stage='REGISTERED'
    db.commit();db.refresh(m)
    return serialize_model(m)


# ---------------------------------------------------------------------------
# Bloque 10 - Dataset Manager Visual / Ground Truth / Evaluación
# ---------------------------------------------------------------------------

def _dataset_for(db: Session, dataset_id: uuid.UUID, user: User):
    d=db.get(MLDataset,dataset_id)
    if not d: raise HTTPException(404,'Dataset inexistente')
    ensure_org_access(user,d.organization_id)
    return d

def _frame_for(db: Session, frame_id: uuid.UUID, user: User):
    f=db.get(MLDatasetFrame,frame_id)
    if not f: raise HTTPException(404,'Frame inexistente')
    ensure_org_access(user,f.organization_id)
    return f

@router.get('/datasets/{dataset_id}/workspace')
def dataset_workspace(dataset_id:uuid.UUID,user:User=Depends(require_permission('ml.read')),db:Session=Depends(get_db)):
    return workspace(db,_dataset_for(db,dataset_id,user))

@router.post('/datasets/{dataset_id}/capture/camera/{camera_id}')
def capture_camera(dataset_id:uuid.UUID,camera_id:uuid.UUID,body:CameraCaptureRequest,user:User=Depends(require_permission('ml.manage')),db:Session=Depends(get_db)):
    d=_dataset_for(db,dataset_id,user);cam=db.get(Camera,camera_id)
    if not cam: raise HTTPException(404,'Cámara inexistente')
    ensure_org_access(user,cam.organization_id)
    if cam.organization_id!=d.organization_id: raise HTTPException(400,'Cámara y dataset pertenecen a organizaciones distintas')
    r=redis_client();saved=[]
    for i in range(body.count):
        data=r.get(frame_key(cam.id))
        if not data: raise HTTPException(409,'La cámara todavía no tiene frame disponible')
        try: f=ingest_jpeg(db,d,bytes(data),camera_id=cam.id,source_type='CAMERA',source_ref=f'{cam.code}:live',frame_index=i,actor_id=user.id);saved.append(f)
        except ValueError as e: raise HTTPException(400,str(e))
        db.commit()
        if i+1<body.count and body.interval_ms: time.sleep(body.interval_ms/1000)
    return {'captured':len(saved),'frames':[serialize_frame(db,x) for x in saved]}

@router.post('/datasets/{dataset_id}/capture/video')
def capture_video(dataset_id:uuid.UUID,file:UploadFile=File(...),every_seconds:float=Form(1.0),max_frames:int=Form(120),user:User=Depends(require_permission('ml.manage')),db:Session=Depends(get_db)):
    d=_dataset_for(db,dataset_id,user)
    if max_frames<1 or max_frames>500: raise HTTPException(422,'max_frames debe estar entre 1 y 500')
    suffix=Path(file.filename or 'video.mp4').suffix or '.mp4'
    with tempfile.NamedTemporaryFile(delete=False,suffix=suffix) as tmp:
        while True:
            chunk=file.file.read(1024*1024)
            if not chunk: break
            tmp.write(chunk)
        tmp_path=Path(tmp.name)
    try:
        rows=ingest_video(db,d,tmp_path,every_seconds=max(.1,float(every_seconds)),max_frames=max_frames,actor_id=user.id,source_ref=file.filename or 'upload')
        db.commit();return {'captured':len(rows),'frames':[serialize_frame(db,x) for x in rows[:50]]}
    except ValueError as e: db.rollback();raise HTTPException(400,str(e))
    finally:
        tmp_path.unlink(missing_ok=True)

@router.get('/frames/{frame_id}/image')
def frame_image(frame_id:uuid.UUID,user:User=Depends(require_permission('ml.read')),db:Session=Depends(get_db)):
    f=_frame_for(db,frame_id,user);p=frame_path(f)
    if not p.exists(): raise HTTPException(404,'Archivo de frame ausente')
    return FileResponse(p,media_type='image/jpeg',headers={'Cache-Control':'no-store'})

@router.put('/frames/{frame_id}/annotations')
def save_annotations(frame_id:uuid.UUID,body:AnnotationReplaceRequest,user:User=Depends(require_permission('ml.manage')),db:Session=Depends(get_db)):
    f=_frame_for(db,frame_id,user)
    try: replace_annotations(db,f,[x.model_dump() for x in body.annotations],body.verified,user.id)
    except ValueError as e: raise HTTPException(422,str(e))
    db.commit();db.refresh(f);return serialize_frame(db,f)

@router.patch('/frames/{frame_id}/curation')
def curate_frame(frame_id:uuid.UUID,body:CurationRequest,user:User=Depends(require_permission('ml.manage')),db:Session=Depends(get_db)):
    f=_frame_for(db,frame_id,user)
    if f.curation_status=='DUPLICATE' and body.status=='ACCEPTED': raise HTTPException(409,'Frame marcado duplicado; no se acepta sin recaptura')
    f.curation_status=body.status;f.updated_at=datetime.now(timezone.utc);db.commit();db.refresh(f);return serialize_frame(db,f)

@router.post('/datasets/{dataset_id}/freeze-visual')
def freeze_visual(dataset_id:uuid.UUID,body:FreezeVisualRequest,user:User=Depends(require_permission('ml.manage')),db:Session=Depends(get_db)):
    d=_dataset_for(db,dataset_id,user)
    try: v,manifest=freeze_dataset(db,d,body.version,body.classes,body.notes)
    except ValueError as e: raise HTTPException(409,str(e))
    db.commit();return {'id':str(v.id),'version':v.version,'status':v.status,'manifest':manifest}

@router.get('/evaluations')
def list_evaluations(organization_id:uuid.UUID|None=None,user:User=Depends(require_permission('ml.read')),db:Session=Depends(get_db)):
    oid=org_for(user,organization_id)
    if not oid: return []
    rows=list(db.scalars(select(MLEvaluationRun).where(MLEvaluationRun.organization_id==oid).order_by(MLEvaluationRun.created_at.desc()).limit(50)))
    return [{'id':str(x.id),'dataset_id':str(x.dataset_id),'model_version_id':str(x.model_version_id),'camera_id':str(x.camera_id) if x.camera_id else None,'status':x.status,'sample_count':x.sample_count,'metrics':x.metrics or {},'error_message':x.error_message,'created_at':x.created_at} for x in rows]

@router.post('/evaluations')
def run_evaluation(body:EvaluationRequest,user:User=Depends(require_permission('ml.manage')),db:Session=Depends(get_db)):
    d=_dataset_for(db,body.dataset_id,user);m=db.get(VisionModelVersion,body.model_version_id)
    if not m or m.detector_type!='PPE': raise HTTPException(404,'Modelo PPE inexistente')
    if not model_available(m): raise HTTPException(409,'Artifact no disponible')
    if body.camera_id:
        cam=db.get(Camera,body.camera_id)
        if not cam or cam.organization_id!=d.organization_id: raise HTTPException(400,'Cámara inválida')
    try: run=evaluate_model(db,d,m,user.id,body.camera_id,body.iou_threshold,body.confidence_threshold);db.commit()
    except Exception as e: db.commit();raise HTTPException(500,f'Evaluación falló: {e}')
    return {'id':str(run.id),'status':run.status,'sample_count':run.sample_count,'metrics':run.metrics}

@router.get('/shadow/by-camera')
def shadow_by_camera(organization_id:uuid.UUID|None=None,user:User=Depends(require_permission('ml.read')),db:Session=Depends(get_db)):
    oid=org_for(user,organization_id)
    if not oid: return []
    cams=list(db.scalars(select(Camera).where(Camera.organization_id==oid).order_by(Camera.name)))
    out=[]
    for cam in cams:
        s=shadow_summary(db,oid,camera_id=cam.id)
        out.append({'camera_id':str(cam.id),'camera_code':cam.code,'camera_name':cam.name,**s})
    return out

@router.post('/models/{model_id}/promote-controlled')
def promote_controlled(model_id:uuid.UUID,body:PromotionRequest,user:User=Depends(require_permission('ml.manage')),db:Session=Depends(get_db)):
    if not body.confirm: raise HTTPException(409,'Promoción requiere confirm=true explícito')
    model=db.get(VisionModelVersion,model_id);cam=db.get(Camera,body.camera_id)
    if not model or model.detector_type!='PPE': raise HTTPException(404,'Modelo PPE inexistente')
    if not cam: raise HTTPException(404,'Cámara inexistente')
    ensure_org_access(user,cam.organization_id)
    if (model.model_metadata or {}).get('production_certified_for_hys') is False: raise HTTPException(409,'Bootstrap/no certificado: no puede promoverse a producción')
    ev=db.scalar(select(MLEvaluationRun).where(MLEvaluationRun.organization_id==cam.organization_id,MLEvaluationRun.model_version_id==model.id,MLEvaluationRun.status=='COMPLETED').order_by(MLEvaluationRun.completed_at.desc()))
    if not ev: raise HTTPException(409,'Se requiere evaluación Ground Truth completada')
    metrics=ev.metrics or {}
    if float(metrics.get('precision',0))<body.min_precision or float(metrics.get('recall',0))<body.min_recall: raise HTTPException(409,'Ground Truth no alcanza precision/recall requeridos')
    sh=shadow_summary(db,cam.organization_id,camera_id=cam.id)
    if sh['samples']<body.min_shadow_samples or sh['agreement_ratio']<body.min_shadow_agreement: raise HTTPException(409,'SHADOW no alcanza muestras/acuerdo requeridos')
    try: dep=create_deployment(db,cam.organization_id,model,cam.id,'PRODUCTION',user.id)
    except ValueError as e: raise HTTPException(409,str(e))
    model.model_stage='PRODUCTION';model.approved_at=datetime.now(timezone.utc);model.approved_by_user_id=user.id;db.commit()
    return {'status':'PROMOTED','deployment_id':str(dep.id),'camera_id':str(cam.id),'model':model.code,'ground_truth':metrics,'shadow':sh}
