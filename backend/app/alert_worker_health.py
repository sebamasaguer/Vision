from datetime import datetime, timezone
from redis import Redis
from app.core.config import settings
from app.alert_worker import HEARTBEAT_KEY


def main():
    r=Redis.from_url(settings.redis_url,socket_timeout=2)
    raw=r.get(HEARTBEAT_KEY)
    if not raw:
        raise SystemExit("alert-worker heartbeat ausente")
    text=raw.decode() if isinstance(raw,bytes) else str(raw)
    ts=datetime.fromisoformat(text)
    if ts.tzinfo is None: ts=ts.replace(tzinfo=timezone.utc)
    age=(datetime.now(timezone.utc)-ts.astimezone(timezone.utc)).total_seconds()
    if age>max(20.0,settings.alert_poll_interval_seconds*4):
        raise SystemExit(f"alert-worker heartbeat vencido age={age:.1f}s")
    print(f"alert-worker healthy age={age:.1f}s")

if __name__=='__main__': main()
