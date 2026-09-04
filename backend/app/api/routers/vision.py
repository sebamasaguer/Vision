import json, uuid
from datetime import datetime, timezone
import cv2, numpy as np
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import ensure_org_access, is_superadmin, require_permission
from app.db.session import get_db
from app.models.access import User
from app.models.camera import Camera
from app.models.vision import CameraVisionSetting, VisionModelVersion
from app.models.safety import SafetyDetectionEvent
from app.schemas.vision import VisionSettingsUpdate, VisionWorkerStatus
from app.services.audit import add_audit
from app.services.camera_runtime import redis_client, frame_key
from app.services.vision_runtime import VISION_HEARTBEAT, result_key, overlay_key
router=APIRouter(prefix='/vision',tags=['Visión artificial'])

def _cfg(db,camera_id,user):
    cam=db.get(Camera,camera_id)
    if not cam: raise HTTPException(404,'Cámara inexistente')
    ensure_org_access(user,cam.organization_id)
    cfg=db.scalar(select(CameraVisionSetting).where(CameraVisionSetting.camera_id==cam.id))
    if not cfg: raise HTTPException(409,'Configuración de visión ausente; ejecute bootstrap')
    model=db.get(VisionModelVersion,cfg.model_version_id)
    ppe_model=db.get(VisionModelVersion,cfg.ppe_model_version_id) if cfg.ppe_model_version_id else None
    return cam,cfg,model,ppe_model

def _model_payload(model):
    if not model: return None
    return {'id':str(model.id),'code':model.code,'name':model.name,'provider':model.provider,'backend':model.backend,'version':model.version,'license_name':model.license_name,'license_url':model.license_url,'commercial_use':model.commercial_use,'metadata':model.model_metadata}

def _serialize(cam,cfg,model,ppe_model=None):
    return {
        'camera_id':str(cam.id),'camera_code':cam.code,'camera_name':cam.name,'camera_status':cam.status,
        'enabled':cfg.enabled,'inference_fps':cfg.inference_fps,'min_confidence':cfg.min_confidence,
        'nms_iou_threshold':cfg.nms_iou_threshold,'tracker_iou_threshold':cfg.tracker_iou_threshold,
        'tracker_max_missed_frames':cfg.tracker_max_missed_frames,'tracker_min_hits_to_confirm':cfg.tracker_min_hits_to_confirm,
        'min_box_area_ratio':cfg.min_box_area_ratio,'max_box_area_ratio':cfg.max_box_area_ratio,'min_height_ratio':cfg.min_height_ratio,
        'min_aspect_ratio':cfg.min_aspect_ratio,'max_aspect_ratio':cfg.max_aspect_ratio,'top_band_reject_y_ratio':cfg.top_band_reject_y_ratio,
        'top_band_reject_bottom_ratio':cfg.top_band_reject_bottom_ratio,
        'ppe_enabled':cfg.ppe_enabled,'ppe_min_visibility_ratio':cfg.ppe_min_visibility_ratio,'ppe_uncertainty_margin':cfg.ppe_uncertainty_margin,
        'compliance_enabled':cfg.compliance_enabled,'compliance_window_seconds':cfg.compliance_window_seconds,
        'compliance_min_persistence_seconds':cfg.compliance_min_persistence_seconds,'compliance_min_consensus_ratio':cfg.compliance_min_consensus_ratio,
        'compliance_min_missing_observations':cfg.compliance_min_missing_observations,'compliance_cooldown_seconds':cfg.compliance_cooldown_seconds,
        'compliance_clear_grace_seconds':cfg.compliance_clear_grace_seconds,'compliance_track_absence_close_seconds':cfg.compliance_track_absence_close_seconds,
        'model':_model_payload(model),'ppe_model':_model_payload(ppe_model),
    }



@router.get('/worker',response_model=VisionWorkerStatus)
def worker(user:User=Depends(require_permission('vision.read'))):
    try: raw=redis_client().get(VISION_HEARTBEAT)
    except Exception: return VisionWorkerStatus(status='offline')
    if not raw:return VisionWorkerStatus(status='offline')
    try:
        d=json.loads(raw.decode()); age=(datetime.now(timezone.utc)-datetime.fromisoformat(d['at'])).total_seconds(); return VisionWorkerStatus(status='online' if age<=20 else 'degraded',heartbeat_age_seconds=round(age,2),backend=d.get('backend'))
    except Exception:return VisionWorkerStatus(status='degraded')

