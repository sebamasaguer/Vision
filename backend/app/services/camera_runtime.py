import json
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit, urlunsplit

import cv2
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.camera import Camera
from app.services.camera_crypto import decrypt_secret

FRAME_PREFIX = "hys:camera:frame:"
META_PREFIX = "hys:camera:meta:"
WORKER_HEARTBEAT = "hys:camera-worker:heartbeat"


def redis_client():
    from redis import Redis
    return Redis.from_url(settings.redis_url, socket_timeout=2, decode_responses=False)


def frame_key(camera_id: uuid.UUID | str) -> str:
    return f"{FRAME_PREFIX}{camera_id}"


def meta_key(camera_id: uuid.UUID | str) -> str:
    return f"{META_PREFIX}{camera_id}"


def build_source(camera: Camera) -> str:
    if camera.source_type == "DEMO_FILE":
        return settings.demo_video_path
    url = decrypt_secret(camera.source_url_encrypted)
    if not url:
        raise RuntimeError("RTSP URL no configurada")
    username = decrypt_secret(camera.username_encrypted)
    password = decrypt_secret(camera.password_encrypted)
    if not username:
        return url
    parts = urlsplit(url)
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    userinfo = quote(username, safe="")
    if password:
        userinfo += ":" + quote(password, safe="")
    netloc = f"{userinfo}@{host}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def update_camera_state(
    camera_id: uuid.UUID,
    *,
    status: str | None = None,
    last_error: str | None = None,
    measured_fps: float | None = None,
    source_fps: float | None = None,
    latency_ms: float | None = None,
    frame_received: bool = False,
    connected: bool = False,
) -> None:
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        cam = db.get(Camera, camera_id)
        if not cam:
            return
        if status and cam.status != status:
            cam.status = status
            cam.last_status_change_at = now
        if last_error is not None:
            cam.last_error = last_error[:500] if last_error else None
        if measured_fps is not None:
            cam.measured_fps = measured_fps
        if source_fps is not None:
            cam.source_fps = source_fps
        if latency_ms is not None:
            cam.latency_ms = latency_ms
        if connected:
            cam.last_connection_at = now
        if frame_received:
            cam.last_frame_at = now
        db.commit()


def publish_frame(redis, camera_id: uuid.UUID, jpeg: bytes, metadata: dict) -> None:
    pipe = redis.pipeline()
    ttl = max(3, settings.camera_frame_ttl_seconds)
    pipe.set(frame_key(camera_id), jpeg, ex=ttl)
    pipe.set(meta_key(camera_id), json.dumps(metadata, separators=(",", ":")).encode("utf-8"), ex=ttl)
    pipe.execute()


def measured_rate_hz(timestamps: list[float] | deque[float]) -> float:
    """Return the observed event rate from publication timestamps.

    This intentionally measures frames *published by HYS Vision*, not how fast
    OpenCV can decode a local file. That distinction is essential for temporal
    validation and later tracking/alert logic.
    """
    if len(timestamps) < 2:
        return 0.0
    elapsed = float(timestamps[-1] - timestamps[0])
    if elapsed <= 0:
        return 0.0
    return (len(timestamps) - 1) / elapsed


def demo_pacing_delay(*, frame_index: int, source_fps: float, playback_started: float, now: float) -> float:
    """Seconds to wait so a local MP4 advances on its original wall-clock timeline."""
    if source_fps <= 0 or frame_index <= 0:
        return 0.0
    target_at = playback_started + (frame_index / source_fps)
    return max(0.0, target_at - now)


def valid_source_fps(value: float | int | None, fallback: float = 15.0) -> float:
    try:
        fps = float(value or 0)
    except (TypeError, ValueError):
        fps = 0.0
    # Avoid pathological metadata causing multi-minute sleeps or busy loops.
    if fps < 0.2 or fps > 240:
        return fallback
    return fps


