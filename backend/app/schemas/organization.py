import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from app.schemas.common import ORMModel

class OrganizationCreate(BaseModel):
    code: str = Field(min_length=2, max_length=50)
    name: str = Field(min_length=2, max_length=200)
class OrganizationOut(ORMModel):
    id: uuid.UUID; code: str; name: str; active: bool; created_at: datetime

class SiteCreate(BaseModel):
    organization_id: uuid.UUID
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=2, max_length=200)
    address: str | None = Field(default=None, max_length=300)
class SiteOut(ORMModel):
    id: uuid.UUID; organization_id: uuid.UUID; code: str; name: str; address: str | None; active: bool

class PlantCreate(BaseModel):
    site_id: uuid.UUID
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=2, max_length=200)
class PlantOut(ORMModel):
    id: uuid.UUID; organization_id: uuid.UUID; site_id: uuid.UUID; code: str; name: str; active: bool

class SectorCreate(BaseModel):
    plant_id: uuid.UUID
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=500)
class SectorOut(ORMModel):
    id: uuid.UUID; organization_id: uuid.UUID; site_id: uuid.UUID; plant_id: uuid.UUID; code: str; name: str; description: str | None; active: bool
