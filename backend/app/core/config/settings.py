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


@lru_cache
def get_settings() -> Settings:
    return Settings()
