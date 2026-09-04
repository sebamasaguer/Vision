import signal
import threading
import time
from datetime import datetime, timezone
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.camera import Camera
from app.services.camera_runtime import CameraRunner, WORKER_HEARTBEAT, redis_client

shutdown = False


def stop_handler(*_):
    global shutdown
    shutdown = True


def main():
    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)
    redis = redis_client()
    runners: dict[str, tuple[CameraRunner, threading.Thread]] = {}
    print("HYS camera-worker v0.2.0 iniciado", flush=True)
    while not shutdown:
        redis.set(WORKER_HEARTBEAT, datetime.now(timezone.utc).isoformat(), ex=20)
        with SessionLocal() as db:
            active_ids = {str(x) for x in db.scalars(select(Camera.id).where(Camera.active.is_(True)))}
        for cid in list(runners):
            runner, thread = runners[cid]
            if cid not in active_ids or not thread.is_alive():
                runner.stop()
                thread.join(timeout=2)
                runners.pop(cid, None)
        for cid in active_ids:
            if cid not in runners:
                import uuid
                runner = CameraRunner(uuid.UUID(cid))
                thread = threading.Thread(target=runner.run, daemon=True, name=f"camera-{cid[:8]}")
                runners[cid] = (runner, thread)
                thread.start()
        time.sleep(max(1.0, settings.camera_poll_interval_seconds))
    for runner, thread in runners.values():
        runner.stop(); thread.join(timeout=3)
    print("HYS camera-worker detenido", flush=True)


if __name__ == "__main__":
    main()
