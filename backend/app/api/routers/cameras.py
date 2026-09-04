import asyncio
import json
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import ensure_org_access, is_superadmin, require_permission
from app.core.config import settings
from app.db.session import get_db
from app.models.access import User
from app.models.camera import Camera
from app.models.organization import Sector
from app.models.vision import CameraVisionSetting, VisionModelVersion
from app.schemas.camera import CameraCreate, CameraOut, CameraSummary, CameraUpdate, CameraWorkerStatus
from app.services.audit import add_audit
from app.services.camera_crypto import decrypt_secret, encrypt_secret, mask_rtsp_url
from app.services.camera_runtime import WORKER_HEARTBEAT, frame_key, redis_client

router = APIRouter(prefix="/cameras", tags=["Cámaras"])


def _serialize(cam: Camera) -> CameraOut:
    try:
        masked = mask_rtsp_url(decrypt_secret(cam.source_url_encrypted)) if cam.source_type == "RTSP" else None
    except Exception:
        masked = "rtsp://***"
    return CameraOut(
        **{c.name: getattr(cam, c.name) for c in cam.__table__.columns if c.name not in {"source_url_encrypted", "username_encrypted", "password_encrypted"}},
        rtsp_url_masked=masked,
        credentials_configured=bool(cam.username_encrypted or cam.password_encrypted),
    )


def _get_camera(db: Session, camera_id: uuid.UUID, user: User) -> Camera:
    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Cámara inexistente")
    ensure_org_access(user, cam.organization_id)
    return cam


@router.get("", response_model=list[CameraOut])
def list_cameras(sector_id: uuid.UUID | None = None, user: User = Depends(require_permission("camera.read")), db: Session = Depends(get_db)):
    stmt = select(Camera).order_by(Camera.name)
    if not is_superadmin(user):
        stmt = stmt.where(Camera.organization_id == user.organization_id)
    if sector_id:
        stmt = stmt.where(Camera.sector_id == sector_id)
    return [_serialize(x) for x in db.scalars(stmt)]


@router.get("/summary", response_model=CameraSummary)
def camera_summary(user: User = Depends(require_permission("camera.read")), db: Session = Depends(get_db)):
    stmt = select(Camera)
    if not is_superadmin(user):
        stmt = stmt.where(Camera.organization_id == user.organization_id)
    cams = list(db.scalars(stmt))
    return CameraSummary(
        total=len(cams),
        online=sum(x.status == "ONLINE" for x in cams),
        offline=sum(x.status == "OFFLINE" for x in cams),
        degraded=sum(x.status == "DEGRADADA" for x in cams),
        no_video=sum(x.status == "SIN_VIDEO" for x in cams),
        auth_error=sum(x.status == "ERROR_AUTENTICACION" for x in cams),
        demo=sum(x.source_type == "DEMO_FILE" for x in cams),
    )


@router.get("/worker", response_model=CameraWorkerStatus)
def worker_status(user: User = Depends(require_permission("camera.read"))):
    raw = redis_client().get(WORKER_HEARTBEAT)
    if not raw:
        return CameraWorkerStatus(status="offline", heartbeat_age_seconds=None)
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(text)).total_seconds()
    except Exception:
        return CameraWorkerStatus(status="degraded", heartbeat_age_seconds=None)
    return CameraWorkerStatus(status="online" if age <= 15 else "degraded", heartbeat_age_seconds=round(age, 2))


@router.get("/{camera_id}", response_model=CameraOut)
def get_camera(camera_id: uuid.UUID, user: User = Depends(require_permission("camera.read")), db: Session = Depends(get_db)):
    return _serialize(_get_camera(db, camera_id, user))


