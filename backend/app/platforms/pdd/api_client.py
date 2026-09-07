from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.modules.sessions.auth_context import StoredSessionCookie
from app.platforms.exceptions import (
    PlatformAuthenticationInvalidError,
    PlatformRequestFailedError,
    PlatformRequestTimeoutError,
    PlatformResponseInvalidError,
)
from app.platforms.pdd.endpoints import PddEndpoint
from app.platforms.pdd.signer import PddAntiContentSigner, PddAntiContentSignerError
from app.platforms.session_cookies import response_cookie_updates


@dataclass(frozen=True)
class PddApiResponse:
    payload: dict[str, Any]
    cookie_updates: tuple[StoredSessionCookie, ...]


class PddApiClient:
    """Session-aware PDD HTTP boundary with per-request anti-content."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        signer: PddAntiContentSigner | None = None,
        timeout_seconds: float = 30,
    ) -> None:
        self.client = client
        self.signer = signer or PddAntiContentSigner()
        self.timeout_seconds = timeout_seconds

    def request_json(
        self,
        endpoint: PddEndpoint,
        cookies: tuple[StoredSessionCookie, ...],
    ) -> PddApiResponse:
        try:
            anti_content = self.signer.generate()
        except PddAntiContentSignerError as error:
            raise PlatformRequestFailedError(
                details={"failure_stage": "signer"},
            ) from error

        headers = dict(endpoint.headers)
        headers["anti-content"] = anti_content.get_secret_value()
        # Electron has already selected the cookies applicable to this exact
        # PDD endpoint. Preserve that browser session context as one Cookie
        # header instead of applying a second client-side domain/path filter.
        headers["cookie"] = _cookie_header(cookies)
        try:
            if self.client is not None:
                response = self._request(self.client, endpoint, headers, cookies)
            else:
                with httpx.Client(
                    timeout=self.timeout_seconds,
                    follow_redirects=True,
                ) as client:
                    response = self._request(client, endpoint, headers, cookies)
        except httpx.TimeoutException as error:
            raise PlatformRequestTimeoutError(
                details={"failure_stage": "http_transport"},
            ) from error
        except httpx.RequestError as error:
            raise PlatformRequestFailedError(
                details={"failure_stage": "http_transport"},
            ) from error

        if response.status_code in {401, 403}:
            raise PlatformAuthenticationInvalidError()
        if response.status_code >= 400:
            raise PlatformRequestFailedError(
                details={
                    "failure_stage": "http_response",
                    "platform_http_status": response.status_code,
                },
            )
        try:
            payload = response.json()
        except ValueError as error:
            raise PlatformResponseInvalidError(
                details={"failure_stage": "json_parse"},
            ) from error
        if not isinstance(payload, dict):
            raise PlatformResponseInvalidError(
                details={"failure_stage": "json_shape"},
            )
        return PddApiResponse(
            payload=payload,
            cookie_updates=response_cookie_updates(response),
        )

    @staticmethod
    def _request(
        client: httpx.Client,
        endpoint: PddEndpoint,
        headers: dict[str, str],
        cookies: tuple[StoredSessionCookie, ...],
    ) -> httpx.Response:
        request = client.build_request(
            endpoint.method,
            endpoint.url,
            headers=headers,
            json={},
        )
        return client.send(request)


def _cookie_header(cookies: tuple[StoredSessionCookie, ...]) -> str:
    return "; ".join(
        f"{cookie.name}={cookie.value.get_secret_value()}" for cookie in cookies
    )
