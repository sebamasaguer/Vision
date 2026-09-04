import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class MLDataset(Base):
    __tablename__ = 'ml_datasets'
    __table_args__ = (UniqueConstraint('organization_id', 'code', name='uq_ml_dataset_org_code'),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    license_name: Mapped[str] = mapped_column(String(100), nullable=False, default='PROPRIETARY-HYS')
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class MLDatasetVersion(Base):
    __tablename__ = 'ml_dataset_versions'
    __table_args__ = (UniqueConstraint('dataset_id', 'version', name='uq_ml_dataset_version'),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('ml_datasets.id', ondelete='CASCADE'), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default='DRAFT', index=True)
    classes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    image_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    annotation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    train_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    val_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    test_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    manifest_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MLTrainingRun(Base):
    __tablename__ = 'ml_training_runs'

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True)
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('ml_dataset_versions.id', ondelete='RESTRICT'), nullable=False, index=True)
    model_family: Mapped[str] = mapped_column(String(80), nullable=False, default='YOLOX')
    base_model: Mapped[str] = mapped_column(String(80), nullable=False, default='yolox_nano')
    status: Mapped[str] = mapped_column(String(24), nullable=False, default='QUEUED', index=True)
    epochs: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    image_size: Mapped[int] = mapped_column(Integer, nullable=False, default=640)
    batch_size: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    device: Mapped[str] = mapped_column(String(40), nullable=False, default='cpu')
    command_line: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_model_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey('vision_model_versions.id', ondelete='SET NULL'), nullable=True, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MLModelDeployment(Base):
    __tablename__ = 'ml_model_deployments'

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True)
    camera_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey('cameras.id', ondelete='CASCADE'), nullable=True, index=True)
    model_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('vision_model_versions.id', ondelete='RESTRICT'), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(24), nullable=False, index=True)  # SHADOW | PRODUCTION
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)


class MLShadowObservation(Base):
    __tablename__ = 'ml_shadow_observations'

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True)
    camera_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('cameras.id', ondelete='CASCADE'), nullable=False, index=True)
    deployment_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('ml_model_deployments.id', ondelete='CASCADE'), nullable=False, index=True)
    track_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    ppe_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    baseline_status: Mapped[str] = mapped_column(String(32), nullable=False)
    candidate_status: Mapped[str] = mapped_column(String(32), nullable=False)
    baseline_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    candidate_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    agreement: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
