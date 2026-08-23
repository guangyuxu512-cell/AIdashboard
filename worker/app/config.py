from functools import lru_cache
from pathlib import Path
from uuid import UUID

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="WORKER_",
        extra="ignore",
    )

    server_url: AnyHttpUrl
    device_id: UUID
    device_token: SecretStr
    heartbeat_interval_seconds: float = Field(default=15, ge=1, le=300)
    poll_interval_seconds: float = Field(default=3, ge=0.2, le=60)
    lease_renew_interval_seconds: float = Field(default=20, ge=1, le=300)
    request_timeout_seconds: float = Field(default=10, ge=1, le=60)
    runtime_root: Path = Path("runtime")
    log_directory: Path = Path("logs")
    log_max_bytes: int = Field(
        default=5 * 1024 * 1024,
        ge=1024,
        le=100 * 1024 * 1024,
    )
    log_backup_count: int = Field(default=5, ge=1, le=20)
    yingdao_install_root: Path | None = None
    yingdao_data_root: Path | None = None
    yingdao_test_app_id: str | None = None
    yingdao_startup_timeout_seconds: float = Field(default=30, ge=5, le=120)
    provider_inventory_interval_seconds: float = Field(default=60, ge=10, le=3600)
    event_flush_interval_seconds: float = Field(default=0.4, ge=0.1, le=5)
    event_batch_size: int = Field(default=30, ge=1, le=100)
    event_buffer_capacity: int = Field(default=2_000, ge=100, le=20_000)
    event_flush_retry_count: int = Field(default=3, ge=1, le=10)
    runtime_status_path: Path = Path("runtime-status.json")


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()  # type: ignore[call-arg]
