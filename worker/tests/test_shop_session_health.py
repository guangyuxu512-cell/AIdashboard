import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.rpa_session_bridge import LocalCookie, LocalRefreshStatus, LocalSession, LocalShop, RpaBridgeError
from app.shop_session_health import ShopSessionHealth


def shop(revision="a" * 64):
    return LocalShop(localShopId="local-a", platformShopId="123", shopName="测试店铺",
                     platform="douyin", sessionStored=True, sessionRevision=revision)


class Bridge:
    def __init__(self):
        self.revision = "a" * 64
        self.refreshes = []
        self.status = None

    async def request_session_refresh(self, local_id, platform_id, revision, require_compass):
        self.refreshes.append((local_id, platform_id, revision, require_compass))
        return True

    async def session_refresh_status(self, local_id, platform_id, revision):
        return self.status

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
        if request.url.host == "compass.jinritemai.com":
            return httpx.Response(200, json={"st": 0, "data": {"shop_id": "123"}})
        assert request.url.host == "fxg.jinritemai.com"
        assert request.headers["cookie"] == "test=synthetic"
        return httpx.Response(200, json={"code": 0, "data": {"id": "123"}})

    now = datetime(2026, 11, 16, tzinfo=UTC)
    monitor = ShopSessionHealth(Bridge(), transport=httpx.MockTransport(handler), now=lambda: now)
    target = shop()
    assert monitor.due([target]) == target
    asyncio.run(monitor.check(target))
    assert calls == ["/compass_api/shop/mall/common/shop_info_v2", "/common/index/index"]
    assert monitor.report(target) == {"sessionStatus": "valid", "sessionCheckedAt": now.isoformat(),
                                     "compassSessionStatus": "valid", "compassSessionCheckedAt": now.isoformat()}
    assert "synthetic" not in repr(monitor.report(target))
    assert monitor.due([target]) is None
    assert monitor.report(shop("b" * 64))["sessionStatus"] is None


def test_busy_shop_exclusion_keeps_previous_observation_and_rechecks_before_expiry():
    clock = [100.0]
    now = [datetime(2026, 11, 24, tzinfo=UTC)]

    def handler(request):
        if request.url.host == "compass.jinritemai.com":
            return httpx.Response(200, json={"st": 0, "data": {"shop_id": "123"}})
        return httpx.Response(200, json={"code": 0, "data": {"id": "123"}})

    monitor = ShopSessionHealth(Bridge(), transport=httpx.MockTransport(handler),
                                clock=lambda: clock[0], now=lambda: now[0])
    first = shop()
    second = shop().model_copy(update={"local_shop_id": "local-b", "platform_shop_id": "456"})
    asyncio.run(monitor.check(first))
    clock[0] += 16 * 60
    now[0] += timedelta(minutes=16)
    assert monitor.due([first, second], excluded_platform_ids=frozenset({"123"})) == second
    assert monitor.report(first)["sessionStatus"] == "valid"
    assert monitor.report(first)["compassSessionStatus"] == "valid"
    assert monitor.due([first, second]) == first


def test_no_saved_snapshot_never_starts_a_check():
    target = shop().model_copy(update={"session_stored": False, "session_revision": None})
    monitor = ShopSessionHealth(Bridge())
    assert monitor.due([target]) is None
    assert monitor.report(target)["sessionStatus"] is None
    assert monitor.missing_session_due([target]) == target


def test_missing_session_refresh_is_per_shop_and_bounded():
    bridge = Bridge()
    clock = [100.0]
    monitor = ShopSessionHealth(bridge, clock=lambda: clock[0])
    targets = [shop().model_copy(update={"local_shop_id": str(index), "platform_shop_id": str(index),
                                         "session_stored": False, "session_revision": None})
               for index in range(5)]
    for target in targets:
        assert monitor.missing_session_due(targets) == target
        assert asyncio.run(monitor.request_refresh(target)) is True
    assert len(bridge.refreshes) == 5
    assert monitor.missing_session_due(targets) is None
    assert not asyncio.run(monitor.request_refresh(targets[0]))


