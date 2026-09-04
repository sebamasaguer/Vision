import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class Camera(Base):
    __tablename__ = "cameras"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_cameras_org_code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    site_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)
    plant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("plants.id", ondelete="CASCADE"), nullable=False, index=True)
    sector_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("sectors.id", ondelete="CASCADE"), nullable=False, index=True)

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    location: Mapped[str | None] = mapped_column(String(250), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="RTSP")
    source_url_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    username_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    configured_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    configured_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    capture_fps: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    measured_fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OFFLINE", index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_connection_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_frame_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_status_change_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
