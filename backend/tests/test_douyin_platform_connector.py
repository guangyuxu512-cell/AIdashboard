import logging
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from app.modules.sessions.auth_context import (
    ShopSessionAuthContext,
    StoredSessionCookie,
)
from app.modules.shops.enums import ShopPlatform
from app.platforms.douyin.connector import (
    ACCEPT_HEADER,
    SHOP_INFO_URL,
    DouyinPlatformConnector,
)
from app.platforms.exceptions import (
    PlatformAuthenticationInvalidError,
    PlatformRequestTimeoutError,
)


def auth_context(cookie_value: str = "highly-sensitive-cookie") -> ShopSessionAuthContext:
    return ShopSessionAuthContext(
        shop_id=uuid4(),
        platform=ShopPlatform.DOUYIN,
        session_version=1,
        cookies=(
            StoredSessionCookie(
                name="sessionid",
                value=SecretStr(cookie_value),
                domain=".jinritemai.com",
                path="/",
                secure=True,
            ),
        ),
    )


def test_connector_constructs_verified_request_and_converts_response(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "highly-sensitive-cookie"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == SHOP_INFO_URL
        assert request.headers["accept"] == ACCEPT_HEADER
        assert f"sessionid={secret}" in request.headers["cookie"]
        return httpx.Response(
            200,
            request=request,
            json={
                "st": 0,
                "msg": "success",
                "data": {"shop_id": "shop-1", "shop_name": "HuanYu"},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        connector = DouyinPlatformConnector(client)
        with caplog.at_level(logging.INFO):
            identity = connector.fetch_shop_identity(uuid4(), auth_context(secret))

    assert identity.platform_shop_id == "shop-1"
    assert identity.shop_display_name == "HuanYu"
    assert "fetch_shop_identity" in caplog.text
    assert secret not in caplog.text
    assert "cookie" not in caplog.text.lower()


def test_connector_classifies_authentication_failure_and_timeout() -> None:
    def unauthorized(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, request=request)

    with httpx.Client(transport=httpx.MockTransport(unauthorized)) as client:
        with pytest.raises(PlatformAuthenticationInvalidError):
            DouyinPlatformConnector(client).fetch_shop_identity(
                uuid4(),
                auth_context(),
            )

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    with httpx.Client(transport=httpx.MockTransport(timeout)) as client:
        with pytest.raises(PlatformRequestTimeoutError):
            DouyinPlatformConnector(client).fetch_shop_identity(
                uuid4(),
                auth_context(),
            )
