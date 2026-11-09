"""Verify both identities on one immutable application-session snapshot."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from app.modules.sessions.auth_context import ShopSessionAuthContext
from app.modules.shops.enums import ShopPlatform
from app.platforms.douyin.endpoints import MERCHANT_IDENTITY_ENDPOINT, SHOP_INFO_V2_ENDPOINT
from app.platforms.session_cookies import to_httpx_cookies


MERCHANT_VERIFICATION_TOTAL_SECONDS = 4.0
_MAX_RESPONSE_BYTES = 256 * 1024
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/148.0.0.0 Safari/537.36"
)


class MerchantIdentityUnverified(Exception):
    """No confirmed same-shop identity; no Session may be released."""


class MerchantIdentityMismatch(MerchantIdentityUnverified):
    """A platform identity was returned and differs from the target."""


class MerchantValidationUnavailable(Exception):
    """The platform check could not be completed; no Session may be released."""


async def verify_merchant_session(
    context: ShopSessionAuthContext,
    target_platform_shop_id: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    total_seconds: float = MERCHANT_VERIFICATION_TOTAL_SECONDS,
    compass_already_verified: bool = False,
) -> None:
    if context.platform is not ShopPlatform.DOUYIN or not target_platform_shop_id:
        raise MerchantIdentityUnverified()
    try:
        async with asyncio.timeout(total_seconds):
            if not compass_already_verified:
                compass = await _request_identity(
                    SHOP_INFO_V2_ENDPOINT.url, "https://compass.jinritemai.com/shop", context, transport,
                )
                compass_status = compass.get("st")
                if compass_status in (10008, "10008"):
                    raise MerchantIdentityUnverified()
                if isinstance(compass_status, bool) or compass_status not in (None, 0, "0"):
                    raise MerchantValidationUnavailable()
                compass_data = compass.get("data")
                compass_id = _shop_id(compass_data.get("shop_id")) if isinstance(compass_data, dict) else None
                if not compass_id:
                    raise MerchantIdentityUnverified()
                if compass_id != target_platform_shop_id:
                    raise MerchantIdentityMismatch()

            merchant = await _request_identity(
                MERCHANT_IDENTITY_ENDPOINT.url, MERCHANT_IDENTITY_ENDPOINT.referer or "", context, transport,
            )
            code = merchant.get("code")
            if code in (10008, "10008"):
                # Observed but not established to mean logged out.
                raise MerchantIdentityUnverified()
            if type(code) is not int:
                raise MerchantValidationUnavailable()
            if code != 0:
                raise MerchantValidationUnavailable()
            merchant_data = merchant.get("data")
            merchant_id = _shop_id(merchant_data.get("id")) if isinstance(merchant_data, dict) else None
            if not merchant_id:
                raise MerchantIdentityUnverified()
            if merchant_id != target_platform_shop_id:
                raise MerchantIdentityMismatch()
    except MerchantIdentityUnverified:
        raise
    except (TimeoutError, httpx.HTTPError, OSError, ValueError, MerchantValidationUnavailable):
        raise MerchantValidationUnavailable() from None


async def _request_identity(
    url: str,
    referer: str,
    context: ShopSessionAuthContext,
    transport: httpx.AsyncBaseTransport | None,
) -> dict[str, Any]:
    # A fresh client per endpoint prevents the Compass response from changing
    # the cookies used for the merchant check. Neither response is persisted.
    async with httpx.AsyncClient(
        timeout=2.5, follow_redirects=False, transport=transport,
    ) as client:
        async with client.stream(
            "GET", url,
            headers={"accept": "application/json, text/plain, */*", "referer": referer, "user-agent": _USER_AGENT},
            cookies=to_httpx_cookies(context.cookies),
        ) as response:
            if response.status_code != 200:
                raise MerchantValidationUnavailable()
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > _MAX_RESPONSE_BYTES:
                    raise MerchantValidationUnavailable()
    try:
        parsed = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise MerchantValidationUnavailable() from None
    if not isinstance(parsed, dict):
        raise MerchantValidationUnavailable()
    return parsed


def _shop_id(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return str(value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def verify_merchant_session_sync(
    context: ShopSessionAuthContext, target_platform_shop_id: str, *,
    compass_already_verified: bool = False,
) -> None:
    asyncio.run(verify_merchant_session(
        context, target_platform_shop_id, compass_already_verified=compass_already_verified,
    ))
