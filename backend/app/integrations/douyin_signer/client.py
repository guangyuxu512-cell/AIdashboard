from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import httpx
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.integrations.douyin_signer.exceptions import (
    DouyinSignerAuthenticationError,
    DouyinSignerConfigurationError,
    DouyinSignerResponseError,
    DouyinSignerUnavailableError,
)
from app.integrations.douyin_signer.schemas import DouyinSignRequest, DouyinSignResult


class DouyinSignerClient:
    """Internal-only client for the isolated Douyin Node signer service."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client = client

    def sign(self, request: DouyinSignRequest) -> DouyinSignResult:
        api_key = self._settings.douyin_signer_api_key
        if api_key is None:
            raise DouyinSignerConfigurationError()
        try:
            with self._client_scope() as client:
                response = client.post(
                    f"{self._settings.douyin_signer_url}/sign",
                    headers={"X-API-Key": api_key.get_secret_value()},
                    json=request.signer_payload(),
                    timeout=self._settings.douyin_signer_timeout_seconds,
                    follow_redirects=False,
                )
        except httpx.TimeoutException:
            raise DouyinSignerUnavailableError() from None
        except httpx.RequestError:
            raise DouyinSignerUnavailableError() from None

        if response.status_code in {401, 403}:
            raise DouyinSignerAuthenticationError()
        if response.status_code >= 500:
            raise DouyinSignerUnavailableError()
        if response.status_code >= 400:
            raise DouyinSignerResponseError()
        try:
            payload = response.json()
        except ValueError:
            raise DouyinSignerResponseError() from None
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            raise DouyinSignerResponseError()
        try:
            return DouyinSignResult.model_validate(payload)
        except ValidationError:
            raise DouyinSignerResponseError() from None

    @contextmanager
    def _client_scope(self) -> Iterator[httpx.Client]:
        if self._client is not None:
            yield self._client
            return
        with httpx.Client() as client:
            yield client
