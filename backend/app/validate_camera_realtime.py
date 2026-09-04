"""Runtime certification for Hotfix v0.2.1.

Runs inside camera-worker/backend image. It never prints camera credentials.
"""
import json
import time

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.camera import Camera
from app.services.camera_runtime import meta_key, redis_client


def main() -> int:
    with SessionLocal() as db:
        cameras = list(db.scalars(select(Camera).where(Camera.active.is_(True), Camera.source_type == "DEMO_FILE")))

    if not cameras:
        print("[SKIP] No hay Demo Camera activa; pacing cubierto por tests unitarios.")
        return 0

    redis = redis_client()
    failures: list[str] = []
    for camera in cameras:
        target = float(camera.capture_fps or 5.0)
        meta = None
        deadline = time.monotonic() + 12.0
        while time.monotonic() < deadline:
            raw = redis.get(meta_key(camera.id))
            if raw:
                candidate = json.loads(raw.decode("utf-8"))
                if float(candidate.get("measured_fps") or 0) > 0:
                    meta = candidate
                    break
            time.sleep(0.5)

        if not meta:
            failures.append(f"{camera.code}: sin metrica estable en Redis")
            continue

        measured = float(meta.get("measured_fps") or 0)
        source = float(meta.get("source_fps") or 0)
        declared_target = float(meta.get("capture_fps_target") or 0)
        mode = meta.get("playback_mode")
        low = max(0.15, target * 0.60)
        high = target * 1.35

        print(
            f"[METRIC] {camera.code}: source_fps={source:.2f} "
            f"target={target:.2f} measured={measured:.2f} mode={mode}"
        )
        if mode != "REALTIME":
            failures.append(f"{camera.code}: playback_mode={mode!r}")
        if source <= 0:
            failures.append(f"{camera.code}: source_fps invalido")
        if abs(declared_target - target) > 0.05:
            failures.append(f"{camera.code}: capture_fps_target inconsistente")
        if not (low <= measured <= high):
            failures.append(
                f"{camera.code}: measured_fps={measured:.2f} fuera de rango {low:.2f}..{high:.2f}"
            )

    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        return 1
    print("[PASS] Demo Camera respeta tiempo real y la metrica refleja FPS de captura.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