def test_new_trusted_rpa_helper_resets_exhausted_refresh_attempts():
    bridge = Bridge()
    clock = [100.0]
    monitor = ShopSessionHealth(bridge, clock=lambda: clock[0])
    original = shop().model_copy(update={"session_stored": False, "session_revision": None,
                                         "rpa_helper_digest": "a" * 64})
    for _ in range(3):
        assert asyncio.run(monitor.request_refresh(original))
        clock[0] += 301
    assert not asyncio.run(monitor.request_refresh(original))
    updated = original.model_copy(update={"rpa_helper_digest": "b" * 64})
    assert asyncio.run(monitor.request_refresh(updated))
    assert len(bridge.refreshes) == 4


def test_new_rpa_helper_rechecks_a_stored_session_without_waiting_for_old_timer():
    bridge = Bridge()
    clock = [100.0]
    def handler(request):
        if request.url.host == "compass.jinritemai.com":
            return httpx.Response(200, json={"st": 0, "data": {"shop_id": "123"}})
        return httpx.Response(200, json={"code": 0, "data": {"id": "123"}})
    monitor = ShopSessionHealth(bridge, transport=httpx.MockTransport(handler), clock=lambda: clock[0])
    old = shop().model_copy(update={"rpa_helper_digest": "a" * 64})
    new = old.model_copy(update={"rpa_helper_digest": "b" * 64})
    assert monitor.due([old]) is old
    assert not asyncio.run(monitor.check(old))
    assert monitor.due([old]) is None
    assert monitor.due([new]) is new


def test_rpa_helper_change_does_not_override_recorded_manual_verification():
    bridge = Bridge()
    bridge.status = LocalRefreshStatus("manual_required", datetime.now(UTC))
    monitor = ShopSessionHealth(bridge)
    old = shop().model_copy(update={"rpa_helper_digest": "a" * 64})
    new = old.model_copy(update={"rpa_helper_digest": "b" * 64})
    assert not asyncio.run(monitor.request_refresh(old))
    assert not asyncio.run(monitor.request_refresh(new))
    assert bridge.refreshes == []


def test_unavailable_rpa_can_accept_refresh_after_it_is_updated():
    class UpdatingBridge(Bridge):
        ready = False

        async def request_session_refresh(self, local_id, platform_id, revision, require_compass):
            if not self.ready:
                raise RpaBridgeError("RPA_HELPER_UNTRUSTED")
            return await super().request_session_refresh(local_id, platform_id, revision, require_compass)

    bridge = UpdatingBridge()
    clock = [100.0]
    monitor = ShopSessionHealth(bridge, clock=lambda: clock[0])
    target = shop().model_copy(update={"session_stored": False, "session_revision": None})
    for _ in range(4):
        assert not asyncio.run(monitor.request_refresh(target))
        clock[0] += 301
    bridge.ready = True
    assert asyncio.run(monitor.request_refresh(target))
    assert bridge.refreshes == [("local-a", "123", "missing", False)]


def test_invalid_merchant_can_recover_even_when_compass_is_unavailable():
    bridge = Bridge()
    def handler(request):
        if request.url.host == "compass.jinritemai.com":
            raise httpx.ConnectError("offline")
        return httpx.Response(200, json={"code": 1, "msg": "请先登录"})
    monitor = ShopSessionHealth(bridge, transport=httpx.MockTransport(handler))
    target = shop()
    assert asyncio.run(monitor.check(target)) is True
    assert asyncio.run(monitor.request_refresh(target)) is True
    assert bridge.refreshes == [("local-a", "123", "a" * 64, False)]


def test_unconfirmed_shop_stays_unknown_and_stops_when_rpa_requires_manual_verification():
    bridge = Bridge()
    clock = [100.0]
    target = shop().model_copy(update={"compass_session_verified": False})
    def handler(request):
        if request.url.host == "compass.jinritemai.com":
            return httpx.Response(200, json={"st": 10012})
        return httpx.Response(200, json={"code": 10008})
    monitor = ShopSessionHealth(bridge, transport=httpx.MockTransport(handler), clock=lambda: clock[0])
    assert asyncio.run(monitor.check(target)) is False
    assert monitor.report(target)["sessionStatus"] is None
    assert monitor.report(target)["compassSessionStatus"] is None
    bridge.status = LocalRefreshStatus("manual_required", datetime.now(UTC))
    clock[0] += 3600
    assert not asyncio.run(monitor.request_refresh(target))
    assert asyncio.run(monitor.check(target)) is False
    assert len(bridge.refreshes) == 0


