import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PPEType(Base):
    __tablename__ = "ppe_types"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(String(600), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(80), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    criticality: Mapped[str] = mapped_column(String(24), nullable=False, default="ADVERTENCIA")
    color: Mapped[str] = mapped_column(String(16), nullable=False, default="#4fe2b6")
    detector_class: Mapped[str | None] = mapped_column(String(120), nullable=True)
    min_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.70)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Zone(Base):
    __tablename__ = "zones"
    __table_args__ = (UniqueConstraint("camera_id", "code", name="uq_zones_camera_code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    site_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)
    plant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("plants.id", ondelete="CASCADE"), nullable=False, index=True)
    sector_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("sectors.id", ondelete="CASCADE"), nullable=False, index=True)
    camera_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(String(600), nullable=True)
    polygon_points: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ZonePPERule(Base):
    __tablename__ = "zone_ppe_rules"
    __table_args__ = (UniqueConstraint("zone_id", "ppe_type_id", name="uq_zone_ppe_rule"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    zone_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("zones.id", ondelete="CASCADE"), nullable=False, index=True)
    ppe_type_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("ppe_types.id", ondelete="RESTRICT"), nullable=False, index=True)
    requirement: Mapped[str] = mapped_column(String(24), nullable=False, default="REQUIRED")
    severity: Mapped[str] = mapped_column(String(24), nullable=False, default="ADVERTENCIA")
    min_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    schedule_start: Mapped[str | None] = mapped_column(String(5), nullable=True)
    schedule_end: Mapped[str | None] = mapped_column(String(5), nullable=True)
    task: Mapped[str | None] = mapped_column(String(180), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(80), nullable=True)
    operation_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class SafetyDetectionEvent(Base):
    __tablename__ = "safety_detection_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_number: Mapped[str] = mapped_column(String(48), unique=True, nullable=False, index=True)
    dedupe_key: Mapped[str] = mapped_column(String(220), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    site_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)
    plant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("plants.id", ondelete="CASCADE"), nullable=False, index=True)
    sector_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("sectors.id", ondelete="CASCADE"), nullable=False, index=True)
    camera_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False, index=True)
    zone_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("zones.id", ondelete="SET NULL"), nullable=True, index=True)
    ppe_type_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("ppe_types.id", ondelete="RESTRICT"), nullable=False, index=True)
    track_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ppe_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ppe_name: Mapped[str] = mapped_column(String(160), nullable=False)
    requirement: Mapped[str] = mapped_column(String(24), nullable=False, default="REQUIRED")
    severity: Mapped[str] = mapped_column(String(24), nullable=False, default="ADVERTENCIA", index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="OPEN", index=True)
    detection_status: Mapped[str] = mapped_column(String(24), nullable=False, default="NO_DETECTADO")
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    consensus_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    missing_observations: Mapped[int] = mapped_column(nullable=False, default=0)
    evaluable_observations: Mapped[int] = mapped_column(nullable=False, default=0)
    rule_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    model_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    close_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    operational_status: Mapped[str] = mapped_column(String(24), nullable=False, default="NEW", index=True)
    review_outcome: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING", index=True)
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    acknowledged_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING", index=True)
    evidence_count: Mapped[int] = mapped_column(nullable=False, default=0)
    evidence_captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    alert_priority: Mapped[str] = mapped_column(String(24), nullable=False, default="NORMAL", index=True)
    sla_ack_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    sla_resolve_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    ack_sla_status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING", index=True)
    resolve_sla_status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING", index=True)
    escalation_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    next_escalation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_notification_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # v0.9.0 — clasificación de datos y archivado controlado de QA/piloto.
    data_origin: Mapped[str] = mapped_column(String(24), nullable=False, default="OPERATIONAL", index=True)
    analytics_excluded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    archived_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    archive_reason: Mapped[str | None] = mapped_column(String(240), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ComplianceEvaluation(Base):
    __tablename__ = "compliance_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    camera_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False, index=True)
    zone_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("zones.id", ondelete="SET NULL"), nullable=True, index=True)
    ppe_type_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("ppe_types.id", ondelete="SET NULL"), nullable=True, index=True)
    event_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("safety_detection_events.id", ondelete="SET NULL"), nullable=True, index=True)
    track_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ppe_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    observed_status: Mapped[str] = mapped_column(String(24), nullable=False)
    compliance_status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    consensus_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    missing_observations: Mapped[int] = mapped_column(nullable=False, default=0)
    evaluable_observations: Mapped[int] = mapped_column(nullable=False, default=0)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class SafetyEventEvidence(Base):
    __tablename__ = "safety_event_evidence"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("safety_detection_events.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    bucket: Mapped[str] = mapped_column(String(120), nullable=False)
    object_key: Mapped[str] = mapped_column(String(600), nullable=False, unique=True)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source_frame_at: Mapped[str | None] = mapped_column(String(80), nullable=True)
    immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class SafetyEventNote(Base):
    __tablename__ = "safety_event_notes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("safety_detection_events.id", ondelete="CASCADE"), nullable=False, index=True)
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    note_type: Mapped[str] = mapped_column(String(24), nullable=False, default="COMMENT")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)


class SafetyEventAction(Base):
    __tablename__ = "safety_event_actions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("safety_detection_events.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    from_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)


class PilotCleanupRun(Base):
    __tablename__ = "pilot_cleanup_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="RUNNING", index=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    archived_events: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    closed_technical_events: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resolved_operational_events: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    disabled_compliance_cameras: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    restored_sla_policies: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    preserved_evidence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    preserved_actions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AlertPolicy(Base):
    __tablename__ = "alert_policies"
    __table_args__ = (UniqueConstraint("organization_id", "severity", name="uq_alert_policy_org_severity"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    acknowledge_sla_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    resolve_sla_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    escalation_after_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    escalation_repeat_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    max_escalation_level: Mapped[int] = mapped_column(Integer, nullable=False)
    notification_channels: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class NotificationChannel(Base):
    __tablename__ = "notification_channels"
    __table_args__ = (UniqueConstraint("organization_id", "channel", name="uq_notification_channel_org_type"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    configuration_status: Mapped[str] = mapped_column(String(32), nullable=False, default="CONFIG_REQUIRED", index=True)
    destination: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AlertEscalation(Base):
    __tablename__ = "alert_escalations"
    __table_args__ = (UniqueConstraint("event_id", "level", name="uq_alert_escalation_event_level"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("safety_detection_events.id", ondelete="CASCADE"), nullable=False, index=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="EXECUTED", index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (UniqueConstraint("event_id", "channel", "trigger_type", "escalation_level", name="uq_notification_delivery_dedupe"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("safety_detection_events.id", ondelete="CASCADE"), nullable=False, index=True)
    channel_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("notification_channels.id", ondelete="SET NULL"), nullable=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    escalation_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recipient: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    external_reference: Mapped[str | None] = mapped_column(String(300), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
