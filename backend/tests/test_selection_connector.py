"""Only FakeSigner + MockTransport; these are not new platform requests."""

import asyncio
from contextlib import nullcontext
from datetime import UTC, datetime
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.integrations.douyin_signer import DouyinSignResult
from app.modules.sessions.auth_context import ShopSessionAuthContext, StoredSessionCookie
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import (
    SessionVersionConflictError,
    ShopSessionAuthenticationInvalidError,
    ShopSessionNotConfiguredError,
)
from app.modules.shops.enums import ShopPlatform
from app.platforms.douyin.api_client import DouyinApiClient
from app.platforms.douyin.selection_connector import DouyinProductSelectionConnector
from app.platforms.exceptions import (
    PlatformAuthenticationInvalidError,
    PlatformResponseInvalidError,
    PlatformSignerFailedError,
)
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


@pytest.mark.parametrize("capacity", [1, 3])
def test_enabled_but_unconfirmed_consumer_only_recovers_expired_leases(monkeypatch, capacity):
    from app.modules.product_selection import run_executor
    recovered = []
    # The mocked idle cancellation must not abort sibling workers before their first pass.
    first_pass = Barrier(capacity)
    class Executor:
        def recover_only(self):
            recovered.append(True)
            first_pass.wait()
        def execute_available(self):
            pytest.fail("Unknown mapping cannot claim a run or issue HTTP")

    async def stop(_):
        raise asyncio.CancelledError()

    monkeypatch.setattr(run_executor, "get_settings", lambda: Settings(product_selection_execution_enabled=True, product_selection_concurrency=capacity))
    monkeypatch.setattr(run_executor, "selection_request_mapping_available", lambda: False)
    monkeypatch.setattr(run_executor, "build_selection_run_executor", lambda *_: Executor())
    monkeypatch.setattr(run_executor.asyncio, "sleep", stop)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_executor.execute_selection_runs_forever())
    assert recovered == [True] * capacity


@pytest.mark.parametrize("capacity", [1, 3])
def test_enabled_confirmed_consumer_uses_existing_executor(monkeypatch, capacity):
    from app.modules.product_selection import run_executor
    executed = []
    # The mocked idle cancellation must not abort sibling workers before their first pass.
    first_pass = Barrier(capacity)
    class Executor:
        def execute_available(self):
            executed.append(True)
            first_pass.wait()
            return 0
    async def stop(_):
        raise asyncio.CancelledError()
    monkeypatch.setattr(run_executor, "get_settings", lambda: Settings(product_selection_execution_enabled=True, product_selection_concurrency=capacity))
    monkeypatch.setattr(run_executor, "build_selection_run_executor", lambda *_: Executor())
    monkeypatch.setattr(run_executor.asyncio, "sleep", stop)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_executor.execute_selection_runs_forever())
    assert executed == [True] * capacity


def _install_stored_session_fakes(monkeypatch, *, health_result, context_version=4):
    from app.modules.product_selection import platform_io

    shop_id = uuid4()
    calls = []
    context = ShopSessionAuthContext(
        shop_id=shop_id,
        platform=ShopPlatform.DOUYIN,
        session_version=context_version,
        cookies=(),
    )

    class Accessor:
        def __init__(self, *_args):
            pass

        def get_auth_context(self, requested_shop_id, platform):
            assert requested_shop_id == shop_id
            assert platform is ShopPlatform.DOUYIN
            calls.append("context")
            return context

    class Health:
        def __init__(self, *_args, **kwargs):
            assert kwargs["before_platform_io"] is not None

        def check(self, requested_shop_id, *, force):
            assert requested_shop_id == shop_id
            assert force is False
            calls.append("health")
            if isinstance(health_result, Exception):
                raise health_result
            return health_result

    monkeypatch.setattr(
        platform_io,
        "ShopRepository",
        lambda _: SimpleNamespace(
            get=lambda _: SimpleNamespace(
                platform=ShopPlatform.DOUYIN,
                platform_shop_id="verified-synthetic-shop",
            ),
        ),
    )
    monkeypatch.setattr(platform_io, "ShopSessionAccessor", Accessor)
    monkeypatch.setattr(platform_io, "ShopSessionHealthService", Health)
    monkeypatch.setattr(platform_io, "create_platform_connectors", lambda: {})
    return shop_id, calls


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (ShopSessionNotConfiguredError(), "SHOP_SESSION_NOT_CONFIGURED"),
        (ShopSessionAuthenticationInvalidError(), "AUTH_INVALID"),
    ],
)
def test_stored_session_preparation_propagates_authoritative_readiness_errors(
    monkeypatch,
    failure,
    expected,
):
    from app.core.exceptions import AppError
    from app.modules.product_selection import platform_io
    from app.modules.product_selection.run_service import safe_run_error

    shop_id, calls = _install_stored_session_fakes(
        monkeypatch,
        health_result=failure,
    )
    adapter = platform_io.SelectionStoredSessionIO(
        lambda: nullcontext(None),
        cipher_factory=lambda: object(),
    )
    with pytest.raises(AppError) as caught:
        adapter.session_context(shop_id)
    assert caught.value.code == expected
    assert safe_run_error(caught.value) == (expected, "session", None)
    assert calls == ["health"]


