from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, PostgresDsn, SecretStr
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="BACKEND_",
        extra="ignore",
    )

    database_url: PostgresDsn | None = None
    encryption_key: SecretStr | None = None
    runtime_environment: Literal["development", "test", "production"] = "development"
    cors_allowed_origins: list[str] = Field(default_factory=list)
    human_session_ttl_seconds: int = Field(
        default=7 * 24 * 60 * 60,
        ge=5 * 60,
        le=30 * 24 * 60 * 60,
    )
    human_session_cookie_name: str = Field(
        default="siyu_human_session",
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    human_session_cookie_secure: bool = False
    human_session_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    human_session_cookie_path: str = Field(
        default="/api/v1",
        pattern=r"^/[^\s]*$",
    )
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
    ai_generation_scan_interval_seconds: float = Field(
        default=1.0,
        ge=0.1,
        le=60,
    )
    toapis_api_key: SecretStr | None = None
    toapis_base_url: str = "https://toapis.cn"
    toapis_model_code: Literal["gpt-image-2"] = "gpt-image-2"
    toapis_resolution: Literal["1k", "2k", "4k"] = "2k"
    toapis_quality: Literal["low", "medium", "high"] = "low"
    toapis_poll_interval_seconds: float = Field(default=5.0, ge=0.1, le=60)
    toapis_poll_timeout_seconds: int = Field(default=180, ge=10, le=3600)
    toapis_request_timeout_seconds: int = Field(default=180, ge=10, le=600)

    @field_validator("toapis_api_key", mode="before")
    @classmethod
    def normalize_optional_toapis_api_key(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("toapis_base_url")
    @classmethod
    def validate_toapis_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("ToAPIs Base URL必须是不含路径的HTTPS Origin")
        try:
            parsed.port
        except ValueError as error:
            raise ValueError("ToAPIs Base URL端口无效") from error
        return normalized

    @model_validator(mode="after")
    def validate_human_auth_transport(self) -> "Settings":
        normalized_origins: list[str] = []
        for origin in self.cors_allowed_origins:
            normalized = origin.strip().rstrip("/")
            if normalized == "*":
                raise ValueError("Credential CORS不允许使用通配Origin")
            parsed = urlsplit(normalized)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("CORS配置必须是完整且不含路径的HTTP Origin")
            try:
                parsed.port
            except ValueError as error:
                raise ValueError("CORS Origin端口无效") from error
            normalized_origins.append(
                f"{parsed.scheme.lower()}://{parsed.netloc.lower()}",
            )
        if len(set(normalized_origins)) != len(normalized_origins):
            raise ValueError("CORS Origin不能重复")
        if self.human_session_cookie_samesite == "none" and not (
            self.human_session_cookie_secure
        ):
            raise ValueError("SameSite=None要求Secure Cookie")
        if self.runtime_environment == "production" and not (
            self.human_session_cookie_secure
        ):
            raise ValueError("生产环境必须启用Human Session Secure Cookie")
        self.cors_allowed_origins = normalized_origins
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
