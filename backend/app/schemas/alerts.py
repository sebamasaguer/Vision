import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class AlertPolicyOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    severity: str
    name: str
    acknowledge_sla_seconds: int
    resolve_sla_seconds: int
    escalation_after_seconds: int
    escalation_repeat_seconds: int
    max_escalation_level: int
    notification_channels: list[str]
    active: bool


class AlertPolicyUpdate(BaseModel):
    acknowledge_sla_seconds: int | None = Field(default=None, ge=10, le=86400)
    resolve_sla_seconds: int | None = Field(default=None, ge=30, le=604800)
    escalation_after_seconds: int | None = Field(default=None, ge=10, le=86400)
    escalation_repeat_seconds: int | None = Field(default=None, ge=10, le=86400)
    max_escalation_level: int | None = Field(default=None, ge=1, le=10)
    notification_channels: list[str] | None = None
    active: bool | None = None


class NotificationChannelOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    channel: str
    enabled: bool
    configuration_status: str
    destination: str | None = None
    config_json: dict
    last_test_at: datetime | None = None
    last_test_status: str | None = None
    last_error: str | None = None


class NotificationChannelUpdate(BaseModel):
    enabled: bool | None = None
    destination: str | None = Field(default=None, max_length=1000)
    config_json: dict | None = None


class NotificationDeliveryOut(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    event_number: str | None = None
    channel: str
    trigger_type: str
    escalation_level: int
    recipient: str | None = None
    status: str
    attempt_count: int
    external_reference: str | None = None
    error_message: str | None = None
    created_at: datetime
    sent_at: datetime | None = None


class AlertEscalationOut(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    level: int
    reason: str
    status: str
    scheduled_at: datetime | None = None
    executed_at: datetime | None = None
    details: dict
    created_at: datetime


class MonitoringInboxItem(BaseModel):
    event_id: uuid.UUID
    event_number: str
    organization_id: uuid.UUID
    camera_code: str | None = None
    zone_code: str | None = None
    track_id: str
    ppe_code: str
    ppe_name: str
    severity: str
    priority: str
    technical_status: str
    operational_status: str
    review_outcome: str
    assigned_to_user_id: uuid.UUID | None = None
    assigned_to_name: str | None = None
    confirmed_at: datetime
    last_seen_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    sla_ack_due_at: datetime | None = None
    sla_resolve_due_at: datetime | None = None
    ack_sla_status: str
    resolve_sla_status: str
    escalation_level: int
    next_escalation_at: datetime | None = None
    seconds_to_ack_due: float | None = None
    seconds_to_resolve_due: float | None = None
    notification_count: int = 0
    evidence_count: int = 0


class MonitoringSummary(BaseModel):
    active: int
    unacknowledged: int
    ack_overdue: int
    resolution_overdue: int
    escalated: int
    critical: int
    assigned_to_me: int
    notifications_failed: int


class InboxResponse(BaseModel):
    total: int
    items: list[MonitoringInboxItem]


class PolicyListResponse(BaseModel):
    organization_id: uuid.UUID | None = None
    items: list[AlertPolicyOut]


class ChannelListResponse(BaseModel):
    organization_id: uuid.UUID | None = None
    items: list[NotificationChannelOut]


class DeliveryListResponse(BaseModel):
    total: int
    items: list[NotificationDeliveryOut]


class EscalationListResponse(BaseModel):
    total: int
    items: list[AlertEscalationOut]


class WorkerStatus(BaseModel):
    status: str
    age_seconds: float | None = None
    heartbeat: str | None = None
