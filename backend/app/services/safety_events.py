from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, object_session

from app.models.safety import ComplianceEvaluation, SafetyDetectionEvent, SafetyEventAction


def event_number(now: datetime) -> str:
    return f"HYS-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


def _event_payload(camera, action: dict, model_snapshot: dict):
    rule = action.get("rule") or {}
    now = action.get("now") or datetime.now(timezone.utc)
    return dict(
        event_number=event_number(now),
        dedupe_key=action["key"],
        organization_id=camera.organization_id,
        site_id=camera.site_id,
        plant_id=camera.plant_id,
        sector_id=camera.sector_id,
        camera_id=camera.id,
        zone_id=uuid.UUID(str(rule["zone_id"])) if rule.get("zone_id") else None,
        ppe_type_id=uuid.UUID(str(rule["ppe_type_id"])),
        track_id=action["track_id"],
        ppe_code=rule.get("ppe_code") or "UNKNOWN",
        ppe_name=rule.get("ppe_name") or rule.get("ppe_code") or "EPP",
        requirement=rule.get("requirement") or "REQUIRED",
        severity=rule.get("severity") or "ADVERTENCIA",
        status="OPEN",
        detection_status=action.get("observed_status") or "NO_DETECTADO",
        first_observed_at=now - timedelta(seconds=float(action.get("missing_span_seconds") or 0.0)),
        confirmed_at=now,
        last_seen_at=now,
        duration_seconds=float(action.get("missing_span_seconds") or 0.0),
        last_confidence=action.get("confidence"),
        min_confidence=action.get("confidence"),
        consensus_ratio=float(action.get("consensus_ratio") or 0.0),
        missing_observations=int(action.get("missing_observations") or 0),
        evaluable_observations=int(action.get("evaluable_observations") or 0),
        rule_snapshot={k: v for k, v in rule.items() if k not in {"ppe_type_obj"}},
        model_snapshot=model_snapshot,
        created_at=now,
        updated_at=now,
    )



def get_open_event(db: Session, dedupe_key: str):
    return db.scalar(select(SafetyDetectionEvent).where(
        SafetyDetectionEvent.dedupe_key == dedupe_key, SafetyDetectionEvent.status == "OPEN"
    ).order_by(desc(SafetyDetectionEvent.confirmed_at)))

def open_or_get_event(db: Session, camera, action: dict, model_snapshot: dict, cooldown_seconds: float, now: datetime):
    existing = db.scalar(select(SafetyDetectionEvent).where(
        SafetyDetectionEvent.dedupe_key == action["key"], SafetyDetectionEvent.status == "OPEN"
    ).order_by(desc(SafetyDetectionEvent.confirmed_at)))
    if existing:
        update_event(existing, action, now)
        return existing, None

    latest_closed = db.scalar(select(SafetyDetectionEvent).where(
        SafetyDetectionEvent.dedupe_key == action["key"], SafetyDetectionEvent.status == "CLOSED"
    ).order_by(desc(SafetyDetectionEvent.ended_at)).limit(1))
    if latest_closed and latest_closed.ended_at:
        until = latest_closed.ended_at + timedelta(seconds=float(cooldown_seconds))
        if now < until:
            return None, until

    payload = _event_payload(camera, {**action, "now": now}, model_snapshot)
    event = SafetyDetectionEvent(**payload)
    db.add(event)
    db.flush()
    from app.services.alerting import initialize_event_alert_state
    initialize_event_alert_state(db, event, now, create_notification=True)
    db.add(SafetyEventAction(organization_id=event.organization_id,event_id=event.id,actor_user_id=None,action="EVENT_CONFIRMED",from_status=None,to_status="NEW",details={"source":"TEMPORAL_COMPLIANCE_ENGINE","engine_version":model_snapshot.get("engine_version")},created_at=now))
    return event, None


def update_event(event: SafetyDetectionEvent, action: dict, now: datetime):
    event.last_seen_at = now
    event.duration_seconds = max(0.0, (now - event.first_observed_at).total_seconds())
    event.last_confidence = action.get("confidence")
    confidence = action.get("confidence")
    if confidence is not None:
        event.min_confidence = confidence if event.min_confidence is None else min(float(event.min_confidence), float(confidence))
    event.consensus_ratio = float(action.get("consensus_ratio") or 0.0)
    event.missing_observations = int(action.get("missing_observations") or 0)
    event.evaluable_observations = int(action.get("evaluable_observations") or 0)
    rule = action.get("rule") or {}
    if rule:
        event.zone_id = uuid.UUID(str(rule["zone_id"])) if rule.get("zone_id") else event.zone_id
        event.severity = rule.get("severity") or event.severity
        event.rule_snapshot = {k: v for k, v in rule.items() if k not in {"ppe_type_obj"}}
    event.updated_at = now


def close_event(event: SafetyDetectionEvent, now: datetime, reason: str):
    event.status = "CLOSED"
    event.ended_at = now
    event.last_seen_at = now
    event.duration_seconds = max(0.0, (now - event.first_observed_at).total_seconds())
    event.close_reason = reason
    event.updated_at = now
    # Technical close is independent from human operational resolution.
    db = object_session(event)
    if db is not None:
        db.add(SafetyEventAction(organization_id=event.organization_id,event_id=event.id,actor_user_id=None,action="DETECTION_CLOSED",from_status="OPEN",to_status="CLOSED",details={"reason":reason},created_at=now))


def persist_evaluation(db: Session, camera, sample: dict, event_id=None, now: datetime | None = None):
    now = now or datetime.now(timezone.utc)
    rule = sample.get("rule") or {}
    row = ComplianceEvaluation(
        organization_id=camera.organization_id,
        camera_id=camera.id,
        zone_id=uuid.UUID(str(rule["zone_id"])) if rule.get("zone_id") else None,
        ppe_type_id=uuid.UUID(str(rule["ppe_type_id"])) if rule.get("ppe_type_id") else None,
        event_id=uuid.UUID(str(event_id)) if event_id else None,
        track_id=sample["track_id"],
        ppe_code=sample["ppe_code"],
        observed_status=sample["observed_status"],
        compliance_status=sample["compliance_status"],
        confidence=sample.get("confidence"),
        consensus_ratio=sample.get("consensus_ratio"),
        missing_observations=int(sample.get("missing_observations") or 0),
        evaluable_observations=int(sample.get("evaluable_observations") or 0),
        details={
            "zone_code": sample.get("zone_code"),
            "severity": sample.get("severity"),
            "requirement": sample.get("requirement"),
        },
        evaluated_at=now,
    )
    db.add(row)
    return row
