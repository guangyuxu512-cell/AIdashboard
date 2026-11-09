import asyncio
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from app.modules.sessions.auth_context import ShopSessionAuthContext, StoredSessionCookie
from app.modules.shops.enums import ShopPlatform
from app.platforms.douyin.merchant_identity import (
    MerchantIdentityUnverified,
    MerchantValidationUnavailable,
    verify_merchant_session,
)


def candidate() -> ShopSessionAuthContext:
    return ShopSessionAuthContext(
        shop_id=uuid4(), platform=ShopPlatform.DOUYIN, session_version=1,
        cookies=(StoredSessionCookie(
            name="fixture", value=SecretStr("original"), domain=".jinritemai.com",
        ),),
    )


def run(handler, *, total_seconds=4.0):
    asyncio.run(verify_merchant_session(
        candidate(), "shop-a", transport=httpx.MockTransport(handler),
        total_seconds=total_seconds,
    ))


def test_same_snapshot_ids_match_without_merging_compass_updates() -> None:
    paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        assert request.headers["cookie"] == "fixture=original"
        if request.url.host.startswith("compass."):
            return httpx.Response(
                200, request=request,
                headers={"set-cookie": "fixture=changed; Domain=.jinritemai.com; Path=/"},
                json={"st": 0, "data": {"shop_id": "shop-a"}},
            )
        return httpx.Response(200, request=request, json={"code": 0, "data": {"id": "shop-a"}})

    run(handler)
    assert paths == ["/compass_api/shop/mall/common/shop_info_v2", "/common/index/index"]


def test_explicit_sync_reuses_compass_check_when_snapshot_has_not_changed() -> None:
    paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(200, request=request, json={"code": 0, "data": {"id": "shop-a"}})

    asyncio.run(verify_merchant_session(
        candidate(), "shop-a", transport=httpx.MockTransport(handler),
        compass_already_verified=True,
    ))
    assert paths == ["/common/index/index"]


@pytest.mark.parametrize("compass,merchant", [
    ("shop-b", {"code": 0, "data": {"id": "shop-a"}}),
    ("shop-a", {"code": 0, "data": {"id": "shop-b"}}),
    ("shop-a", {"code": 10008}),
    ("shop-a", {"code": "10008"}),
    ("shop-a", {"code": 0, "data": {"shop_id": "shop-a"}}),
])
def test_wrong_or_unconfirmed_identity_never_succeeds(compass, merchant) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = {"st": 0, "data": {"shop_id": compass}} if request.url.host.startswith("compass.") else merchant
        return httpx.Response(200, request=request, json=body)

    with pytest.raises(MerchantIdentityUnverified):
        run(handler)


@pytest.mark.parametrize("mode", ["http", "bad-json", "business", "network", "timeout"])
def test_platform_failures_are_unavailable_not_wrong_shop(mode) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if mode == "network":
            raise httpx.ConnectError("fixture", request=request)
        if mode == "timeout":
            await asyncio.sleep(0.2)
        if mode == "http":
            return httpx.Response(503, request=request)
        if mode == "bad-json":
            return httpx.Response(200, request=request, text="not-json")
        if mode == "business":
            return httpx.Response(200, request=request, json={"st": 5})
        return httpx.Response(200, request=request, json={"st": 0, "data": {"shop_id": "shop-a"}})

    with pytest.raises(MerchantValidationUnavailable):
        run(handler, total_seconds=0.02 if mode == "timeout" else 4.0)
