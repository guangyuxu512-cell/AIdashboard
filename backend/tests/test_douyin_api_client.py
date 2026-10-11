from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from app.integrations.douyin_signer import DouyinSignResult, DouyinSignerUnavailableError
from app.modules.sessions.auth_context import ShopSessionAuthContext, StoredSessionCookie
from app.modules.shops.enums import ShopPlatform
from app.platforms.douyin.api_client import DouyinApiClient
from app.platforms.douyin.endpoints import (
    COMPASS_CORE_INDEX_V3_ENDPOINT,
    PRODUCT_LIST_ENDPOINT,
    SHOP_INFO_V2_ENDPOINT,
    DouyinEndpoint,
)
from app.platforms.exceptions import PlatformRequestFailedError, PlatformSignerFailedError


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
        with pytest.raises(PlatformSignerFailedError):
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


@pytest.mark.parametrize(
    "endpoint",
    [PRODUCT_LIST_ENDPOINT, COMPASS_CORE_INDEX_V3_ENDPOINT],
    ids=["fxg", "compass"],
)
def test_signer_cookie_matches_http_domain_path_and_order(
    endpoint: DouyinEndpoint,
) -> None:
    signer = FakeSigner()
    context = auth_context().model_copy(
        update={
            "cookies": (
                StoredSessionCookie(
                    name="sessionid", value=SecretStr("synthetic-shared"),
                    domain=".jinritemai.com", path="/",
                ),
                StoredSessionCookie(
                    name="sessionid", value=SecretStr("synthetic-fxg"),
                    domain="fxg.jinritemai.com", path="/",
                ),
                StoredSessionCookie(
                    name="sessionid", value=SecretStr("synthetic-compass"),
                    domain="compass.jinritemai.com", path="/",
                ),
                StoredSessionCookie(
                    name="scoped", value=SecretStr("synthetic-long-path"),
                    domain=endpoint.host, path=endpoint.path.rsplit("/", 1)[0],
                ),
                StoredSessionCookie(
                    name="excluded", value=SecretStr("synthetic-wrong-path"),
                    domain=endpoint.host, path="/unrelated",
                ),
                StoredSessionCookie(
                    name="replacement", value=SecretStr("synthetic-old"),
                    domain=endpoint.host, path="/",
                ),
                StoredSessionCookie(
                    name="replacement", value=SecretStr("synthetic-new"),
                    domain=endpoint.host, path="/",
                ),
            ),
        },
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert len(signer.requests) == 1
        cookie = request.headers["cookie"]
        assert signer.requests[0].cookie.get_secret_value() == cookie
        assert cookie.startswith("scoped=synthetic-long-path;")
        assert "excluded=" not in cookie
        assert "synthetic-old" not in cookie
        other_host = "fxg" if endpoint.host.startswith("compass") else "compass"
        assert f"synthetic-{other_host}" not in cookie
        assert request.url.params["a_bogus"] == "synthetic-a-bogus"
        assert "a_bogus" not in httpx.URL(signer.requests[0].full_url).params
        return httpx.Response(200, request=request, json={"st": 0, "data": {}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        DouyinApiClient(client, signer=signer).request_json(endpoint, context)


def test_signed_requests_do_not_reuse_another_shop_cookie() -> None:
    signer = FakeSigner()
    seen_cookies: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        cookie = request.headers["cookie"]
        assert signer.requests[-1].cookie.get_secret_value() == cookie
        seen_cookies.append(cookie)
        return httpx.Response(200, request=request, json={"st": 0, "data": {}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        api = DouyinApiClient(client, signer=signer)
        for value in ("synthetic-shop-a", "synthetic-shop-b"):
            api.request_json(COMPASS_CORE_INDEX_V3_ENDPOINT, auth_context(value))

    assert seen_cookies == ["sessionid=synthetic-shop-a", "sessionid=synthetic-shop-b"]


def test_cookie_selection_is_not_rebuilt_after_signing() -> None:
    class UpdatingSigner(FakeSigner):
        def sign(self, request):  # type: ignore[no-untyped-def]
            result = super().sign(request)
            client.cookies.set(
                "client_cookie", "synthetic-after", domain=".jinritemai.com",
            )
            return result

    signer = UpdatingSigner()

    def handler(request: httpx.Request) -> httpx.Response:
        cookie = request.headers["cookie"]
        assert cookie == signer.requests[0].cookie.get_secret_value()
        assert "client_cookie=synthetic-before" in cookie
        assert "synthetic-after" not in cookie
        return httpx.Response(200, request=request, json={"st": 0, "data": {}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        client.cookies.set("client_cookie", "synthetic-before", domain=".jinritemai.com")
        DouyinApiClient(client, signer=signer).request_json(
            COMPASS_CORE_INDEX_V3_ENDPOINT, auth_context(),
        )


@pytest.mark.parametrize("previous_signature", ["", "synthetic-old-signature"])
def test_signing_removes_old_signature_and_preserves_prepared_query_encoding(
    previous_signature: str,
) -> None:
    signer = FakeSigner()
    query = {
        "begin_date": "2026/10/02 00:00:00",
        "price_bin": "不限",
        "category_id": "1000009092,1000009142",
        "search_info": "",
        "a_bogus": previous_signature,
    }
    original_query = dict(query)

    def handler(request: httpx.Request) -> httpx.Response:
        unsigned_url = httpx.URL(signer.requests[0].full_url)
        assert "a_bogus" not in unsigned_url.params
        assert request.url.params.get_list("a_bogus") == ["synthetic-a-bogus"]
        assert request.url.query.split(b"&a_bogus=")[0] == unsigned_url.query
        for key, value in query.items():
            if key != "a_bogus":
                assert request.url.params[key] == value
        return httpx.Response(200, request=request, json={"st": 0, "data": {}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        DouyinApiClient(client, signer=signer).request_json(
            COMPASS_CORE_INDEX_V3_ENDPOINT, auth_context(), query=query,
        )
    assert query == original_query
