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
from app.platforms.exceptions import (
    PlatformAuthenticationInvalidError,
    PlatformRequestFailedError,
)
from app.platforms.pdd.api_client import PddApiClient
from app.platforms.pdd.connector import (
    MERCHANT_IDENTITY_URL,
    PddPlatformConnector,
)


class FakeSigner:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self) -> SecretStr:
        self.calls += 1
        return SecretStr("synthetic-anti-content")


def auth_context(cookie_value: str = "sensitive-pdd-cookie") -> ShopSessionAuthContext:
    return ShopSessionAuthContext(
        shop_id=uuid4(),
        platform=ShopPlatform.PDD,
        session_version=1,
        cookies=(
            StoredSessionCookie(
                name="pdd_user_id",
                value=SecretStr(cookie_value),
                domain=".pinduoduo.com",
                path="/",
                secure=True,
                httpOnly=True,
            ),
        ),
    )


def test_pdd_identity_uses_verified_contract_and_fixed_result_paths(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "sensitive-pdd-cookie"
    signer = FakeSigner()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == MERCHANT_IDENTITY_URL
        assert request.content == b"{}"
        assert request.headers["anti-content"] == "synthetic-anti-content"
        assert request.headers["origin"] == "https://mms.pinduoduo.com"
        assert f"pdd_user_id={secret}" in request.headers["cookie"]
        return httpx.Response(
            200,
            request=request,
            json={
                "success": True,
                "error_code": 1_000_000,
                "result": {"mallId": "mall-1", "mallName": "PDD Shop"},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        connector = PddPlatformConnector(
            api_client=PddApiClient(client, signer=signer),
        )
        with caplog.at_level(logging.INFO):
            identity = connector.fetch_shop_identity(uuid4(), auth_context(secret))

    assert signer.calls == 1
    assert identity.platform_shop_id == "mall-1"
    assert identity.shop_display_name == "PDD Shop"
    assert secret not in caplog.text
    assert "anti-content" not in caplog.text.lower()


def test_pdd_identity_rejects_platform_failure_and_http_authentication() -> None:
    signer = FakeSigner()

    def platform_failure(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={"success": False, "error_code": 43001, "error_msg": "denied"},
        )

    with httpx.Client(transport=httpx.MockTransport(platform_failure)) as client:
        connector = PddPlatformConnector(
            api_client=PddApiClient(client, signer=signer),
        )
        with pytest.raises(PlatformRequestFailedError):
            connector.fetch_shop_identity(uuid4(), auth_context())

    def unauthorized(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, request=request)

    with httpx.Client(transport=httpx.MockTransport(unauthorized)) as client:
        connector = PddPlatformConnector(
            api_client=PddApiClient(client, signer=signer),
        )
        with pytest.raises(PlatformAuthenticationInvalidError):
            connector.fetch_shop_identity(uuid4(), auth_context())
