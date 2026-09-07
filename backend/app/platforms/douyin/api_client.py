from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

import httpx
from pydantic import SecretStr

from app.integrations.douyin_signer import (
    DouyinSignerAuthenticationError,
    DouyinSignerClient,
    DouyinSignerConfigurationError,
    DouyinSignerResponseError,
    DouyinSignerUnavailableError,
    DouyinSignRequest,
)
from app.modules.sessions.auth_context import ShopSessionAuthContext, StoredSessionCookie
from app.platforms.douyin.endpoints import DouyinEndpoint
from app.platforms.exceptions import (
    PlatformAuthenticationInvalidError,
    PlatformRequestFailedError,
    PlatformRequestTimeoutError,
    PlatformResponseInvalidError,
)
from app.platforms.session_cookies import response_cookie_updates, to_httpx_cookies


@dataclass(frozen=True)
class DouyinApiResponse:
    payload: dict[str, Any]
    cookie_updates: tuple[StoredSessionCookie, ...]


class DouyinApiClient:
    """Session-aware Douyin HTTP boundary with endpoint-scoped signing."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        signer: DouyinSignerClient | None = None,
        timeout_seconds: float = 15,
    ) -> None:
        self.client = client
        self.signer = signer
        self.timeout_seconds = timeout_seconds

    def request_json(
        self,
        endpoint: DouyinEndpoint,
        auth_context: ShopSessionAuthContext,
        *,
        query: Mapping[str, str | int | bool] | None = None,
        body: Mapping[str, Any] | None = None,
    ) -> DouyinApiResponse:
        cookies = to_httpx_cookies(auth_context.cookies)
        headers = dict(endpoint.headers)
        params = dict(query or {})
        try:
            if self.client is not None:
                response = self._request(
                    self.client,
                    endpoint,
                    cookies,
                    auth_context,
                    headers,
                    params,
                    body,
                )
            else:
                with httpx.Client(
                    timeout=self.timeout_seconds,
                    follow_redirects=False,
                ) as client:
                    response = self._request(
                        client,
                        endpoint,
                        cookies,
                        auth_context,
                        headers,
                        params,
                        body,
                    )
        except httpx.TimeoutException as error:
            raise PlatformRequestTimeoutError() from error
        except httpx.RequestError as error:
            raise PlatformRequestFailedError() from error

        if response.status_code in {401, 403}:
            raise PlatformAuthenticationInvalidError()
        if response.status_code >= 400:
            raise PlatformRequestFailedError(
                details={"platform_http_status": response.status_code},
            )
        try:
            payload = response.json()
        except ValueError as error:
            raise PlatformResponseInvalidError() from error
        if not isinstance(payload, dict):
            raise PlatformResponseInvalidError()
        return DouyinApiResponse(
            payload=payload,
            cookie_updates=response_cookie_updates(response),
        )

    def _request(
        self,
        client: httpx.Client,
        endpoint: DouyinEndpoint,
        cookies: httpx.Cookies,
        auth_context: ShopSessionAuthContext,
        headers: dict[str, str],
        params: dict[str, str | int | bool],
        body: Mapping[str, Any] | None,
    ) -> httpx.Response:
        unsigned_request = client.build_request(
            endpoint.method,
            endpoint.url,
            headers=headers,
            cookies=cookies,
            params=params,
            json=body,
        )
        if not endpoint.sign_required:
            return client.send(unsigned_request)

        signer = self.signer or DouyinSignerClient()
        try:
            sign_result = signer.sign(
                DouyinSignRequest(
                    host=endpoint.host,
                    full_url=str(unsigned_request.url),
                    method=endpoint.method,
                    cookie=SecretStr(_cookie_header(auth_context)),
                    user_agent=headers.get("user-agent"),
                    referer=endpoint.referer,
                    body=(
                        SecretStr(json.dumps(body, separators=(",", ":")))
                        if body is not None
                        else None
                    ),
                    aid=endpoint.aid,
                    page_id=endpoint.page_id,
                )
            )
        except (
            DouyinSignerAuthenticationError,
            DouyinSignerConfigurationError,
            DouyinSignerResponseError,
            DouyinSignerUnavailableError,
        ) as error:
            raise PlatformRequestFailedError() from error

        signed_request = client.build_request(
            endpoint.method,
            endpoint.url,
            headers=headers,
            cookies=cookies,
            params={**params, "a_bogus": sign_result.a_bogus.get_secret_value()},
            json=body,
        )
        return client.send(signed_request)


def _cookie_header(auth_context: ShopSessionAuthContext) -> str:
    return "; ".join(
        f"{cookie.name}={cookie.value.get_secret_value()}"
        for cookie in auth_context.cookies
    )