@pytest.mark.parametrize("case", ["network", "wrong_shop"])
def test_unconfirmed_shop_does_not_prepare_when_service_unreachable_or_identity_mismatches(case):
    def handler(request):
        if request.url.host == "compass.jinritemai.com":
            if case == "network":
                raise httpx.ConnectError("offline")
            return httpx.Response(200, json={"st": 10012})
        return httpx.Response(200, json={"code": 0, "data": {"id": "different"}})
    target = shop().model_copy(update={"compass_session_verified": False})
    monitor = ShopSessionHealth(Bridge(), transport=httpx.MockTransport(handler))
    assert asyncio.run(monitor.check(target)) is False


def test_unverified_compass_business_rejection_never_triggers_login():
    bridge = Bridge()
    clock = [100.0]
    target = shop().model_copy(update={"compass_session_verified": False})
    def handler(request):
        if request.url.host == "compass.jinritemai.com":
            return httpx.Response(200, json={"st": 100704})
        return httpx.Response(200, json={"code": 0, "data": {"id": "123"}})
    monitor = ShopSessionHealth(bridge, transport=httpx.MockTransport(handler), clock=lambda: clock[0])
    assert asyncio.run(monitor.check(target)) is False
    assert monitor.report(target)["compassSessionStatus"] is None
    assert bridge.refreshes == []
    def failed(request):
        if request.url.host == "compass.jinritemai.com":
            raise httpx.ConnectError("offline")
        return httpx.Response(200, json={"code": 0, "data": {"id": "123"}})
    offline = ShopSessionHealth(bridge, transport=httpx.MockTransport(failed))
    assert asyncio.run(offline.check(target)) is False
    assert offline.report(target)["compassSessionStatus"] is None


def test_confirmed_invalid_retry_respects_backoff_and_snapshot_change():
    bridge = Bridge()
    clock = [100.0]
    target = shop()
    def handler(request):
        if request.url.host == 'compass.jinritemai.com':
            return httpx.Response(200, json={'st': 0, 'data': {'shop_id': '123'}})
        return httpx.Response(200, json={'code': 1, 'msg': '请先登录'})
    monitor = ShopSessionHealth(bridge, transport=httpx.MockTransport(handler), clock=lambda: clock[0])
    assert asyncio.run(monitor.check(target))
    assert monitor.invalid_session_due([target]) == target
    assert asyncio.run(monitor.request_refresh(target))
    assert monitor.invalid_session_due([target]) is None
    clock[0] += 301
    assert monitor.invalid_session_due([target]) == target
    assert monitor.invalid_session_due([shop('b' * 64)]) is None


def test_busy_and_transient_rpa_failures_retry_but_do_not_mark_the_session_invalid():
    bridge = Bridge()
    clock = [100.0]
    now = [datetime(2026, 11, 23, tzinfo=UTC)]
    target = shop().model_copy(update={"session_stored": False, "session_revision": None})
    monitor = ShopSessionHealth(bridge, clock=lambda: clock[0], now=lambda: now[0])
    assert asyncio.run(monitor.request_refresh(target))
    bridge.status = LocalRefreshStatus("busy", now[0])
    clock[0] += 301
    now[0] += timedelta(seconds=301)
    assert asyncio.run(monitor.request_refresh(target))
    bridge.status = LocalRefreshStatus("retryable", now[0])
    clock[0] += 301
    now[0] += timedelta(seconds=301)
    assert not asyncio.run(monitor.request_refresh(target))
    assert monitor.report(target)["sessionStatus"] is None
    clock[0] += 1500
    now[0] += timedelta(seconds=1500)
    assert asyncio.run(monitor.request_refresh(target))
    assert len(bridge.refreshes) == 3


def test_manual_result_survives_worker_restart_but_not_a_new_session_revision():
    class RevisionAwareBridge(Bridge):
        async def session_refresh_status(self, local_id, platform_id, revision):
            if revision == "a" * 64:
                return LocalRefreshStatus("manual_required", datetime.now(UTC) - timedelta(days=2))
            return None

    bridge = RevisionAwareBridge()
    for _ in range(2):
        monitor = ShopSessionHealth(bridge)
        assert not asyncio.run(monitor.request_refresh(shop()))
    assert not bridge.refreshes
    monitor = ShopSessionHealth(bridge)
    assert asyncio.run(monitor.request_refresh(shop("b" * 64)))
    assert bridge.refreshes == [("local-a", "123", "b" * 64, True)]


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