@router.post("", response_model=CameraOut, status_code=status.HTTP_201_CREATED)
def create_camera(payload: CameraCreate, request: Request, user: User = Depends(require_permission("camera.manage")), db: Session = Depends(get_db)):
    sector = db.get(Sector, payload.sector_id)
    if not sector:
        raise HTTPException(404, "Sector inexistente")
    ensure_org_access(user, sector.organization_id)
    item = Camera(
        organization_id=sector.organization_id, site_id=sector.site_id, plant_id=sector.plant_id, sector_id=sector.id,
        code=payload.code.strip().upper(), name=payload.name.strip(), description=payload.description, location=payload.location,
        source_type=payload.source_type, source_url_encrypted=encrypt_secret(payload.rtsp_url) if payload.source_type == "RTSP" else None,
        username_encrypted=encrypt_secret(payload.username), password_encrypted=encrypt_secret(payload.password),
        manufacturer=payload.manufacturer, model_name=payload.model_name,
        configured_width=payload.configured_width, configured_height=payload.configured_height, source_fps=payload.source_fps,
        capture_fps=payload.capture_fps, active=payload.active, ai_enabled=payload.ai_enabled,
        status="OFFLINE" if payload.active else "OFFLINE",
    )
    db.add(item)
    try:
        db.flush()
        default_model = db.scalar(select(VisionModelVersion).where(VisionModelVersion.is_default.is_(True), VisionModelVersion.active.is_(True)))
        ppe_model = db.scalar(select(VisionModelVersion).where(VisionModelVersion.code == 'PPE_REGION_SVM_BASELINE', VisionModelVersion.active.is_(True)))
        if default_model:
            db.add(CameraVisionSetting(organization_id=item.organization_id, camera_id=item.id, model_version_id=default_model.id, ppe_model_version_id=ppe_model.id if ppe_model else None, enabled=payload.ai_enabled, ppe_enabled=False, inference_fps=1.0, min_confidence=0.62, nms_iou_threshold=0.35, tracker_iou_threshold=0.25, tracker_max_missed_frames=4, tracker_min_hits_to_confirm=3, min_box_area_ratio=0.015, max_box_area_ratio=0.18, min_height_ratio=0.18, min_aspect_ratio=0.28, max_aspect_ratio=0.95, top_band_reject_y_ratio=0.15, top_band_reject_bottom_ratio=0.62, ppe_min_visibility_ratio=0.70, ppe_uncertainty_margin=0.05))
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "Código de cámara duplicado para la organización")
    add_audit(db, user, "CREATE", "camera", str(item.id), after={"code":item.code,"name":item.name,"source_type":item.source_type,"sector_id":str(item.sector_id)}, request=request, organization_id=item.organization_id)
    db.commit(); db.refresh(item)
    return _serialize(item)


@router.patch("/{camera_id}", response_model=CameraOut)
def update_camera(camera_id: uuid.UUID, payload: CameraUpdate, request: Request, user: User = Depends(require_permission("camera.manage")), db: Session = Depends(get_db)):
    cam = _get_camera(db, camera_id, user)
    before = {"name":cam.name,"active":cam.active,"capture_fps":cam.capture_fps,"ai_enabled":cam.ai_enabled}
    data = payload.model_dump(exclude_unset=True)
    for field in ("name","description","location","manufacturer","model_name","capture_fps","active","ai_enabled"):
        if field in data:
            setattr(cam, field, data[field])
    if "rtsp_url" in data:
        if cam.source_type != "RTSP" or not data["rtsp_url"] or not data["rtsp_url"].lower().startswith(("rtsp://","rtsps://")):
            raise HTTPException(422, "rtsp_url inválida")
        cam.source_url_encrypted = encrypt_secret(data["rtsp_url"])
    if "username" in data: cam.username_encrypted = encrypt_secret(data["username"])
    if "password" in data: cam.password_encrypted = encrypt_secret(data["password"])
    if "active" in data and not data["active"]:
        cam.status = "OFFLINE"
        cam.last_status_change_at = datetime.now(timezone.utc)
    if "ai_enabled" in data:
        vision_setting = db.scalar(select(CameraVisionSetting).where(CameraVisionSetting.camera_id == cam.id))
        if vision_setting:
            vision_setting.enabled = bool(data["ai_enabled"])
            vision_setting.updated_at = datetime.now(timezone.utc)
    cam.updated_at = datetime.now(timezone.utc)
    add_audit(db, user, "UPDATE", "camera", str(cam.id), before=before, after={"name":cam.name,"active":cam.active,"capture_fps":cam.capture_fps,"ai_enabled":cam.ai_enabled}, request=request, organization_id=cam.organization_id)
    db.commit(); db.refresh(cam)
    return _serialize(cam)


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_camera(camera_id: uuid.UUID, request: Request, user: User = Depends(require_permission("camera.manage")), db: Session = Depends(get_db)):
    cam = _get_camera(db, camera_id, user)
    cam.active = False; cam.status = "OFFLINE"; cam.last_status_change_at = datetime.now(timezone.utc)
    add_audit(db, user, "DEACTIVATE", "camera", str(cam.id), after={"active":False}, request=request, organization_id=cam.organization_id)
    db.commit()
    return Response(status_code=204)


@router.get("/{camera_id}/snapshot.jpg")
def snapshot(camera_id: uuid.UUID, user: User = Depends(require_permission("camera.read")), db: Session = Depends(get_db)):
    cam = _get_camera(db, camera_id, user)
    data = redis_client().get(frame_key(cam.id))
    if not data:
        raise HTTPException(404, "La cámara todavía no tiene un frame disponible")
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control":"no-store"})


@router.get("/{camera_id}/stream.mjpeg")
def stream(camera_id: uuid.UUID, user: User = Depends(require_permission("camera.read")), db: Session = Depends(get_db)):
    cam = _get_camera(db, camera_id, user)
    r = redis_client()
    key = frame_key(cam.id)

    def generate():
        previous = None
        while True:
            data = r.get(key)
            if data and data != previous:
                previous = data
                yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(data)).encode() + b"\r\n\r\n" + data + b"\r\n"
            time.sleep(0.15)

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame", headers={"Cache-Control":"no-store"})
