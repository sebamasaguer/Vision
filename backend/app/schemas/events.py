import uuid
from datetime import datetime
from pydantic import BaseModel


class SafetyEventOut(BaseModel):
    id: uuid.UUID
    event_number: str
    organization_id: uuid.UUID
    camera_id: uuid.UUID
    camera_code: str | None = None
    camera_name: str | None = None
    zone_id: uuid.UUID | None = None
    zone_code: str | None = None
    zone_name: str | None = None
    track_id: str
    ppe_code: str
    ppe_name: str
    severity: str
    status: str
    detection_status: str
    first_observed_at: datetime
    confirmed_at: datetime
    last_seen_at: datetime
    ended_at: datetime | None = None
    duration_seconds: float
    last_confidence: float | None = None
    consensus_ratio: float
    missing_observations: int
    evaluable_observations: int
    close_reason: str | None = None
    rule_snapshot: dict
    model_snapshot: dict
    operational_status: str = "NEW"
    review_outcome: str = "PENDING"
    assigned_to_user_id: uuid.UUID | None = None
    assigned_to_name: str | None = None
    acknowledged_by_user_id: uuid.UUID | None = None
    acknowledged_by_name: str | None = None
    acknowledged_at: datetime | None = None
    reviewed_by_user_id: uuid.UUID | None = None
    reviewed_by_name: str | None = None
    reviewed_at: datetime | None = None
    resolved_by_user_id: uuid.UUID | None = None
    resolved_by_name: str | None = None
    resolved_at: datetime | None = None
    review_notes: str | None = None
    resolution_note: str | None = None
    evidence_status: str = "PENDING"
    evidence_count: int = 0
    evidence_captured_at: datetime | None = None
    evidence_error: str | None = None
    response_seconds: float | None = None
    resolution_seconds: float | None = None
    alert_priority: str = "NORMAL"
    sla_ack_due_at: datetime | None = None
    sla_resolve_due_at: datetime | None = None
    ack_sla_status: str = "PENDING"
    resolve_sla_status: str = "PENDING"
    escalation_level: int = 0
    next_escalation_at: datetime | None = None
    last_escalated_at: datetime | None = None
    last_notification_at: datetime | None = None


class SafetyEventSummary(BaseModel):
    active: int
    critical_active: int
    high_active: int
    closed_today: int
    total: int
