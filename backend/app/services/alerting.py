from __future__ import annotations

import json
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib import request as urlrequest

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.organization import Organization
from app.models.safety import (
    AlertEscalation,
    AlertPolicy,
    NotificationChannel,
    NotificationDelivery,
    SafetyDetectionEvent,
    SafetyEventAction,
)

SEVERITY_POLICY_DEFAULTS = {
    "ADVERTENCIA": dict(name="Advertencia", acknowledge_sla_seconds=300, resolve_sla_seconds=1800, escalation_after_seconds=300, escalation_repeat_seconds=300, max_escalation_level=2),
    "ALTA": dict(name="Alta", acknowledge_sla_seconds=120, resolve_sla_seconds=900, escalation_after_seconds=120, escalation_repeat_seconds=180, max_escalation_level=3),
    "CRITICA": dict(name="Crítica", acknowledge_sla_seconds=60, resolve_sla_seconds=600, escalation_after_seconds=60, escalation_repeat_seconds=120, max_escalation_level=4),
}
PRIORITY_BY_SEVERITY = {"CRITICA": "P0_CRITICA", "ALTA": "P1_ALTA", "ADVERTENCIA": "P2_ADVERTENCIA", "INFO": "P3_INFO"}
DEFAULT_CHANNELS = ("IN_APP", "EMAIL", "WEBHOOK", "WHATSAPP")


def utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def severity_key(value: str | None) -> str:
    value = (value or "ADVERTENCIA").upper()
    return value if value in SEVERITY_POLICY_DEFAULTS else "ADVERTENCIA"


