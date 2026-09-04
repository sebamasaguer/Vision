from datetime import datetime
from pydantic import BaseModel, Field

class ExecutiveKPI(BaseModel):
    period_from: datetime
    period_to: datetime
    total_events: int
    active_events: int
    critical_events: int
    high_events: int
    warning_events: int
    unique_tracks: int
    false_positive_rate: float
    evidence_coverage_rate: float
    ack_sla_met_rate: float
    resolution_sla_met_rate: float
    escalation_rate: float
    avg_ack_seconds: float | None = None
    avg_resolution_seconds: float | None = None
    compliance_rate: float | None = None
    archived_qa_events: int = 0

class TrendPoint(BaseModel):
    bucket: str
    events: int
    critical: int
    high: int
    warning: int
    false_positive: int
    escalated: int

class RiskItem(BaseModel):
    key: str
    label: str
    count: int
    share: float

class HeatmapZone(BaseModel):
    zone_id: str
    zone_code: str
    zone_name: str
    camera_id: str
    camera_code: str
    polygon_points: list[dict]
    event_count: int
    critical_count: int
    intensity: float

class CleanupStatus(BaseModel):
    total_runs: int
    last_run_at: datetime | None = None
    archived_events: int = 0
    compliance_enabled_cameras: int = 0
    qa_active_events: int = 0

class ExecutiveReport(BaseModel):
    generated_at: datetime
    title: str
    summary: ExecutiveKPI
    top_ppe: list[RiskItem]
    top_zones: list[RiskItem]
    top_cameras: list[RiskItem]
    recommendations: list[str]
