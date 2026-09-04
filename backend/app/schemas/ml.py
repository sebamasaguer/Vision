import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class DatasetCreate(BaseModel):
    organization_id: uuid.UUID | None = None
    code: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=180)
    description: str | None = None
    license_name: str = 'PROPRIETARY-HYS'
    source_url: str | None = None


class DatasetVersionCreate(BaseModel):
    version: str = Field(min_length=1, max_length=50)
    classes: list[str]
    image_count: int = 0
    annotation_count: int = 0
    train_count: int = 0
    val_count: int = 0
    test_count: int = 0
    manifest_sha256: str | None = None
    storage_path: str | None = None
    notes: str | None = None
    freeze: bool = True


class TrainingRunCreate(BaseModel):
    dataset_version_id: uuid.UUID
    base_model: str = 'yolox_nano'
    epochs: int = Field(default=30, ge=1, le=1000)
    image_size: int = Field(default=640, ge=160, le=1536)
    batch_size: int = Field(default=8, ge=1, le=256)
    device: str = 'cpu'


class ModelRegisterRequest(BaseModel):
    organization_id: uuid.UUID | None = None
    code: str
    name: str
    version: str
    backend: str = 'onnx_yolox_ppe'
    artifact_uri: str
    artifact_sha256: str
    class_map: dict[str, str]
    input_width: int = 640
    input_height: int = 640
    metrics: dict | None = None
    dataset_version_id: uuid.UUID | None = None
    license_name: str = 'HYS-PROPRIETARY'
    license_url: str | None = None


class DeploymentRequest(BaseModel):
    model_version_id: uuid.UUID
    camera_id: uuid.UUID | None = None
    mode: str = Field(pattern='^(SHADOW|PRODUCTION)$')


class BootstrapActivateRequest(BaseModel):
    artifact_uri: str = 'bootstrap/intel-worker-safety/model.xml'
    artifact_sha256: str | None = None


class ShadowSummary(BaseModel):
    samples: int
    agreements: int
    agreement_ratio: float
    by_ppe: dict
