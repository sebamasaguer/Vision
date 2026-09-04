from __future__ import annotations

import hashlib
import io
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.safety import SafetyDetectionEvent, SafetyEventAction, SafetyEventEvidence


def minio_client():
    from minio import Minio
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _object_key(event: SafetyDetectionEvent, kind: str, digest: str, ext: str) -> str:
    return f"events/{event.organization_id}/{event.camera_id}/{event.event_number}/{kind.lower()}-{digest[:16]}.{ext}"


def _put_bytes(client, bucket: str, key: str, data: bytes, content_type: str):
    # Content-addressed key + no update/delete endpoint => application-level write-once evidence.
    try:
        client.stat_object(bucket, key)
        return
    except Exception:
        pass
    client.put_object(bucket, key, io.BytesIO(data), len(data), content_type=content_type)


def _record(
    db: Session,
    event: SafetyDetectionEvent,
    kind: str,
    data: bytes,
    mime: str,
    ext: str,
    captured_at: datetime,
    source_frame_at: str | None,
    metadata: dict,
):
    digest = sha256_bytes(data)
    key = _object_key(event, kind, digest, ext)
    existing = db.scalar(
        select(SafetyEventEvidence).where(
            SafetyEventEvidence.event_id == event.id,
            SafetyEventEvidence.kind == kind,
        )
    )
    if existing:
        return existing
    client = minio_client()
    _put_bytes(client, settings.minio_bucket_evidence, key, data, mime)
    row = SafetyEventEvidence(
        organization_id=event.organization_id,
        event_id=event.id,
        kind=kind,
        bucket=settings.minio_bucket_evidence,
        object_key=key,
        mime_type=mime,
        sha256=digest,
        size_bytes=len(data),
        captured_at=captured_at,
        source_frame_at=source_frame_at,
        immutable=True,
        metadata_json=metadata,
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.flush()
    return row


def _run_ffmpeg(args: list[str], timeout: int = 30) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg no disponible para evidencia H.264")
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ffmpeg fallo ({proc.returncode}): {detail[:500]}")


def _encode_jpeg_sequence_h264(frames: list[np.ndarray], fps: float) -> bytes | None:
    if len(frames) < 2:
        return None
    h, w = frames[0].shape[:2]
    fps = max(0.5, float(fps or 1.0))
    with tempfile.TemporaryDirectory(prefix="hys-evidence-") as tmp:
        tmp_path = Path(tmp)
        for idx, img in enumerate(frames):
            if img.shape[:2] != (h, w):
                img = cv2.resize(img, (w, h))
            frame_path = tmp_path / f"frame-{idx:06d}.png"
            ok = cv2.imwrite(str(frame_path), img)
            if not ok:
                raise RuntimeError(f"No se pudo serializar frame {idx} para evidencia")

        out_path = tmp_path / "clip-browser.mp4"
        _run_ffmpeg(
            [
                "-framerate",
                f"{fps:.6f}",
                "-i",
                str(tmp_path / "frame-%06d.png"),
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-profile:v",
                "baseline",
                "-level",
                "3.0",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-r",
                f"{fps:.6f}",
                str(out_path),
            ]
        )
        data = out_path.read_bytes()
        return data if len(data) > 256 else None


def encode_clip(frame_buffer: list[tuple[str, bytes]], fps: float = 1.0) -> bytes | None:
    """Encode immutable event evidence as browser-compatible H.264/AVC MP4.

    Block 6 originally used OpenCV's ``mp4v`` codec. That file is structurally
    valid but is not reliably decoded by Chromium/Chrome. Hotfix v0.7.2 uses
    ffmpeg/libx264 with avc1-compatible H.264, yuv420p and a fast-start moov atom.
    """
    if len(frame_buffer) < 2:
        return None
    frames: list[np.ndarray] = []
    for _, raw in frame_buffer:
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if img is not None:
            frames.append(img)
    return _encode_jpeg_sequence_h264(frames, fps)


def browser_preview_bytes(data: bytes, mime_type: str) -> tuple[bytes, str, bool]:
    """Return a browser-playable representation without mutating original evidence.

    Images are returned unchanged. Existing Block-6 MP4 evidence may contain an
    ``mp4v`` stream, so video is transcoded ephemerally to H.264. The persisted
    object and its SHA-256 remain untouched; callers must expose the source SHA
    separately rather than claim the preview bytes match the evidence digest.
    """
    if not mime_type.startswith("video/"):
        return data, mime_type, False

    with tempfile.TemporaryDirectory(prefix="hys-preview-") as tmp:
        tmp_path = Path(tmp)
        src = tmp_path / "source.mp4"
        out = tmp_path / "preview.mp4"
        src.write_bytes(data)
        _run_ffmpeg(
            [
                "-i",
                str(src),
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-profile:v",
                "baseline",
                "-level",
                "3.0",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(out),
            ]
        )
        preview = out.read_bytes()
        if len(preview) <= 256:
            raise RuntimeError("Preview H.264 vacio o invalido")
        return preview, "video/mp4", True


def capture_event_evidence(
    db: Session,
    event: SafetyDetectionEvent,
    frame_jpeg: bytes | None,
    overlay_jpeg: bytes | None,
    frame_buffer: list[tuple[str, bytes]],
    source_frame_at: str | None,
    fps: float = 1.0,
):
    count = int(
        db.scalar(
            select(func.count())
            .select_from(SafetyEventEvidence)
            .where(SafetyEventEvidence.event_id == event.id)
        )
        or 0
    )
    if count:
        event.evidence_status = "READY"
        event.evidence_count = count
        return count
    now = datetime.now(timezone.utc)
    created = []
    errors = []
    base_meta = {
        "event_number": event.event_number,
        "track_id": event.track_id,
        "ppe_code": event.ppe_code,
        "severity": event.severity,
        "engine": "block6-evidence-v0.7.2",
    }
    try:
        if frame_jpeg:
            created.append(
                _record(
                    db,
                    event,
                    "SNAPSHOT_RAW",
                    frame_jpeg,
                    "image/jpeg",
                    "jpg",
                    now,
                    source_frame_at,
                    {**base_meta, "view": "raw"},
                )
            )
    except Exception as exc:
        errors.append(f"raw:{exc}")
    try:
        if overlay_jpeg:
            created.append(
                _record(
                    db,
                    event,
                    "SNAPSHOT_ANNOTATED",
                    overlay_jpeg,
                    "image/jpeg",
                    "jpg",
                    now,
                    source_frame_at,
                    {**base_meta, "view": "annotated"},
                )
            )
    except Exception as exc:
        errors.append(f"annotated:{exc}")
    try:
        clip = encode_clip(frame_buffer, fps)
        if clip:
            created.append(
                _record(
                    db,
                    event,
                    "CLIP_PRE_EVENT",
                    clip,
                    "video/mp4",
                    "mp4",
                    now,
                    source_frame_at,
                    {
                        **base_meta,
                        "frame_count": len(frame_buffer),
                        "fps": fps,
                        "phase": "pre-confirmation",
                        "video_codec": "h264",
                        "pixel_format": "yuv420p",
                        "browser_compatible": True,
                    },
                )
            )
    except Exception as exc:
        errors.append(f"clip:{exc}")
    created = [x for x in created if x is not None]
    event.evidence_count = len(created)
    event.evidence_captured_at = now if created else None
    event.evidence_error = "; ".join(errors)[:500] if errors else None
    event.evidence_status = "READY" if len(created) >= 2 and not errors else ("PARTIAL" if created else "ERROR")
    db.add(
        SafetyEventAction(
            organization_id=event.organization_id,
            event_id=event.id,
            actor_user_id=None,
            action="EVIDENCE_CAPTURED" if created else "EVIDENCE_CAPTURE_ERROR",
            from_status=None,
            to_status=event.evidence_status,
            details={"items": len(created), "errors": errors},
            created_at=now,
        )
    )
    return len(created)


def read_evidence_bytes(evidence: SafetyEventEvidence) -> bytes:
    response = minio_client().get_object(evidence.bucket, evidence.object_key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()