def test_stored_session_preparation_binds_the_checked_version_once(monkeypatch):
    from app.modules.product_selection import platform_io

    shop_id = uuid4()
    health = SimpleNamespace(
        shop_id=shop_id,
        platform=ShopPlatform.DOUYIN,
        status=ShopSessionStatus.VALID,
        version=4,
    )
    actual_shop_id, calls = _install_stored_session_fakes(
        monkeypatch,
        health_result=health,
        context_version=4,
    )
    # The closure owns the actual Shop ID used by its context.
    health.shop_id = actual_shop_id
    adapter = platform_io.SelectionStoredSessionIO(
        lambda: nullcontext(None),
        cipher_factory=lambda: object(),
    )

    assert adapter.session_context(actual_shop_id).session_version == 4
    assert calls == ["health", "context"]


def test_stored_session_preparation_rejects_version_change_after_check(monkeypatch):
    from app.core.exceptions import AppError
    from app.modules.product_selection import platform_io
    from app.modules.product_selection.run_service import safe_run_error

    health = SimpleNamespace(
        shop_id=uuid4(),
        platform=ShopPlatform.DOUYIN,
        status=ShopSessionStatus.VALID,
        version=3,
    )
    shop_id, calls = _install_stored_session_fakes(
        monkeypatch,
        health_result=health,
        context_version=4,
    )
    health.shop_id = shop_id
    adapter = platform_io.SelectionStoredSessionIO(
        lambda: nullcontext(None),
        cipher_factory=lambda: object(),
    )

    with pytest.raises(SessionVersionConflictError) as caught:
        adapter.session_context(shop_id)
    assert safe_run_error(caught.value) == ("SESSION_VERSION_CONFLICT", "session", None)
    assert calls == ["health", "context"]


def test_stored_session_preparation_classifies_cipher_failure(monkeypatch):
    from app.core.exceptions import AppError
    from app.core.security import EncryptionConfigurationError
    from app.modules.product_selection import platform_io
    from app.modules.product_selection.run_service import safe_run_error

    monkeypatch.setattr(
        platform_io,
        "ShopRepository",
        lambda _: SimpleNamespace(
            get=lambda _: SimpleNamespace(
                platform=ShopPlatform.DOUYIN,
                platform_shop_id="verified-synthetic-shop",
            ),
        ),
    )

    def cipher():
        raise EncryptionConfigurationError("synthetic local config failure")

    adapter = platform_io.SelectionStoredSessionIO(
        lambda: nullcontext(None),
        cipher_factory=cipher,
    )
    with pytest.raises(AppError) as caught:
        adapter.session_context(uuid4())
    assert caught.value.code == "SESSION_ENCRYPTION_UNAVAILABLE"
    assert safe_run_error(caught.value) == (
        "SESSION_ENCRYPTION_UNAVAILABLE",
        "session",
        None,
    )


def test_stored_selection_marks_only_explicit_business_auth_invalid(monkeypatch):
    from app.modules.product_selection import platform_io

    context = _context()
    marked = []

    class Accessor:
        def __init__(self, *_args):
            pass

        def mark_validation_status(self, shop_id, version, status):
            marked.append((shop_id, version, status))

    class Connector:
        def categories(self, _context):
            raise PlatformAuthenticationInvalidError()

    monkeypatch.setattr(platform_io, "ShopSessionAccessor", Accessor)
    adapter = platform_io.SelectionStoredSessionIO(
        lambda: nullcontext(None),
        connector=Connector(),
        cipher_factory=lambda: object(),
    )

    with pytest.raises(PlatformAuthenticationInvalidError):
        adapter.categories(context)

    assert marked == [
        (context.shop_id, context.session_version, ShopSessionStatus.INVALID),
    ]


@pytest.mark.parametrize(
    "failure",
    [
        PlatformSignerFailedError(),
        PlatformResponseInvalidError(),
    ],
)
def test_stored_selection_non_auth_failures_do_not_change_session(
    monkeypatch,
    failure,
):
    from app.modules.product_selection import platform_io

    class Accessor:
        def __init__(self, *_args):
            pass

        def mark_validation_status(self, *_args):
            pytest.fail("non-auth failure must not change Session status")

    class Connector:
        def categories(self, _context):
            raise failure

    monkeypatch.setattr(platform_io, "ShopSessionAccessor", Accessor)
    adapter = platform_io.SelectionStoredSessionIO(
        lambda: nullcontext(None),
        connector=Connector(),
        cipher_factory=lambda: object(),
    )

    with pytest.raises(type(failure)):
        adapter.categories(_context())


def test_stored_selection_old_auth_failure_cannot_invalidate_new_session(
    monkeypatch,
):
    from app.modules.product_selection import platform_io

    class Accessor:
        def __init__(self, *_args):
            pass

        def mark_validation_status(self, *_args):
            raise SessionVersionConflictError()

    class Connector:
        def categories(self, _context):
            raise PlatformAuthenticationInvalidError()

    monkeypatch.setattr(platform_io, "ShopSessionAccessor", Accessor)
    adapter = platform_io.SelectionStoredSessionIO(
        lambda: nullcontext(None),
        connector=Connector(),
        cipher_factory=lambda: object(),
    )

    with pytest.raises(PlatformAuthenticationInvalidError):
        adapter.categories(_context())
