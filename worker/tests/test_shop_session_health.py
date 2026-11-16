import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.rpa_session_bridge import LocalCookie, LocalSession, LocalShop
from app.shop_session_health import ShopSessionHealth


def shop(revision="a" * 64):
    return LocalShop(localShopId="local-a", platformShopId="123", shopName="测试店铺",
                     platform="douyin", sessionStored=True, sessionRevision=revision)


class Bridge:
    def __init__(self):
        self.revision = "a" * 64

    async def session_revision(self, local_id, platform_id):
        return self.revision

    async def read_session(self, local_id, platform_id):
        return LocalSession(localShopId=local_id, platformShopId=platform_id, platform="douyin",
                            userAgent="test-agent", cookies=[LocalCookie(
                                name="test", value="synthetic", domain="fxg.jinritemai.com", path="/")])


def test_only_matching_identity_reports_valid_without_exporting_session():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        assert request.url.host == "fxg.jinritemai.com"
        assert request.headers["cookie"] == "test=synthetic"
        return httpx.Response(200, json={"code": 0, "data": {"id": "123"}})

    now = datetime(2026, 11, 16, tzinfo=UTC)
    monitor = ShopSessionHealth(Bridge(), transport=httpx.MockTransport(handler), now=lambda: now)
    target = shop()
    assert monitor.due([target]) == target
    asyncio.run(monitor.check(target))
    assert calls == ["/common/index/index"]
    assert monitor.report(target) == {"sessionStatus": "valid", "sessionCheckedAt": now.isoformat()}
    assert "synthetic" not in repr(monitor.report(target))
    assert monitor.due([target]) is None
    assert monitor.report(shop("b" * 64))["sessionStatus"] is None


def test_no_saved_snapshot_never_starts_a_check():
    target = shop().model_copy(update={"session_stored": False, "session_revision": None})
    monitor = ShopSessionHealth(Bridge())
    assert monitor.due([target]) is None
    assert monitor.report(target)["sessionStatus"] is None


@pytest.mark.parametrize("status,payload,expected", [
    (200, {"code": 10004, "msg": "请先登录"}, "invalid"),
    (401, {"code": 10004, "msg": "登录状态已过期，请重新登录"}, "invalid"),
    (403, {"code": 10004, "msg": "请先登录"}, None),
    (200, {"code": 10008}, None),
    (200, {"code": 0, "data": {"id": "different"}}, None),
])
def test_only_explicit_login_failure_marks_invalid(status, payload, expected):
    monitor = ShopSessionHealth(Bridge(), transport=httpx.MockTransport(
        lambda request: httpx.Response(status, json=payload)))
    target = shop()
    asyncio.run(monitor.check(target))
    assert monitor.report(target)["sessionStatus"] == expected


def test_network_error_does_not_replace_last_validation_or_invent_expiry():
    now = [datetime(2026, 11, 16, tzinfo=UTC)]
    fail = [False]

    def handler(request):
        if fail[0]:
            raise httpx.ConnectError("synthetic network failure")
        return httpx.Response(200, json={"code": 0, "data": {"id": "123"}})

    monitor = ShopSessionHealth(Bridge(), transport=httpx.MockTransport(handler), now=lambda: now[0])
    target = shop()
    asyncio.run(monitor.check(target))
    fail[0] = True
    now[0] += timedelta(minutes=5)
    asyncio.run(monitor.check(target))
    assert monitor.report(target)["sessionStatus"] == "valid"
    now[0] += timedelta(minutes=26)
    assert monitor.report(target)["sessionStatus"] is None


def test_replaced_session_during_request_never_receives_old_result():
    bridge = Bridge()

    def handler(request):
        bridge.revision = "b" * 64
        return httpx.Response(200, json={"code": 0, "data": {"id": "123"}})

    monitor = ShopSessionHealth(bridge, transport=httpx.MockTransport(handler))
    asyncio.run(monitor.check(shop()))
    assert monitor.report(shop())["sessionStatus"] is None
    assert monitor.report(shop("b" * 64))["sessionStatus"] is None
