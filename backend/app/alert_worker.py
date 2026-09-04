from __future__ import annotations

import time
from datetime import datetime, timezone
from redis import Redis

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.alerting import process_alerts

HEARTBEAT_KEY = "hys:alert-worker:heartbeat"


def heartbeat(redis: Redis):
    redis.set(HEARTBEAT_KEY, datetime.now(timezone.utc).isoformat(), ex=max(30, int(settings.alert_poll_interval_seconds * 6)))


def main():
    redis = Redis.from_url(settings.redis_url, socket_timeout=2)
    print(f"HYS alert-worker v{settings.app_version} iniciado", flush=True)
    while True:
        try:
            heartbeat(redis)
            with SessionLocal() as db:
                result = process_alerts(db, send_external=True)
            heartbeat(redis)
            if result["escalated"]:
                print(f"[ALERT] processed={result['processed']} escalated={result['escalated']} ack_breached={result['ack_breached']} resolve_breached={result['resolve_breached']}", flush=True)
        except Exception as exc:
            print(f"[ALERT-WORKER][ERROR] {type(exc).__name__}: {exc}", flush=True)
        time.sleep(max(1.0, settings.alert_poll_interval_seconds))


if __name__ == "__main__":
    main()
