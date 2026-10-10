"""Only FakeSigner + MockTransport; these are not new platform requests."""

import asyncio
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.integrations.douyin_signer import DouyinSignResult
from app.modules.sessions.auth_context import ShopSessionAuthContext, StoredSessionCookie
from app.modules.shops.enums import ShopPlatform
from app.platforms.douyin.api_client import DouyinApiClient
from app.platforms.douyin.selection_connector import DouyinProductSelectionConnector
from app.platforms.exceptions import PlatformAuthenticationInvalidError
from tests.test_douyin_product_selection import rank_payload, basic_payload


def _context(*extra):
    return ShopSessionAuthContext(shop_id=uuid4(), platform=ShopPlatform.DOUYIN, session_version=1, cookies=(
        StoredSessionCookie(name="sessionid", value=SecretStr("synthetic-only"), domain=".jinritemai.com"),
        StoredSessionCookie(name="s_v_web_id", value=SecretStr("synthetic-current-fingerprint"), domain="compass.jinritemai.com"),
        *extra,
    ))


def _query():
    return {
        "page_no": "2", "page_size": "10", "industry_id": "7", "category_id": "1000009092,1000009142",
        "brand_type": "-1", "price_bin": "不限", "search_info": "", "rank_data_type": "1",
        "begin_date": "2026/10/02 00:00:00", "end_date": "2026/10/08 00:00:00", "date_type": "21", "activity_id": "",
    }


class FakeSigner:
    def __init__(self):
        self.requests = []

    def sign(self, request):
        self.requests.append(request)
        return DouyinSignResult(ok=True, a_bogus=SecretStr("synthetic-new"), duration_ms=1)


def test_rank_and_basic_reuse_actual_cookie_and_query_without_captured_context(caplog):
    signer, seen = FakeSigner(), []

    def handle(request):
        seen.append(request)
        assert signer.requests[-1].cookie.get_secret_value() == request.headers["cookie"]
        assert request.url.params["a_bogus"] == "synthetic-new"
        assert request.url.params["fp"] == "synthetic-current-fingerprint"
        assert request.url.params["verifyFp"] == request.url.params["fp"]
        assert not {"_lid", "msToken"} & set(request.url.params)
        return httpx.Response(200, json=rank_payload() if request.url.path.endswith("video_bring_good") else basic_payload())

    extra = StoredSessionCookie(name="s_v_web_id", value=SecretStr("wrong-path"), domain="compass.jinritemai.com", path="/not-selection")
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        connector = DouyinProductSelectionConnector(DouyinApiClient(client, signer=signer))
        page = connector.rank(_context(extra), _query())
        basic = connector.basic_info(_context(extra), page.products[0].product_id)
    assert basic.product_id == page.products[0].product_id
    for key, value in _query().items():
        assert seen[0].url.params[key] == value
    assert "a_bogus" not in httpx.URL(signer.requests[0].full_url).params
    assert "wrong-path" not in signer.requests[0].cookie.get_secret_value()
    assert "synthetic-current-fingerprint" not in caplog.text


def test_category_uses_confirmed_params_and_fixed_parser():
    signer = FakeSigner()

    def handle(request):
        assert request.url.path.endswith("cate_list")
        for key, value in {"level": "4", "scene": "6", "default_cate_to_level": "2"}.items():
            assert request.url.params[key] == value
        return httpx.Response(200, json={"st": "0", "data": {"cate_list": [
            {"cate_id": "7", "cate_name": "行业", "children": [{"cate_id": "0", "cate_name": "全部", "children": []}]},
        ], "industry_id": "7"}})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = DouyinProductSelectionConnector(DouyinApiClient(client, signer=signer)).categories(_context())
    assert result.industry_id == "7"
    assert result.nodes[0].children[0].category_id == "0"


