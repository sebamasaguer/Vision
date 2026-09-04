import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class MLDatasetFrame(Base):
    __tablename__ = 'ml_dataset_frames'

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True)
    dataset_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('ml_datasets.id', ondelete='CASCADE'), nullable=False, index=True)
    camera_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey('cameras.id', ondelete='SET NULL'), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(24), nullable=False, default='UPLOAD', index=True)
    source_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    frame_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    curation_status: Mapped[str] = mapped_column(String(24), nullable=False, default='PENDING', index=True)
    ground_truth_status: Mapped[str] = mapped_column(String(24), nullable=False, default='UNLABELED', index=True)
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey('ml_dataset_frames.id', ondelete='SET NULL'), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class MLGroundTruthAnnotation(Base):
    __tablename__ = 'ml_ground_truth_annotations'

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    frame_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('ml_dataset_frames.id', ondelete='CASCADE'), nullable=False, index=True)
    class_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    width: Mapped[float] = mapped_column(Float, nullable=False)
    height: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(24), nullable=False, default='MANUAL')
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class MLEvaluationRun(Base):
    __tablename__ = 'ml_evaluation_runs'

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True)
    dataset_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('ml_datasets.id', ondelete='CASCADE'), nullable=False, index=True)
    model_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('vision_model_versions.id', ondelete='RESTRICT'), nullable=False, index=True)
    camera_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey('cameras.id', ondelete='SET NULL'), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default='QUEUED', index=True)
    iou_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.50)
    confidence_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.35)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
