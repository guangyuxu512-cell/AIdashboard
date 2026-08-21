from functools import lru_cache

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
    worker_online_timeout_seconds: int = Field(default=45, ge=15, le=300)
    worker_task_lease_seconds: int = Field(default=60, ge=30, le=600)
    worker_reconcile_interval_seconds: int = Field(default=10, ge=1, le=60)
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
