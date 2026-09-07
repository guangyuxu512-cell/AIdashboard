from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class DouyinSignRequest(BaseModel):
    """Request context consumed by the isolated Node signing process."""

    model_config = ConfigDict(extra="forbid")

    host: str | None = None
    full_url: str | None = None
    href: str | None = None
    url: str | None = None
    params: dict[str, Any] | None = None
    method: str | None = None
    cookie: SecretStr | None = None
    user_agent: str | None = None
    referer: str | None = None
    body: SecretStr | None = None
    ms_token: SecretStr | None = None
    aid: int | None = None
    page_id: int | None = None
    timeout_ms: int | None = Field(default=None, ge=1, le=30_000)
    child_timeout_ms: int | None = Field(default=None, ge=1, le=30_000)

    def signer_payload(self) -> dict[str, Any]:
        payload = self.model_dump(exclude_none=True)
        for field_name in ("cookie", "body", "ms_token"):
            value = payload.get(field_name)
            if isinstance(value, SecretStr):
                payload[field_name] = value.get_secret_value()
        return payload


class DouyinSignResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ok: bool
    a_bogus: SecretStr
    ms_token: SecretStr | None = Field(default=None, alias="msToken")
    duration_ms: int = Field(ge=0)
    version: str | None = None
