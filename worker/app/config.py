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
    yingdao_install_root: Path | None = None
    yingdao_data_root: Path | None = None
    yingdao_command_timeout_seconds: float = Field(default=15, ge=1, le=60)


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()  # type: ignore[call-arg]
