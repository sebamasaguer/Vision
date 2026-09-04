import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, model_validator
from app.schemas.common import ORMModel

CameraStatus = Literal["ONLINE", "OFFLINE", "DEGRADADA", "SIN_VIDEO", "ERROR_AUTENTICACION", "IA_DESACTIVADA"]
CameraSourceType = Literal["RTSP", "DEMO_FILE"]


class CameraCreate(BaseModel):
    sector_id: uuid.UUID
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=250)
    source_type: CameraSourceType = "RTSP"
    rtsp_url: str | None = Field(default=None, max_length=1000)
    username: str | None = Field(default=None, max_length=200)
    password: str | None = Field(default=None, max_length=500)
    manufacturer: str | None = Field(default=None, max_length=120)
    model_name: str | None = Field(default=None, max_length=120)
    configured_width: int | None = Field(default=None, ge=160, le=16384)
    configured_height: int | None = Field(default=None, ge=120, le=16384)
    source_fps: float | None = Field(default=None, gt=0, le=240)
    capture_fps: float = Field(default=5.0, ge=0.2, le=30)
    active: bool = True
    ai_enabled: bool = False

    @model_validator(mode="after")
    def validate_source(self):
        if self.source_type == "RTSP":
            if not self.rtsp_url or not self.rtsp_url.lower().startswith(("rtsp://", "rtsps://")):
                raise ValueError("Una cámara RTSP requiere rtsp_url con esquema rtsp:// o rtsps://")
        return self


class CameraUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=250)
    rtsp_url: str | None = Field(default=None, max_length=1000)
    username: str | None = Field(default=None, max_length=200)
    password: str | None = Field(default=None, max_length=500)
    manufacturer: str | None = Field(default=None, max_length=120)
    model_name: str | None = Field(default=None, max_length=120)
    capture_fps: float | None = Field(default=None, ge=0.2, le=30)
    active: bool | None = None
    ai_enabled: bool | None = None


class CameraOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    site_id: uuid.UUID
    plant_id: uuid.UUID
    sector_id: uuid.UUID
    code: str
    name: str
    description: str | None
    location: str | None
    source_type: str
    rtsp_url_masked: str | None = None
    credentials_configured: bool = False
    manufacturer: str | None
    model_name: str | None
    configured_width: int | None
    configured_height: int | None
    source_fps: float | None
    capture_fps: float
    measured_fps: float | None
    latency_ms: float | None
    status: str
    active: bool
    ai_enabled: bool
    last_connection_at: datetime | None
    last_frame_at: datetime | None
    last_status_change_at: datetime
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class CameraSummary(BaseModel):
    total: int
    online: int
    offline: int
    degraded: int
    no_video: int
    auth_error: int
    demo: int


class CameraWorkerStatus(BaseModel):
    status: str
    heartbeat_age_seconds: float | None
