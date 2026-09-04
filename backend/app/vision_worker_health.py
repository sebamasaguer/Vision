"""Lightweight Docker health probe for vision-engine.

No OpenCV/NumPy/vision_runtime imports: the probe only verifies the Redis
heartbeat written by the already-running vision-engine process.
"""
import json
import os
import sys
from datetime import datetime, timezone

from redis import Redis

VISION_HEARTBEAT = "hys:vision-engine:heartbeat"
MAX_AGE_SECONDS = 20.0


def main() -> int:
    try:
        redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
        client = Redis.from_url(
            redis_url,
            socket_connect_timeout=2,
            socket_timeout=2,
            decode_responses=True,
        )
        raw = client.get(VISION_HEARTBEAT)
        if not raw:
            raise RuntimeError("heartbeat ausente")
        data = json.loads(raw)
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(data["at"])).total_seconds()
        if age > MAX_AGE_SECONDS:
            raise RuntimeError(f"heartbeat vencido: {age:.1f}s")
        print(f"vision-engine healthy age={age:.1f}s backend={data.get('backend')}")
        return 0
    except Exception as exc:
        print(f"vision-engine unhealthy: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
