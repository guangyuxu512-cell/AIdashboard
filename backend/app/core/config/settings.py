from functools import lru_cache
from pathlib import Path

from pydantic import Field, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="BACKEND_",
        extra="ignore",
    )

    database_url: PostgresDsn | None = None
    encryption_key: SecretStr | None = None
    asset_storage_dir: Path = Path("data/assets")
    asset_max_upload_bytes: int = Field(
        default=10 * 1024 * 1024,
        ge=1024,
        le=100 * 1024 * 1024,
    )
    worker_online_timeout_seconds: int = Field(default=45, ge=15, le=300)
    worker_task_lease_seconds: int = Field(default=60, ge=30, le=600)
    worker_reconcile_interval_seconds: int = Field(default=10, ge=1, le=60)
    task_event_retention_days: int = Field(default=90, ge=1, le=3650)
    task_event_retention_sweep_interval_seconds: int = Field(
        default=86400,
        ge=60,
        le=604800,
    )
    task_event_retention_batch_size: int = Field(default=100, ge=1, le=1000)
    schedule_scan_interval_seconds: int = Field(default=10, ge=1, le=300)
    schedule_trigger_batch_size: int = Field(default=50, ge=1, le=500)
    shop_session_validation_freshness_seconds: int = Field(
        default=300,
        ge=0,
        le=86400,
    )
    shop_session_refresh_lease_seconds: int = Field(
        default=1800,
        ge=60,
        le=3600,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
