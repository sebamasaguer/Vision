"""Runtime smoke for PERSON hardening on a real frame from camera-worker."""
import time
import cv2
import numpy as np
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.camera import Camera
from app.models.vision import CameraVisionSetting, VisionModelVersion
from app.services.camera_runtime import redis_client, frame_key
from app.services.vision_runtime import create_detector, harden_person_detections, apply_nms


def main():
    with SessionLocal() as db:
        row = db.execute(
            select(Camera, CameraVisionSetting, VisionModelVersion)
            .join(CameraVisionSetting, CameraVisionSetting.camera_id == Camera.id)
            .join(VisionModelVersion, VisionModelVersion.id == CameraVisionSetting.model_version_id)
            .where(Camera.active.is_(True))
            .order_by(Camera.created_at)
        ).first()
    if not row:
        print('[SKIP] Sin cámara activa o modelo de visión.')
        return 0
    cam, cfg, model = row
    redis = redis_client()
    raw_frame = None
    for _ in range(20):
        raw_frame = redis.get(frame_key(cam.id))
        if raw_frame:
            break
        time.sleep(.5)
    if not raw_frame:
        print('[FAIL] No hay frame publicado por camera-worker.')
        return 1
    frame = cv2.imdecode(np.frombuffer(raw_frame, np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        print('[FAIL] Frame JPEG no decodificable.')
        return 1
    detector = create_detector(model.backend)
    started = time.perf_counter()
    raw = detector.detect_raw(frame, float(cfg.min_confidence))
    hardened, stats = harden_person_detections(
        raw, frame.shape,
        min_box_area_ratio=cfg.min_box_area_ratio,
        max_box_area_ratio=cfg.max_box_area_ratio,
        min_height_ratio=cfg.min_height_ratio,
        min_aspect_ratio=cfg.min_aspect_ratio,
        max_aspect_ratio=cfg.max_aspect_ratio,
        top_band_reject_y_ratio=cfg.top_band_reject_y_ratio,
        top_band_reject_bottom_ratio=cfg.top_band_reject_bottom_ratio,
    )
    filtered = apply_nms(hardened, float(cfg.min_confidence), float(cfg.nms_iou_threshold))
    elapsed = (time.perf_counter() - started) * 1000
    print(f'[VISION] camera={cam.code} backend={model.backend} raw={len(raw)} filtered={len(filtered)} rejected={stats["rejected"]} inference_ms={elapsed:.1f}')
    print('[PASS] Detector PERSON + hardening ejecutados sobre frame real del camera-worker.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
