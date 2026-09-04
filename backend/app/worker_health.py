"""Lightweight Docker health probe for camera-worker.

Deliberately avoids importing camera_runtime/OpenCV/SQLAlchemy. Docker launches
this module in a fresh Python interpreter every healthcheck; importing cv2 in
that path can exceed a short Docker timeout under CPU load even when the worker
heartbeat itself is current.
"""
import os
import sys
from datetime import datetime, timezone

from redis import Redis

WORKER_HEARTBEAT = "hys:camera-worker:heartbeat"
MAX_AGE_SECONDS = 15.0


def main() -> int:
    try:
        redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
        client = Redis.from_url(
            redis_url,
            socket_connect_timeout=2,
            socket_timeout=2,
            decode_responses=True,
        )
        text = client.get(WORKER_HEARTBEAT)
        if not text:
            raise RuntimeError("heartbeat ausente")
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(text)).total_seconds()
        if age > MAX_AGE_SECONDS:
            raise RuntimeError(f"heartbeat vencido: {age:.1f}s")
        print(f"camera-worker healthy age={age:.1f}s")
        return 0
    except Exception as exc:
        print(f"camera-worker unhealthy: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
