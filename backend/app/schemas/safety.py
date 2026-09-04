import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import ORMModel

Severity = Literal["INFO", "ADVERTENCIA", "ALTA", "CRITICA"]
Requirement = Literal["REQUIRED", "OPTIONAL", "NOT_APPLICABLE"]


class PolygonPoint(BaseModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)


def _validate_polygon(points: list[PolygonPoint]) -> list[PolygonPoint]:
    if len(points) < 3:
        raise ValueError("La zona debe tener al menos 3 puntos")
    if len(points) > 64:
        raise ValueError("La zona no puede superar 64 puntos")
    # Área por fórmula del cordón. Evita polígonos colineales o prácticamente nulos.
    area2 = 0.0
    for i, p in enumerate(points):
        q = points[(i + 1) % len(points)]
        area2 += p.x * q.y - q.x * p.y
    if abs(area2) / 2.0 < 0.00005:
        raise ValueError("El polígono de la zona tiene un área demasiado pequeña")
    return points


class PPETypeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=600)
    icon: str | None = Field(default=None, max_length=80)
    active: bool = True
    criticality: Severity = "ADVERTENCIA"
    color: str = Field(default="#4fe2b6", pattern=r"^#[0-9A-Fa-f]{6}$")
    detector_class: str | None = Field(default=None, max_length=120)
    min_confidence: float = Field(default=0.70, ge=0.0, le=1.0)
    notes: str | None = Field(default=None, max_length=2000)


class PPETypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=600)
    icon: str | None = Field(default=None, max_length=80)
    active: bool | None = None
    criticality: Severity | None = None
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    detector_class: str | None = Field(default=None, max_length=120)
    min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: str | None = Field(default=None, max_length=2000)


class PPETypeOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    icon: str | None
    active: bool
    criticality: str
    color: str
    detector_class: str | None
    min_confidence: float
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ZoneCreate(BaseModel):
    camera_id: uuid.UUID
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=600)
    polygon_points: list[PolygonPoint]
    active: bool = True

    @field_validator("polygon_points")
    @classmethod
    def validate_polygon(cls, value):
        return _validate_polygon(value)


class ZoneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=600)
    polygon_points: list[PolygonPoint] | None = None
    active: bool | None = None

    @field_validator("polygon_points")
    @classmethod
    def validate_polygon(cls, value):
        if value is None:
            return value
        return _validate_polygon(value)


class ZoneOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    site_id: uuid.UUID
    plant_id: uuid.UUID
    sector_id: uuid.UUID
    camera_id: uuid.UUID
    code: str
    name: str
    description: str | None
    polygon_points: list[dict]
    active: bool
    created_at: datetime
    updated_at: datetime


class ZoneRuleInput(BaseModel):
    ppe_type_id: uuid.UUID
    requirement: Requirement = "REQUIRED"
    severity: Severity = "ADVERTENCIA"
    min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    schedule_start: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    schedule_end: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    task: str | None = Field(default=None, max_length=180)
    risk_level: str | None = Field(default=None, max_length=80)
    operation_type: str | None = Field(default=None, max_length=120)
    active: bool = True


class ZoneRuleSet(BaseModel):
    rules: list[ZoneRuleInput] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def unique_ppe(self):
        ids = [x.ppe_type_id for x in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("No se puede repetir el mismo EPP en una zona")
        return self


class ZoneRuleOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    zone_id: uuid.UUID
    ppe_type_id: uuid.UUID
    ppe_code: str
    ppe_name: str
    requirement: str
    severity: str
    min_confidence: float | None
    effective_min_confidence: float
    schedule_start: str | None
    schedule_end: str | None
    task: str | None
    risk_level: str | None
    operation_type: str | None
    active: bool
    created_at: datetime
    updated_at: datetime
