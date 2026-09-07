from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from app.integrations.douyin_signer import DouyinSignResult, DouyinSignerUnavailableError
from app.modules.sessions.auth_context import ShopSessionAuthContext, StoredSessionCookie
from app.modules.shops.enums import ShopPlatform
from app.platforms.douyin.api_client import DouyinApiClient
from app.platforms.douyin.endpoints import PRODUCT_LIST_ENDPOINT, SHOP_INFO_V2_ENDPOINT
from app.platforms.exceptions import PlatformRequestFailedError


PRODUCT_LIST_QUERY = {
    "page": "0",
    "pageSize": "20",
    "draft_status": "0",
    "comment_percent": "",
    "group_id": "",
    "sku_type": "",
    "tab": "onSale",
    "business_type": "4",
    "is_online": "1",
    "not_for_sale_search_type": "1",
    "from_mng": "1",
    "check_status": "3",
    "status": "0",
    "supply_status": "",
    "need_auto_rectify_info": "true",
    "need_pay_no_stock_skus": "true",
    "order_field": "audit_time",
    "sort": "desc",
    "appid": "1",
    "_bid": "ffa_goods",
}


def auth_context(cookie_value: str = "sensitive-cookie") -> ShopSessionAuthContext:
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


class FakeSigner:
    def __init__(self) -> None:
        self.requests = []

    def sign(self, request):  # type: ignore[no-untyped-def]
        self.requests.append(request)
        return DouyinSignResult(
            ok=True,
            a_bogus=SecretStr("synthetic-a-bogus"),
            duration_ms=1,
        )


def test_unsigned_endpoint_skips_signer_and_preserves_session_boundary(
    caplog: pytest.LogCaptureFixture,
) -> None:
    signer = FakeSigner()
    secret = "sensitive-cookie"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == SHOP_INFO_V2_ENDPOINT.url
        assert request.headers["accept"] == "application/json, text/plain, */*"
        assert f"sessionid={secret}" in request.headers["cookie"]
        return httpx.Response(
            200,
            request=request,
            headers={"set-cookie": "sessionid=rotated; Path=/; HttpOnly"},
            json={"st": 0, "data": {"shop_id": "shop-1", "shop_name": "Shop"}},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        response = DouyinApiClient(client, signer=signer).request_json(
            SHOP_INFO_V2_ENDPOINT,
            auth_context(secret),
        )

    assert signer.requests == []
    assert response.payload["data"]["shop_id"] == "shop-1"
    assert response.cookie_updates[0].value.get_secret_value() == "rotated"
    assert secret not in caplog.text


def test_signed_product_list_injects_new_signature_once() -> None:
    signer = FakeSigner()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.host == "fxg.jinritemai.com"
        assert request.url.path == "/product/tproduct/list"
        assert request.url.params["a_bogus"] == "synthetic-a-bogus"
        assert request.url.params["page"] == "0"
        assert "msToken" not in request.url.params
        assert "verifyFp" not in request.url.params
        assert "fp" not in request.url.params
        assert "__token" not in request.url.params
        assert "_lid" not in request.url.params
        return httpx.Response(200, request=request, json={"code": 0, "data": {"list": []}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        DouyinApiClient(client, signer=signer).request_json(
            PRODUCT_LIST_ENDPOINT,
            auth_context(),
            query=PRODUCT_LIST_QUERY,
        )

    assert len(signer.requests) == 1
    request = signer.requests[0]
    assert request.host == "fxg.jinritemai.com"
    assert request.method == "GET"
    assert request.aid == 6383
    assert request.page_id == 6241
    assert request.referer == "https://fxg.jinritemai.com/ffa/g/list"
    assert "a_bogus" not in (request.full_url or "")
    assert request.ms_token is None


def test_signer_and_platform_failures_become_platform_errors() -> None:
    class UnavailableSigner:
        def sign(self, request):  # type: ignore[no-untyped-def]
            raise DouyinSignerUnavailableError()

    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500, request=request))) as client:
        with pytest.raises(PlatformRequestFailedError):
            DouyinApiClient(client, signer=UnavailableSigner()).request_json(
                PRODUCT_LIST_ENDPOINT,
                auth_context(),
                query=PRODUCT_LIST_QUERY,
            )

        with pytest.raises(PlatformRequestFailedError):
            DouyinApiClient(client).request_json(
                SHOP_INFO_V2_ENDPOINT,
                auth_context(),
            )
