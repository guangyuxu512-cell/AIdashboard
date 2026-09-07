from __future__ import annotations

import logging
from time import monotonic
from typing import Any
from uuid import UUID

import httpx

from app.core.exceptions import AppError
from app.modules.sessions.auth_context import ShopSessionAuthContext, StoredSessionCookie
from app.modules.shops.enums import ShopPlatform
from app.platforms.exceptions import PlatformRequestFailedError, PlatformResponseInvalidError
from app.platforms.pdd.api_client import PddApiClient
from app.platforms.pdd.endpoints import MERCHANT_IDENTITY_ENDPOINT
from app.platforms.schemas import PlatformShopIdentity


logger = logging.getLogger(__name__)
MERCHANT_IDENTITY_URL = MERCHANT_IDENTITY_ENDPOINT.url
MERCHANT_IDENTITY_OPERATION = "fetch_shop_identity"
PDD_SUCCESS_CODE = 1_000_000


class PddPlatformConnector:
    """Verified PDD merchant identity request with fixed result paths."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        timeout_seconds: float = 30,
        api_client: PddApiClient | None = None,
    ) -> None:
        self.api_client = api_client or PddApiClient(
            client,
            timeout_seconds=timeout_seconds,
        )

    def fetch_shop_identity(
        self,
        shop_id: UUID,
        auth_context: ShopSessionAuthContext,
    ) -> PlatformShopIdentity:
        if auth_context.platform is not ShopPlatform.PDD:
            raise PlatformRequestFailedError("Connector 与 Session 平台不匹配")
        started_at = monotonic()
        try:
            return self.fetch_identity_from_cookies(auth_context.cookies)
        finally:
            logger.info(
                "platform_request operation=%s shop_id=%s platform=%s duration_ms=%s",
                MERCHANT_IDENTITY_OPERATION,
                shop_id,
                ShopPlatform.PDD.value,
                round((monotonic() - started_at) * 1000),
            )

    def fetch_identity_from_cookies(
        self,
        cookies: tuple[StoredSessionCookie, ...],
    ) -> PlatformShopIdentity:
        try:
            response = self.api_client.request_json(MERCHANT_IDENTITY_ENDPOINT, cookies)
            return self._parse_response(response.payload, response.cookie_updates)
        except AppError as error:
            details = error.details if isinstance(error.details, dict) else {}
            logger.warning(
                "pdd_identity_preflight_failed error_code=%s failure_stage=%s platform_code=%s",
                error.code,
                details.get("failure_stage", "unknown"),
                details.get("platform_code", "unknown"),
            )
            raise

    @staticmethod
    def _parse_response(
        payload: dict[str, Any],
        cookie_updates: tuple[StoredSessionCookie, ...],
    ) -> PlatformShopIdentity:
        platform_success = payload.get("success")
        platform_code = payload.get("errorCode")
        if platform_success is not True or platform_code not in {
            PDD_SUCCESS_CODE,
            str(PDD_SUCCESS_CODE),
        }:
            raise PlatformRequestFailedError(
                details={
                    "failure_stage": "platform_response",
                    "platform_code": _safe_scalar(platform_code),
                },
            )
        result = payload.get("result")
        if not isinstance(result, dict):
            raise PlatformResponseInvalidError(
                details={"failure_stage": "identity_parse"},
            )
        # `result` is the verified identity object. Keep these fixed paths;
        # do not recursively guess fields from other platform response shapes.
        platform_shop_id = str(result.get("mallId") or "").strip()
        shop_display_name = str(result.get("mallName") or "").strip()
        if not platform_shop_id or not shop_display_name:
            raise PlatformResponseInvalidError(
                details={"failure_stage": "identity_parse"},
            )
        return PlatformShopIdentity(
            platform_shop_id=platform_shop_id,
            shop_display_name=shop_display_name,
            cookie_updates=cookie_updates,
        )


def _safe_scalar(value: Any) -> str:
    if isinstance(value, (str, int, float, bool)):
        return str(value)[:64]
    return "unknown"