def ensure_alert_policies(db: Session, organization_id: uuid.UUID) -> list[AlertPolicy]:
    now = datetime.now(timezone.utc)
    rows = {p.severity: p for p in db.scalars(select(AlertPolicy).where(AlertPolicy.organization_id == organization_id))}
    for severity, cfg in SEVERITY_POLICY_DEFAULTS.items():
        if severity in rows:
            continue
        row = AlertPolicy(
            organization_id=organization_id,
            severity=severity,
            name=cfg["name"],
            acknowledge_sla_seconds=cfg["acknowledge_sla_seconds"],
            resolve_sla_seconds=cfg["resolve_sla_seconds"],
            escalation_after_seconds=cfg["escalation_after_seconds"],
            escalation_repeat_seconds=cfg["escalation_repeat_seconds"],
            max_escalation_level=cfg["max_escalation_level"],
            notification_channels=list(DEFAULT_CHANNELS),
            active=True,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        rows[severity] = row
    db.flush()
    return [rows[k] for k in ("ADVERTENCIA", "ALTA", "CRITICA")]


def ensure_notification_channels(db: Session, organization_id: uuid.UUID) -> list[NotificationChannel]:
    now = datetime.now(timezone.utc)
    rows = {c.channel: c for c in db.scalars(select(NotificationChannel).where(NotificationChannel.organization_id == organization_id))}
    defaults = {
        "IN_APP": dict(enabled=True, configuration_status="READY", destination="Bandeja de Monitoreo"),
        "EMAIL": dict(enabled=False, configuration_status="CONFIG_REQUIRED", destination=None),
        "WEBHOOK": dict(enabled=False, configuration_status="CONFIG_REQUIRED", destination=None),
        "WHATSAPP": dict(enabled=False, configuration_status="CONFIG_REQUIRED", destination=None),
    }
    for channel, cfg in defaults.items():
        if channel in rows:
            continue
        row = NotificationChannel(
            organization_id=organization_id,
            channel=channel,
            enabled=cfg["enabled"],
            configuration_status=cfg["configuration_status"],
            destination=cfg["destination"],
            config_json={},
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        rows[channel] = row
    db.flush()
    return [rows[k] for k in DEFAULT_CHANNELS]


def seed_alerting_for_existing_organizations(db: Session) -> None:
    for organization_id in db.scalars(select(Organization.id)):
        ensure_alert_policies(db, organization_id)
        ensure_notification_channels(db, organization_id)
    db.commit()


def get_policy(db: Session, event: SafetyDetectionEvent) -> AlertPolicy:
    ensure_alert_policies(db, event.organization_id)
    key = severity_key(event.severity)
    policy = db.scalar(select(AlertPolicy).where(
        AlertPolicy.organization_id == event.organization_id,
        AlertPolicy.severity == key,
        AlertPolicy.active.is_(True),
    ))
    if policy is None:
        policy = db.scalar(select(AlertPolicy).where(
            AlertPolicy.organization_id == event.organization_id,
            AlertPolicy.severity == "ADVERTENCIA",
        ))
    if policy is None:
        raise RuntimeError("No existe política de alertas para la organización")
    return policy


def _event_payload(event: SafetyDetectionEvent, trigger: str, level: int) -> dict:
    return {
        "event_id": str(event.id),
        "event_number": event.event_number,
        "trigger": trigger,
        "escalation_level": level,
        "severity": event.severity,
        "priority": event.alert_priority,
        "ppe_code": event.ppe_code,
        "ppe_name": event.ppe_name,
        "track_id": event.track_id,
        "status": event.status,
        "operational_status": event.operational_status,
        "ack_sla_status": event.ack_sla_status,
        "resolve_sla_status": event.resolve_sla_status,
        "confirmed_at": utc(event.confirmed_at).isoformat() if event.confirmed_at else None,
    }


def _delivery_exists(db: Session, event_id: uuid.UUID, channel: str, trigger: str, level: int) -> NotificationDelivery | None:
    return db.scalar(select(NotificationDelivery).where(
        NotificationDelivery.event_id == event_id,
        NotificationDelivery.channel == channel,
        NotificationDelivery.trigger_type == trigger,
        NotificationDelivery.escalation_level == level,
    ))


def _send_email(destination: str, payload: dict) -> str:
    if not settings.alert_smtp_host or not settings.alert_smtp_from:
        raise RuntimeError("SMTP no configurado")
    recipients = [x.strip() for x in destination.replace(";", ",").split(",") if x.strip()]
    if not recipients:
        raise RuntimeError("Destinatario email ausente")
    msg = EmailMessage()
    msg["Subject"] = f"HYS Vision IA · {payload['severity']} · {payload['ppe_name']}"
    msg["From"] = settings.alert_smtp_from
    msg["To"] = ", ".join(recipients)
    msg.set_content(json.dumps(payload, ensure_ascii=False, indent=2))
    with smtplib.SMTP(settings.alert_smtp_host, settings.alert_smtp_port, timeout=settings.alert_external_timeout_seconds) as smtp:
        if settings.alert_smtp_starttls:
            smtp.starttls()
        if settings.alert_smtp_user:
            smtp.login(settings.alert_smtp_user, settings.alert_smtp_password or "")
        smtp.send_message(msg)
    return "smtp"


def _post_json(url: str, payload: dict, extra_headers: dict | None = None) -> str:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "HYS-Vision-IA/0.8.0"}
    headers.update(extra_headers or {})
    req = urlrequest.Request(url, data=data, headers=headers, method="POST")
    with urlrequest.urlopen(req, timeout=settings.alert_external_timeout_seconds) as res:
        if res.status < 200 or res.status >= 300:
            raise RuntimeError(f"HTTP {res.status}")
        return res.headers.get("X-Request-Id") or f"http-{res.status}"


def _send_external(channel: NotificationChannel, payload: dict) -> str:
    if channel.channel == "EMAIL":
        return _send_email(channel.destination or "", payload)
    if channel.channel == "WEBHOOK":
        if not channel.destination:
            raise RuntimeError("URL webhook ausente")
        headers = {}
        if settings.alert_webhook_bearer_token:
            headers["Authorization"] = f"Bearer {settings.alert_webhook_bearer_token}"
        return _post_json(channel.destination, payload, headers)
    if channel.channel == "WHATSAPP":
        if not settings.alert_whatsapp_webhook_url:
            raise RuntimeError("Proveedor WhatsApp webhook no configurado")
        if not channel.destination:
            raise RuntimeError("Destino WhatsApp ausente")
        body = {"to": channel.destination, "type": "hys_alert", "alert": payload}
        headers = {}
        if settings.alert_whatsapp_bearer_token:
            headers["Authorization"] = f"Bearer {settings.alert_whatsapp_bearer_token}"
        return _post_json(settings.alert_whatsapp_webhook_url, body, headers)
    raise RuntimeError(f"Canal externo no soportado: {channel.channel}")


def dispatch_notification(db: Session, event: SafetyDetectionEvent, channel: NotificationChannel, trigger: str, level: int, now: datetime, *, send_external: bool = True) -> NotificationDelivery:
    existing = _delivery_exists(db, event.id, channel.channel, trigger, level)
    if existing:
        return existing
    payload = _event_payload(event, trigger, level)
    row = NotificationDelivery(
        organization_id=event.organization_id,
        event_id=event.id,
        channel_id=channel.id,
        channel=channel.channel,
        trigger_type=trigger,
        escalation_level=level,
        recipient=channel.destination,
        status="PENDING",
        attempt_count=0,
        payload_snapshot=payload,
        created_at=now,
    )
    db.add(row)
    db.flush()
    if not channel.enabled:
        row.status = "DISABLED"
        return row
    if channel.channel == "IN_APP":
        row.status = "DELIVERED"
        row.attempt_count = 1
        row.sent_at = now
        row.external_reference = "monitoring-inbox"
        event.last_notification_at = now
        return row
    if channel.configuration_status != "READY":
        row.status = "CONFIG_REQUIRED"
        row.error_message = "Canal habilitado sin configuración completa"
        return row
    if not send_external:
        row.status = "QUEUED"
        return row
    row.attempt_count += 1
    try:
        row.external_reference = _send_external(channel, payload)
        row.status = "SENT"
        row.sent_at = now
        event.last_notification_at = now
        channel.last_error = None
    except Exception as exc:
        row.status = "FAILED"
        row.error_message = str(exc)[:1000]
        channel.last_error = row.error_message
    return row


def notify_for_trigger(db: Session, event: SafetyDetectionEvent, policy: AlertPolicy, trigger: str, level: int, now: datetime, *, send_external: bool = True) -> list[NotificationDelivery]:
    channels = ensure_notification_channels(db, event.organization_id)
    allowed = {str(x).upper() for x in (policy.notification_channels or [])}
    out = []
    for channel in channels:
        if channel.channel not in allowed:
            continue
        # Disabled external channels are not noise in the delivery log; IN_APP is always materialized.
        if channel.channel != "IN_APP" and not channel.enabled:
            continue
        out.append(dispatch_notification(db, event, channel, trigger, level, now, send_external=send_external))
    return out


def initialize_event_alert_state(db: Session, event: SafetyDetectionEvent, now: datetime | None = None, *, create_notification: bool = True) -> SafetyDetectionEvent:
    now = utc(now or datetime.now(timezone.utc))
    policy = get_policy(db, event)
    confirmed = utc(event.confirmed_at) or now
    # Eventos heredados de bloques anteriores reciben su ventana SLA desde la
    # activación del Bloque 7, evitando convertir un backlog histórico en una
    # tormenta de escalamiento retroactivo. Eventos nuevos conservan confirmed_at.
    base = confirmed if abs((now - confirmed).total_seconds()) <= 30 else now
    if event.sla_ack_due_at is None:
        event.sla_ack_due_at = base + timedelta(seconds=policy.acknowledge_sla_seconds)
    if event.sla_resolve_due_at is None:
        event.sla_resolve_due_at = base + timedelta(seconds=policy.resolve_sla_seconds)
    if event.next_escalation_at is None and event.operational_status != "RESOLVED" and int(event.escalation_level or 0) == 0 and event.last_escalated_at is None:
        event.next_escalation_at = base + timedelta(seconds=policy.escalation_after_seconds)
    event.alert_priority = PRIORITY_BY_SEVERITY.get((event.severity or "").upper(), "P2_ADVERTENCIA")
    recompute_event_sla(event, now)
    ensure_notification_channels(db, event.organization_id)
    if create_notification:
        notify_for_trigger(db, event, policy, "EVENT_OPENED", 0, now, send_external=False)
    return event


def recompute_event_sla(event: SafetyDetectionEvent, now: datetime | None = None) -> SafetyDetectionEvent:
    now = utc(now or datetime.now(timezone.utc))
    ack_due = utc(event.sla_ack_due_at)
    resolve_due = utc(event.sla_resolve_due_at)
    ack_at = utc(event.acknowledged_at)
    resolved_at = utc(event.resolved_at)
    if ack_at:
        event.ack_sla_status = "MET" if not ack_due or ack_at <= ack_due else "BREACHED"
    elif ack_due and now > ack_due:
        event.ack_sla_status = "BREACHED"
    else:
        event.ack_sla_status = "PENDING"
    if resolved_at:
        event.resolve_sla_status = "MET" if not resolve_due or resolved_at <= resolve_due else "BREACHED"
    elif resolve_due and now > resolve_due:
        event.resolve_sla_status = "BREACHED"
    else:
        event.resolve_sla_status = "PENDING"
    return event


def _escalation_reason(event: SafetyDetectionEvent) -> str:
    if event.ack_sla_status == "BREACHED" and not event.acknowledged_at:
        return "ACK_SLA_BREACH"
    if event.resolve_sla_status == "BREACHED" and event.operational_status != "RESOLVED":
        return "RESOLVE_SLA_BREACH"
    return "UNRESOLVED_ALERT"


def escalate_event(db: Session, event: SafetyDetectionEvent, policy: AlertPolicy, now: datetime, *, send_external: bool = True) -> AlertEscalation | None:
    if event.operational_status == "RESOLVED" or event.escalation_level >= policy.max_escalation_level:
        event.next_escalation_at = None
        return None
    next_level = int(event.escalation_level or 0) + 1
    existing = db.scalar(select(AlertEscalation).where(AlertEscalation.event_id == event.id, AlertEscalation.level == next_level))
    if existing:
        event.escalation_level = max(event.escalation_level, existing.level)
        return existing
    reason = _escalation_reason(event)
    row = AlertEscalation(
        organization_id=event.organization_id,
        event_id=event.id,
        level=next_level,
        reason=reason,
        status="EXECUTED",
        scheduled_at=event.next_escalation_at,
        executed_at=now,
        details={"ack_sla_status":event.ack_sla_status,"resolve_sla_status":event.resolve_sla_status,"priority":event.alert_priority},
        created_at=now,
    )
    db.add(row)
    event.escalation_level = next_level
    event.last_escalated_at = now
    event.next_escalation_at = now + timedelta(seconds=policy.escalation_repeat_seconds) if next_level < policy.max_escalation_level else None
    db.add(SafetyEventAction(
        organization_id=event.organization_id,
        event_id=event.id,
        actor_user_id=None,
        action="ALERT_ESCALATED",
        from_status=event.operational_status,
        to_status=event.operational_status,
        details={"level":next_level,"reason":reason},
        created_at=now,
    ))
    notify_for_trigger(db, event, policy, reason, next_level, now, send_external=send_external)
    return row


def process_alerts(db: Session, now: datetime | None = None, *, send_external: bool = True) -> dict:
    now = utc(now or datetime.now(timezone.utc))
    events = list(db.scalars(select(SafetyDetectionEvent).where(SafetyDetectionEvent.operational_status != "RESOLVED", SafetyDetectionEvent.archived_at.is_(None)).order_by(SafetyDetectionEvent.confirmed_at)))
    initialized = escalated = breached_ack = breached_resolve = 0
    for event in events:
        was_uninitialized = event.sla_ack_due_at is None or event.sla_resolve_due_at is None
        initialize_event_alert_state(db, event, now, create_notification=True)
        if was_uninitialized:
            initialized += 1
        before_ack, before_resolve = event.ack_sla_status, event.resolve_sla_status
        recompute_event_sla(event, now)
        if event.ack_sla_status == "BREACHED": breached_ack += 1
        if event.resolve_sla_status == "BREACHED": breached_resolve += 1
        policy = get_policy(db, event)
        due = utc(event.next_escalation_at)
        if due and now >= due:
            if escalate_event(db, event, policy, now, send_external=send_external):
                escalated += 1
    db.commit()
    return {"processed":len(events),"initialized":initialized,"escalated":escalated,"ack_breached":breached_ack,"resolve_breached":breached_resolve}


def monitoring_sla_state(event: SafetyDetectionEvent, now: datetime | None = None) -> str:
    recompute_event_sla(event, now)
    if event.resolve_sla_status == "BREACHED":
        return "RESOLUTION_OVERDUE"
    if event.ack_sla_status == "BREACHED":
        return "ACK_OVERDUE"
    if event.escalation_level > 0:
        return "ESCALATED"
    return "ON_TIME"
