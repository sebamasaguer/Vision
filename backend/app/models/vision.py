import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class VisionModelVersion(Base):
    __tablename__ = 'vision_model_versions'

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    backend: Mapped[str] = mapped_column(String(80), nullable=False)
    detector_type: Mapped[str] = mapped_column(String(50), nullable=False, default='PERSON')
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    license_name: Mapped[str] = mapped_column(String(100), nullable=False)
    license_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    commercial_use: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # v1.0.0 — model registry / artifacts.
    artifact_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    artifact_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    framework: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model_stage: Mapped[str] = mapped_column(String(32), nullable=False, default='REGISTERED', index=True)
    input_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    class_map: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metrics_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class CameraVisionSetting(Base):
    __tablename__ = 'camera_vision_settings'
    __table_args__ = (UniqueConstraint('camera_id', name='uq_camera_vision_setting_camera'),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True
    )
    camera_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('cameras.id', ondelete='CASCADE'), nullable=False, index=True
    )
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('vision_model_versions.id', ondelete='RESTRICT'), nullable=False, index=True
    )

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    inference_fps: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    min_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.62)
    nms_iou_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.35)
    tracker_iou_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.25)
    tracker_max_missed_frames: Mapped[int] = mapped_column(Integer, nullable=False, default=4)

    # v0.4.1 — hardening PERSON. Todos los parámetros son por cámara y reemplazables.
    tracker_min_hits_to_confirm: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    min_box_area_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.015)
    max_box_area_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.18)
    min_height_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.18)
    min_aspect_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.28)
    max_aspect_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.95)
    top_band_reject_y_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.15)
    top_band_reject_bottom_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.62)

    # v0.5.0 — PPE por regiones anatómicas del mismo TRACK.
    ppe_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    ppe_model_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey('vision_model_versions.id', ondelete='RESTRICT'), nullable=True, index=True)
    ppe_min_visibility_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.70)
    ppe_uncertainty_margin: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)

    # v0.6.0 — cumplimiento temporal y deduplicación.
    compliance_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    compliance_window_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=4.0)
    compliance_min_persistence_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=2.0)
    compliance_min_consensus_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.70)
    compliance_min_missing_observations: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    compliance_cooldown_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=15.0)
    compliance_clear_grace_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    compliance_track_absence_close_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