def test_replaced_snapshot_clears_previously_observed_status():
    bridge = Bridge()

    def handler(request):
        if request.url.host == "compass.jinritemai.com":
            return httpx.Response(200, json={"st": 0, "data": {"shop_id": "123"}})
        return httpx.Response(200, json={"code": 0, "data": {"id": "123"}})

    monitor = ShopSessionHealth(bridge, transport=httpx.MockTransport(handler))
    asyncio.run(monitor.check(shop()))
    assert monitor.report(shop())["compassSessionStatus"] == "valid"
    bridge.revision = "b" * 64
    asyncio.run(monitor.check(shop()))
    assert monitor.report(shop())["sessionStatus"] is None
    assert monitor.report(shop())["compassSessionStatus"] is None


@pytest.mark.parametrize("status,payload,expected", [
    (200, {"st": 0, "data": {"shop_id": "123"}}, "valid"),
    (200, {"st": 0, "data": {"shop_id": "different"}}, None),
    (200, {"st": 100704}, None),
    (200, {"st": 1, "msg": "请先登录"}, "invalid"),
    (503, {"st": 1, "msg": "请先登录"}, None),
])
def test_compass_checks_matching_shop_and_only_explicit_auth_failure(status, payload, expected):
    def handler(request):
        if request.url.host == "compass.jinritemai.com":
            return httpx.Response(status, json=payload)
        return httpx.Response(200, json={"code": 0, "data": {"id": "123"}})

    monitor = ShopSessionHealth(Bridge(), transport=httpx.MockTransport(handler))
    asyncio.run(monitor.check(shop()))
    result = monitor.report(shop())
    assert result["sessionStatus"] == "valid"
    assert result["compassSessionStatus"] == expected
    assert bool(result["compassSessionCheckedAt"]) is (expected is not None)
    assert "synthetic" not in repr(result)


def test_compass_network_error_does_not_mark_expired_or_block_merchant():
    def handler(request):
        if request.url.host == "compass.jinritemai.com":
            raise httpx.ConnectError("network error")
        return httpx.Response(200, json={"code": 0, "data": {"id": "123"}})

    monitor = ShopSessionHealth(Bridge(), transport=httpx.MockTransport(handler))
    asyncio.run(monitor.check(shop()))
    assert monitor.report(shop())["sessionStatus"] == "valid"
    assert monitor.report(shop())["compassSessionStatus"] is None


def test_only_inconclusive_service_retries_and_abandoned_reservation_expires():
    clock = [100.0]
    calls = []

    def handler(request):
        calls.append(request.url.host)
        if request.url.host == "compass.jinritemai.com":
            raise httpx.ConnectError("network error")
        return httpx.Response(200, json={"code": 0, "data": {"id": "123"}})

    monitor = ShopSessionHealth(Bridge(), transport=httpx.MockTransport(handler), clock=lambda: clock[0])
    target = shop()
    assert monitor.due([target]) == target
    asyncio.run(monitor.check(target))
    clock[0] += 301
    assert monitor.due([target]) == target
    asyncio.run(monitor.check(target))
    assert calls.count("fxg.jinritemai.com") == 1
    assert calls.count("compass.jinritemai.com") == 2
    clock[0] += 301
    assert monitor.due([target]) == target
    # A task cancelled before it starts cannot permanently block this shop.
    clock[0] += 301
    assert monitor.due([target]) == target


def test_inconclusive_shops_do_not_starve_later_mapped_shops():
    clock = [100.0]
    monitor = ShopSessionHealth(Bridge(), clock=lambda: clock[0])
    targets = [shop().model_copy(update={"local_shop_id": str(index), "platform_shop_id": str(index)})
               for index in range(8)]
    seen = []
    for _ in range(8):
        target = monitor.due(targets)
        assert target is not None
        seen.append(target.local_shop_id)
        clock[0] += 60
    assert seen == [str(index) for index in range(8)]
