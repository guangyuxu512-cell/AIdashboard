from __future__ import annotations

import logging
from time import monotonic
from typing import Any
from uuid import UUID

import httpx
from pydantic import SecretStr

from app.modules.sessions.auth_context import (
    ShopSessionAuthContext,
    StoredSessionCookie,
)
from app.modules.shops.enums import ShopPlatform
from app.platforms.exceptions import (
    PlatformAuthenticationInvalidError,
    PlatformRequestFailedError,
    PlatformRequestTimeoutError,
    PlatformResponseInvalidError,
)
from app.platforms.schemas import PlatformShopIdentity


logger = logging.getLogger(__name__)

SHOP_INFO_URL = (
    "https://compass.jinritemai.com/compass_api/shop/mall/common/shop_info_v2"
)
SHOP_INFO_OPERATION = "fetch_shop_identity"
ACCEPT_HEADER = "application/json, text/plain, */*"


class DouyinPlatformConnector:
    """Verified read-only shop identity request from the Douyin Compass page."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        timeout_seconds: float = 15,
    ) -> None:
        self.client = client
        self.timeout_seconds = timeout_seconds

    def fetch_shop_identity(
        self,
        shop_id: UUID,
        auth_context: ShopSessionAuthContext,
    ) -> PlatformShopIdentity:
        if auth_context.platform is not ShopPlatform.DOUYIN:
            raise PlatformRequestFailedError("Connector 与 Session 平台不匹配")

        started_at = monotonic()
        status_code = 0
        try:
            if self.client is not None:
                response = self._request(self.client, auth_context)
            else:
                with httpx.Client(
                    timeout=self.timeout_seconds,
                    follow_redirects=False,
                ) as client:
                    response = self._request(client, auth_context)
            status_code = response.status_code
            return self._parse_response(response)
        except httpx.TimeoutException as error:
            raise PlatformRequestTimeoutError() from error
        except httpx.RequestError as error:
            raise PlatformRequestFailedError() from error
        finally:
            logger.info(
                "platform_request operation=%s shop_id=%s platform=%s status=%s duration_ms=%s",
                SHOP_INFO_OPERATION,
                shop_id,
                ShopPlatform.DOUYIN.value,
                status_code,
                round((monotonic() - started_at) * 1000),
            )

    def _request(
        self,
        client: httpx.Client,
        auth_context: ShopSessionAuthContext,
    ) -> httpx.Response:
        cookies = httpx.Cookies()
        for cookie in auth_context.cookies:
            if cookie.domain:
                cookies.set(
                    cookie.name,
                    cookie.value.get_secret_value(),
                    domain=cookie.domain,
                    path=cookie.path,
                )
            else:
                cookies.set(
                    cookie.name,
                    cookie.value.get_secret_value(),
                    path=cookie.path,
                )
        request = client.build_request(
            "GET",
            SHOP_INFO_URL,
            headers={"accept": ACCEPT_HEADER},
            cookies=cookies,
        )
        return client.send(request)

    @staticmethod
    def _parse_response(response: httpx.Response) -> PlatformShopIdentity:
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

        platform_code = payload.get("st")
        if platform_code not in (None, 0, "0"):
            raise PlatformRequestFailedError(
                details={"platform_code": _safe_scalar(platform_code)},
            )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise PlatformResponseInvalidError()
        platform_shop_id = str(data.get("shop_id") or "").strip()
        shop_display_name = str(data.get("shop_name") or "").strip()
        if not platform_shop_id or not shop_display_name:
            raise PlatformResponseInvalidError()
        return PlatformShopIdentity(
            platform_shop_id=platform_shop_id,
            shop_display_name=shop_display_name,
            cookie_updates=_response_cookie_updates(response),
        )


def _safe_scalar(value: Any) -> str:
    if isinstance(value, (str, int, float, bool)):
        return str(value)[:64]
    return "unknown"


def _response_cookie_updates(
    response: httpx.Response,
) -> tuple[StoredSessionCookie, ...]:
    updates: list[StoredSessionCookie] = []
    for cookie in response.cookies.jar:
        rest = {str(key).lower(): value for key, value in cookie._rest.items()}
        same_site = rest.get("samesite")
        updates.append(
            StoredSessionCookie(
                name=cookie.name,
                value=SecretStr(cookie.value),
                domain=cookie.domain or None,
                path=cookie.path or "/",
                secure=cookie.secure,
                httpOnly="httponly" in rest,
                sameSite=str(same_site) if same_site is not None else None,
                expirationDate=float(cookie.expires) if cookie.expires is not None else None,
            ),
        )
    return tuple(updates)
