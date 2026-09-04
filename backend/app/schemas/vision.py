from pydantic import BaseModel, Field, model_validator


class VisionSettingsUpdate(BaseModel):
    enabled: bool | None = None
    inference_fps: float | None = Field(default=None, ge=0.2, le=10)
    min_confidence: float | None = Field(default=None, ge=0.05, le=0.99)
    nms_iou_threshold: float | None = Field(default=None, ge=0.05, le=0.95)
    tracker_iou_threshold: float | None = Field(default=None, ge=0.01, le=0.95)
    tracker_max_missed_frames: int | None = Field(default=None, ge=1, le=60)
    tracker_min_hits_to_confirm: int | None = Field(default=None, ge=2, le=20)
    min_box_area_ratio: float | None = Field(default=None, ge=0.0005, le=0.50)
    max_box_area_ratio: float | None = Field(default=None, ge=0.01, le=1.0)
    min_height_ratio: float | None = Field(default=None, ge=0.02, le=0.95)
    min_aspect_ratio: float | None = Field(default=None, ge=0.05, le=2.0)
    max_aspect_ratio: float | None = Field(default=None, ge=0.10, le=4.0)
    top_band_reject_y_ratio: float | None = Field(default=None, ge=0.0, le=0.50)
    top_band_reject_bottom_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    ppe_enabled: bool | None = None
    ppe_min_visibility_ratio: float | None = Field(default=None, ge=0.25, le=1.0)
    ppe_uncertainty_margin: float | None = Field(default=None, ge=0.0, le=0.30)
    compliance_enabled: bool | None = None
    compliance_window_seconds: float | None = Field(default=None, ge=1.0, le=60.0)
    compliance_min_persistence_seconds: float | None = Field(default=None, ge=0.2, le=30.0)
    compliance_min_consensus_ratio: float | None = Field(default=None, ge=0.50, le=1.0)
    compliance_min_missing_observations: int | None = Field(default=None, ge=2, le=100)
    compliance_cooldown_seconds: float | None = Field(default=None, ge=0.0, le=3600.0)
    compliance_clear_grace_seconds: float | None = Field(default=None, ge=0.0, le=30.0)
    compliance_track_absence_close_seconds: float | None = Field(default=None, ge=0.5, le=60.0)

    @model_validator(mode='after')
    def validate_pairs(self):
        if self.min_box_area_ratio is not None and self.max_box_area_ratio is not None:
            if self.min_box_area_ratio >= self.max_box_area_ratio:
                raise ValueError('min_box_area_ratio debe ser menor que max_box_area_ratio')
        if self.min_aspect_ratio is not None and self.max_aspect_ratio is not None:
            if self.min_aspect_ratio >= self.max_aspect_ratio:
                raise ValueError('min_aspect_ratio debe ser menor que max_aspect_ratio')
        if self.compliance_window_seconds is not None and self.compliance_min_persistence_seconds is not None:
            if self.compliance_min_persistence_seconds > self.compliance_window_seconds:
                raise ValueError('compliance_min_persistence_seconds no puede superar compliance_window_seconds')
        return self


class VisionWorkerStatus(BaseModel):
    status: str
    heartbeat_age_seconds: float | None = None
    backend: str | None = None