@pytest.mark.parametrize("status,error", [(401, PlatformAuthenticationInvalidError), (403, PlatformAuthenticationInvalidError)])
def test_http_auth_is_not_a_fake_empty_board(status, error):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(status))) as client:
        connector = DouyinProductSelectionConnector(DouyinApiClient(client, signer=FakeSigner()))
        with pytest.raises(error):
            connector.rank(_context(), _query())


def test_rank_rejects_unfrozen_extra_parameters_before_http():
    connector = DouyinProductSelectionConnector()
    with pytest.raises(ValueError, match="frozen business"):
        connector.rank(_context(), _query() | {"a_bogus": "must-not-be-used"})


def test_disabled_consumer_has_no_database_or_platform_io(monkeypatch):
    from app.modules.product_selection import run_executor
    monkeypatch.setattr(run_executor, "build_selection_run_executor", lambda *_: pytest.fail("No executor/DB/platform must be started"))
    monkeypatch.setattr(run_executor, "get_settings", lambda: Settings(product_selection_execution_enabled=False))
    asyncio.run(run_executor.execute_selection_runs_forever())


def test_enabled_but_unconfirmed_consumer_only_recovers_expired_leases(monkeypatch):
    from app.modules.product_selection import run_executor
    recovered = []
    class Executor:
        def recover_only(self):
            recovered.append(True)
        def execute_available(self):
            pytest.fail("Unknown mapping cannot claim a run or issue HTTP")

    async def stop(_):
        raise asyncio.CancelledError()

    monkeypatch.setattr(run_executor, "get_settings", lambda: Settings(product_selection_execution_enabled=True))
    monkeypatch.setattr(run_executor, "selection_request_mapping_available", lambda: False)
    monkeypatch.setattr(run_executor, "build_selection_run_executor", lambda *_: Executor())
    monkeypatch.setattr(run_executor.asyncio, "sleep", stop)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_executor.execute_selection_runs_forever())
    assert recovered == [True]


def test_enabled_confirmed_consumer_uses_existing_executor(monkeypatch):
    from app.modules.product_selection import run_executor
    executed = []
    class Executor:
        def execute_available(self):
            executed.append(True)
            return 0
    async def stop(_):
        raise asyncio.CancelledError()
    monkeypatch.setattr(run_executor, "get_settings", lambda: Settings(product_selection_execution_enabled=True))
    monkeypatch.setattr(run_executor, "build_selection_run_executor", lambda *_: Executor())
    monkeypatch.setattr(run_executor.asyncio, "sleep", stop)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_executor.execute_selection_runs_forever())
    assert executed == [True]


@pytest.mark.parametrize("configured,status,expired,expected", [
    (False, "not_configured", False, "SHOP_SESSION_NOT_CONFIGURED"),
    (True, "captured", False, "AUTH_INVALID"),
    (True, "valid", True, "AUTH_INVALID"),
    (True, "valid", False, "SESSION_ENCRYPTION_UNAVAILABLE"),
])
def test_stored_session_preparation_classifies_missing_invalid_and_cipher_failure(monkeypatch, configured, status, expired, expected):
    from app.core.exceptions import AppError
    from app.core.security import EncryptionConfigurationError
    from app.modules.product_selection import platform_io
    from app.modules.product_selection.run_service import safe_run_error
    metadata = SimpleNamespace(configured=configured, status=status, expires_at=datetime.now(UTC) - timedelta(seconds=1) if expired else None)
    monkeypatch.setattr(platform_io, "ShopRepository", lambda _: SimpleNamespace(get=lambda _: SimpleNamespace(platform_shop_id="verified-synthetic-shop")))
    monkeypatch.setattr(platform_io, "ShopSessionService", lambda _: SimpleNamespace(get_metadata=lambda _: metadata))
    def cipher():
        raise EncryptionConfigurationError("synthetic local config failure")
    adapter = platform_io.SelectionStoredSessionIO(lambda: nullcontext(None), cipher_factory=cipher)
    with pytest.raises(AppError) as caught:
        adapter.session_context(uuid4())
    assert caught.value.code == expected
    assert safe_run_error(caught.value) == (expected, "session", None)