@router.get('/cameras')
def cameras(user:User=Depends(require_permission('vision.read')),db:Session=Depends(get_db)):
    stmt=select(Camera,CameraVisionSetting,VisionModelVersion).join(CameraVisionSetting,CameraVisionSetting.camera_id==Camera.id).join(VisionModelVersion,VisionModelVersion.id==CameraVisionSetting.model_version_id).order_by(Camera.name)
    if not is_superadmin(user): stmt=stmt.where(Camera.organization_id==user.organization_id)
    out=[]
    for cam,cfg,model in db.execute(stmt).all():
        ppe_model=db.get(VisionModelVersion,cfg.ppe_model_version_id) if cfg.ppe_model_version_id else None
        out.append(_serialize(cam,cfg,model,ppe_model))
    return out

@router.get('/cameras/{camera_id}/settings')
def settings(camera_id:uuid.UUID,user:User=Depends(require_permission('vision.read')),db:Session=Depends(get_db)):
    return _serialize(*_cfg(db,camera_id,user))

@router.patch('/cameras/{camera_id}/settings')
def update_settings(camera_id:uuid.UUID,payload:VisionSettingsUpdate,request:Request,user:User=Depends(require_permission('vision.manage')),db:Session=Depends(get_db)):
    cam,cfg,model,ppe_model=_cfg(db,camera_id,user); before={k:getattr(cfg,k) for k in ['enabled','inference_fps','min_confidence','nms_iou_threshold','tracker_iou_threshold','tracker_max_missed_frames','tracker_min_hits_to_confirm','min_box_area_ratio','max_box_area_ratio','min_height_ratio','min_aspect_ratio','max_aspect_ratio','top_band_reject_y_ratio','top_band_reject_bottom_ratio','ppe_enabled','ppe_min_visibility_ratio','ppe_uncertainty_margin','compliance_enabled','compliance_window_seconds','compliance_min_persistence_seconds','compliance_min_consensus_ratio','compliance_min_missing_observations','compliance_cooldown_seconds','compliance_clear_grace_seconds','compliance_track_absence_close_seconds']}
    changes = payload.model_dump(exclude_unset=True)
    for k,v in changes.items(): setattr(cfg,k,v)
    cfg.updated_at=datetime.now(timezone.utc); cam.ai_enabled=cfg.enabled
    # Desactivar PERSON/PPE/cumplimiento finaliza eventos preventivos abiertos para evitar estados huérfanos.
    if changes.get('compliance_enabled') is False or changes.get('ppe_enabled') is False or changes.get('enabled') is False:
        now=datetime.now(timezone.utc)
        for ev in db.scalars(select(SafetyDetectionEvent).where(SafetyDetectionEvent.camera_id==cam.id,SafetyDetectionEvent.status=='OPEN')):
            ev.status='CLOSED';ev.ended_at=now;ev.last_seen_at=now;ev.duration_seconds=max(0.0,(now-ev.first_observed_at).total_seconds());ev.close_reason='ENGINE_DISABLED';ev.updated_at=now
    add_audit(db,user,'UPDATE','camera_vision_setting',str(cfg.id),before=before,after=payload.model_dump(exclude_unset=True),request=request,organization_id=cam.organization_id); db.commit()
    return _serialize(cam,cfg,model,ppe_model)

@router.get('/cameras/{camera_id}/runtime')
def runtime(camera_id:uuid.UUID,user:User=Depends(require_permission('vision.read')),db:Session=Depends(get_db)):
    _cfg(db,camera_id,user)
    try: raw=redis_client().get(result_key(camera_id))
    except Exception: raw=None
    return json.loads(raw.decode()) if raw else {'camera_id':str(camera_id),'persons':0,'tracks':[],'status':'WAITING'}

@router.get('/cameras/{camera_id}/overlay.jpg')
def overlay(camera_id:uuid.UUID,user:User=Depends(require_permission('vision.read')),db:Session=Depends(get_db)):
    _cfg(db,camera_id,user); redis=redis_client(); data=redis.get(overlay_key(camera_id)) or redis.get(frame_key(camera_id))
    if not data: raise HTTPException(404,'Frame no disponible')
    return Response(content=data,media_type='image/jpeg',headers={'Cache-Control':'no-store'})
