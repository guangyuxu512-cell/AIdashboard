from __future__ import annotations

import logging
from time import monotonic
from typing import Any
from uuid import UUID

import httpx

from app.modules.sessions.auth_context import ShopSessionAuthContext, StoredSessionCookie
from app.modules.shops.enums import ShopPlatform
from app.platforms.douyin.api_client import DouyinApiClient
from app.platforms.douyin.endpoints import SHOP_INFO_V2_ENDPOINT
from app.platforms.exceptions import PlatformRequestFailedError, PlatformResponseInvalidError
from app.platforms.schemas import PlatformShopIdentity


logger = logging.getLogger(__name__)

SHOP_INFO_URL = SHOP_INFO_V2_ENDPOINT.url
SHOP_INFO_OPERATION = "fetch_shop_identity"
ACCEPT_HEADER = "application/json, text/plain, */*"


class DouyinPlatformConnector:
    """Verified read-only shop identity request from the Douyin Compass page."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        timeout_seconds: float = 15,
        api_client: DouyinApiClient | None = None,
    ) -> None:
        self.api_client = api_client or DouyinApiClient(
            client,
            timeout_seconds=timeout_seconds,
        )

    def fetch_shop_identity(
        self,
        shop_id: UUID,
        auth_context: ShopSessionAuthContext,
    ) -> PlatformShopIdentity:
        if auth_context.platform is not ShopPlatform.DOUYIN:
            raise PlatformRequestFailedError("Connector 与 Session 平台不匹配")

        started_at = monotonic()
        try:
            response = self.api_client.request_json(
                SHOP_INFO_V2_ENDPOINT,
                auth_context,
            )
            return self._parse_response(response.payload, response.cookie_updates)
        finally:
            logger.info(
                "platform_request operation=%s shop_id=%s platform=%s duration_ms=%s",
                SHOP_INFO_OPERATION,
                shop_id,
                ShopPlatform.DOUYIN.value,
                round((monotonic() - started_at) * 1000),
            )

    @staticmethod
    def _parse_response(
        payload: dict[str, Any],
        cookie_updates: tuple[StoredSessionCookie, ...],
    ) -> PlatformShopIdentity:
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
            cookie_updates=cookie_updates,
        )


def _safe_scalar(value: Any) -> str:
    if isinstance(value, (str, int, float, bool)):
        return str(value)[:64]
    return "unknown"