class CameraRunner:
    def __init__(self, camera_id: uuid.UUID):
        self.camera_id = camera_id
        self._stop = False

    def stop(self):
        self._stop = True

    def _load(self) -> Camera | None:
        with SessionLocal() as db:
            return db.scalar(select(Camera).where(Camera.id == self.camera_id))

    def run(self):
        redis = redis_client()
        while not self._stop:
            camera = self._load()
            if not camera or not camera.active:
                update_camera_state(self.camera_id, status="OFFLINE", last_error="Cámara desactivada")
                return
            try:
                source = build_source(camera)
            except Exception as exc:
                update_camera_state(self.camera_id, status="OFFLINE", last_error=str(exc))
                time.sleep(5)
                continue

            cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                # OpenCV no expone de forma portable el código RTSP 401. No inventamos ERROR_AUTENTICACION.
                update_camera_state(self.camera_id, status="OFFLINE", last_error="No se pudo abrir la fuente de video")
                cap.release()
                time.sleep(5)
                continue

            raw_source_fps = cap.get(cv2.CAP_PROP_FPS)
            detected_source_fps = valid_source_fps(raw_source_fps, fallback=float(camera.source_fps or 15.0))
            update_camera_state(
                self.camera_id,
                status="ONLINE",
                last_error="",
                source_fps=detected_source_fps,
                connected=True,
            )

            last_publish = 0.0
            last_db_metrics = 0.0
            no_frame_since = None
            desired_interval = 1.0 / max(float(camera.capture_fps or 5.0), 0.2)
            publish_times: deque[float] = deque(maxlen=30)

            # Local demo files must follow their media timeline. Without this,
            # cv2.VideoCapture decodes the file as fast as the CPU allows.
            is_demo = camera.source_type == "DEMO_FILE"
            playback_started = time.monotonic()
            demo_frame_index = 0

            while not self._stop:
                before = time.monotonic()
                ok, frame = cap.read()
                after = time.monotonic()

                if not ok or frame is None:
                    if is_demo:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        playback_started = time.monotonic()
                        demo_frame_index = 0
                        publish_times.clear()
                        last_publish = 0.0
                        time.sleep(min(0.05, 1.0 / detected_source_fps))
                        continue
                    no_frame_since = no_frame_since or time.monotonic()
                    if time.monotonic() - no_frame_since > 3:
                        update_camera_state(
                            self.camera_id,
                            status="SIN_VIDEO",
                            last_error="Fuente conectada sin frames decodificables",
                        )
                        break
                    time.sleep(0.1)
                    continue

                no_frame_since = None

                if is_demo:
                    demo_frame_index += 1
                    delay = demo_pacing_delay(
                        frame_index=demo_frame_index,
                        source_fps=detected_source_fps,
                        playback_started=playback_started,
                        now=time.monotonic(),
                    )
                    if delay > 0:
                        time.sleep(delay)

                now = time.monotonic()
                # Small scheduling tolerance prevents floating-point/frame-boundary
                # jitter from turning a 5 FPS target into ~3.75 FPS on a 15 FPS file.
                if last_publish and (now - last_publish + min(0.005, desired_interval * 0.05)) < desired_interval:
                    continue

                encode_ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
                if not encode_ok:
                    continue

                last_publish = now
                publish_times.append(now)
                fps = measured_rate_hz(publish_times)
                # Before two publications there is not enough evidence for an
                # observed rate; report zero rather than decode throughput.
                measured_fps = fps if len(publish_times) >= 2 else 0.0
                latency_ms = (after - before) * 1000.0
                meta = {
                    "camera_id": str(self.camera_id),
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "width": int(frame.shape[1]),
                    "height": int(frame.shape[0]),
                    "source_fps": round(detected_source_fps, 2),
                    "capture_fps_target": round(float(camera.capture_fps or 5.0), 2),
                    "measured_fps": round(measured_fps, 2),
                    "latency_ms": round(latency_ms, 2),
                    "playback_mode": "REALTIME" if is_demo else "LIVE",
                }
                publish_frame(redis, self.camera_id, encoded.tobytes(), meta)

                # Camera state remains live in Redis at capture_fps, while
                # durable metrics are flushed at ~1 Hz to avoid needless DB I/O.
                if now - last_db_metrics >= 1.0:
                    update_camera_state(
                        self.camera_id,
                        status="ONLINE",
                        last_error="",
                        measured_fps=measured_fps,
                        source_fps=detected_source_fps,
                        latency_ms=latency_ms,
                        frame_received=True,
                    )
                    last_db_metrics = now

            cap.release()
            if not self._stop:
                time.sleep(2)
