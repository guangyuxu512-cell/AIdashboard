from functools import lru_cache

from pydantic import PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="BACKEND_",
        extra="ignore",
    )

    database_url: PostgresDsn | None = None
    encryption_key: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
