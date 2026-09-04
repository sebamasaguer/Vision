from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "HYS Vision IA"
    app_env: str = "development"
    app_version: str = "1.1.0"
    database_url: str = "sqlite:///./hysvision.db"
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minio"
    minio_secret_key: str = "miniosecret"
    minio_secure: bool = False
    minio_bucket_evidence: str = "hys-evidence"
    jwt_secret: str = Field(default="dev-only-change-me", min_length=16)
    jwt_algorithm: str = "HS256"
    jwt_access_minutes: int = 480
    bootstrap_admin_email: str = "admin@hysvision.app"
    bootstrap_admin_password: str = "change-me-now"
    cors_origins: list[str] = ["http://localhost:5200"]
    camera_credential_key: str = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
    camera_poll_interval_seconds: float = 3.0
    camera_frame_ttl_seconds: int = 10
    demo_video_path: str = "/demo/demo_camera.mp4"
    vision_result_ttl_seconds: int = 10
    hys_model_root: str = "/opt/hys-models"
    hys_dataset_root: str = "/opt/hys-datasets"
    ml_shadow_sample_seconds: float = 2.0
    app_timezone: str = "America/Argentina/Salta"
    alert_poll_interval_seconds: float = 5.0
    alert_external_timeout_seconds: float = 5.0
    alert_smtp_host: str | None = None
    alert_smtp_port: int = 587
    alert_smtp_user: str | None = None
    alert_smtp_password: str | None = None
    alert_smtp_from: str | None = None
    alert_smtp_starttls: bool = True
    alert_webhook_bearer_token: str | None = None
    alert_whatsapp_webhook_url: str | None = None
    alert_whatsapp_bearer_token: str | None = None
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

@lru_cache

def get_settings() -> Settings:
    return Settings()

settings = get_settings()
