import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from app.config import WorkerSettings
from app.contracts import ExecutionResult, LocalShopContext, WorkerTask
from app.rpa_session_bridge import LocalCookie, LocalRefreshStatus, LocalSession, LocalShop
from app.shop_session_health import ShopSessionHealth
from app.worker import Worker


def make_shop(local="a", platform="123", revision="a" * 64):
    return LocalShop(localShopId=local, platformShopId=platform, shopName="test",
                     platform="douyin", sessionStored=True, sessionRevision=revision)


def make_task(skill, shop, *, input_data=None):
    return WorkerTask(task_id=uuid4(), skill_id=skill, input=input_data or {},
        lease_until=datetime.now(UTC) + timedelta(minutes=1),
        local_shops=[LocalShopContext(local_shop_id=shop.local_shop_id,
                                    platform="douyin", platform_shop_id=shop.platform_shop_id)])


class Bridge:
    def __init__(self, shops):
        self.inventory = SimpleNamespace(installation_id=uuid4(), shops=shops)
        self.revisions = {shop.local_shop_id: shop.session_revision for shop in shops}
        self.refreshes = []
        self.refreshed = asyncio.Event()
        self.status = None
        self.auto_finish = True

    async def list_shops(self):
        # Inventory is re-created on every read, just like the real bridge.
        return SimpleNamespace(installation_id=self.inventory.installation_id, shops=list(self.inventory.shops))

    async def session_revision(self, local_id, platform_id):
        return self.revisions[local_id]

    async def read_session(self, local_id, platform_id):
        return LocalSession(localShopId=local_id, platformShopId=platform_id, platform="douyin",
                            userAgent="test", cookies=[LocalCookie(name="test", value="synthetic",
                                domain="fxg.jinritemai.com", path="/")])

    async def session_refresh_status(self, *args):
        return self.status

    async def request_session_refresh(self, *args):
        self.refreshes.append(args)
        if self.auto_finish:
            self.status = LocalRefreshStatus("retryable", datetime.now(UTC))
        self.refreshed.set()
        return True


class UnavailableClient:
    async def report_rpa_inventory(self, _payload):
        raise OSError("center offline")


def make_worker(tmp_path, bridge, handler):
    settings = WorkerSettings(server_url="https://test.invalid", device_id=uuid4(),
                              device_token="synthetic", runtime_root=tmp_path,
                              provider_inventory_interval_seconds=60)
    worker = Worker(settings, UnavailableClient(), object(), rpa_bridge=bridge)
    worker.shop_session_health = ShopSessionHealth(bridge, transport=httpx.MockTransport(handler))
    worker._last_rpa_inventory = bridge.inventory
    return worker


def test_explicit_expiry_wakes_inventory_and_recovers_even_if_center_is_offline(tmp_path):
    async def scenario():
        shop = make_shop()
        bridge = Bridge([shop])
        worker = make_worker(tmp_path, bridge,
            lambda request: httpx.Response(200, json={"code": 1, "msg": "请先登录"}))
        task = make_task("douyin.merchant_products", shop, input_data={"operation": "list"})
        # A running operation on the same shop must finish before recovery starts.
        worker._active_task_ids.add(task.task_id)
        worker._active_health_scopes[task.task_id] = (shop.platform_shop_id, True)
        worker._queue_session_recheck(task, ExecutionResult(status="failed", error_code="SHOP_SESSION_EXPIRED"))
        stop = asyncio.Event()
        loop = asyncio.create_task(worker._rpa_inventory_loop(stop))
        await asyncio.sleep(0.05)
        assert bridge.refreshes == []
        assert worker._session_rechecks
        worker._active_task_ids.clear()
        worker._active_health_scopes.clear()
        worker._rpa_inventory_wakeup.set()
        await asyncio.wait_for(bridge.refreshed.wait(), timeout=2)
        assert bridge.refreshes == [("a", "123", "a" * 64, False)]
        assert worker.shop_session_health.report(shop)["sessionStatus"] == "invalid"
        stop.set()
        await asyncio.wait_for(loop, timeout=2)
        await worker._cancel_shop_health_probe()

    asyncio.run(scenario())


@pytest.mark.parametrize("status,body", [
    (200, {"code": 600002, "msg": "平台业务拒绝"}),
    (503, {"code": 1, "msg": "请先登录"}),
    (200, {"code": 0, "data": {"id": "123"}}),
])
def test_business_rejection_only_verifies_identity_without_automatic_login(tmp_path, status, body):
    async def scenario():
        shop = make_shop()
        bridge = Bridge([shop])
        worker = make_worker(tmp_path, bridge, lambda request: httpx.Response(status, json=body))
        task = make_task("douyin.merchant_products", shop)
        failure = ExecutionResult(status="failed", error_code="PLATFORM_BUSINESS_REJECTED")
        worker._queue_session_recheck(task, failure)
        selected = worker._take_session_recheck([shop], frozenset())
        assert selected == (shop, {"merchant"})
        assert worker.shop_session_health.prioritize(*selected)
        await worker._verify_local_shop(bridge.inventory, shop)
        assert bridge.refreshes == []
        assert worker.shop_session_health.report(shop)["sessionStatus"] != "invalid"
        # Repeated business errors for the same saved snapshot are rate-limited.
        worker._queue_session_recheck(task, failure)
        assert worker._session_rechecks == {}
        # A later explicit expiry is a stronger signal and has its own limit.
        worker._queue_session_recheck(task, ExecutionResult(status="failed", error_code="SHOP_SESSION_EXPIRED"))
        assert worker._session_rechecks == {("a", "123"): {"merchant"}}

    asyncio.run(scenario())


def test_only_explicit_failure_and_merchant_business_rejection_schedule_checks(tmp_path):
    async def scenario():
        shop = make_shop()
        other = make_shop("b", "456", "b" * 64)
        bridge = Bridge([shop, other])
        worker = make_worker(tmp_path, bridge, lambda request: httpx.Response(503))
        merchant = make_task("douyin.merchant_products", shop)
        compass = make_task("douyin.compass_selection", other)
        for code in ("PLATFORM_REQUEST_FAILED", "RPA_SESSION_UNAVAILABLE", "SKILL_TIMEOUT"):
            worker._queue_session_recheck(merchant, ExecutionResult(status="failed", error_code=code))
        worker._queue_session_recheck(compass, ExecutionResult(status="failed", error_code="PLATFORM_BUSINESS_REJECTED"))
        assert worker._session_rechecks == {}
        for task in (merchant, merchant, compass):
            worker._queue_session_recheck(task, ExecutionResult(status="failed", error_code="SHOP_SESSION_EXPIRED"))
        assert worker._session_rechecks == {("a", "123"): {"merchant"}, ("b", "456"): {"compass"}}
        first = worker._take_session_recheck([shop, other], frozenset({"123"}))
        assert first == (other, {"compass"})
        assert worker._take_session_recheck([shop, other], frozenset()) == (shop, {"merchant"})
        assert worker._take_session_recheck([shop, other], frozenset()) is None

    asyncio.run(scenario())


def test_new_snapshot_during_status_report_never_refreshes_old_session(tmp_path):
    async def scenario():
        shop = make_shop()
        bridge = Bridge([shop])
        worker = make_worker(tmp_path, bridge,
            lambda request: httpx.Response(200, json={"code": 1, "msg": "请先登录"}))
        new_shop = shop.model_copy(update={"session_revision": "b" * 64})

        class Client:
            async def report_rpa_inventory(self, _payload):
                bridge.revisions["a"] = "b" * 64
                worker._last_rpa_inventory = SimpleNamespace(installation_id=bridge.inventory.installation_id,
                                                             shops=[new_shop])

        worker.client = Client()
        assert worker.shop_session_health.prioritize(shop, {"merchant"})
        await worker._verify_local_shop(bridge.inventory, shop)
        assert bridge.refreshes == []
        assert worker.shop_session_health.report(new_shop)["sessionStatus"] is None

    asyncio.run(scenario())


def test_cancelled_priority_probe_is_requeued(tmp_path):
    async def scenario():
        shop = make_shop()
        bridge = Bridge([shop])
        worker = make_worker(tmp_path, bridge, lambda request: httpx.Response(503))
        started = asyncio.Event()

        async def interrupted(_shop):
            started.set()
            await asyncio.Event().wait()

        worker.shop_session_health.check = interrupted
        probe = asyncio.create_task(worker._verify_local_shop(bridge.inventory, shop, priority_kinds={"merchant"}))
        await started.wait()
        probe.cancel()
        with pytest.raises(asyncio.CancelledError):
            await probe
        assert worker._session_rechecks == {("a", "123"): {"merchant"}}
        assert worker._rpa_inventory_wakeup.is_set()

    asyncio.run(scenario())


def test_saved_replacement_is_verified_again_before_status_becomes_valid(tmp_path):
    async def scenario():
        shop = make_shop()
        bridge = Bridge([shop])
        valid = False

        def response(request):
            if not valid:
                return httpx.Response(200, json={"code": 1, "msg": "请先登录"})
            if request.url.host == "compass.jinritemai.com":
                return httpx.Response(200, json={"st": 0, "data": {"shop_id": "123"}})
            return httpx.Response(200, json={"code": 0, "data": {"id": "123"}})

        worker = make_worker(tmp_path, bridge, response)
        assert worker.shop_session_health.prioritize(shop, {"merchant"})
        await worker._verify_local_shop(bridge.inventory, shop)
        assert worker.shop_session_health.report(shop)["sessionStatus"] == "invalid"
        assert len(bridge.refreshes) == 1
        replacement = shop.model_copy(update={"session_revision": "b" * 64})
        bridge.revisions["a"] = "b" * 64
        bridge.inventory = SimpleNamespace(installation_id=bridge.inventory.installation_id, shops=[replacement])
        worker._last_rpa_inventory = bridge.inventory
        assert worker.shop_session_health.report(replacement)["sessionStatus"] is None
        valid = True
        assert worker.shop_session_health.due([replacement]) == replacement
        await worker._verify_local_shop(bridge.inventory, replacement)
        assert worker.shop_session_health.report(replacement)["sessionStatus"] == "valid"
        assert len(bridge.refreshes) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("skill,kind", [
    ("douyin.category_schema", "merchant"),
    ("douyin.merchant_products", "merchant"),
    ("douyin.compass_selection", "compass"),
])
@pytest.mark.parametrize("condition", ["same", "changed", "synthetic"])
def test_real_task_expiry_is_bound_and_survives_restart(tmp_path, skill, kind, condition):
    async def scenario():
        shop = make_shop()
        bridge = Bridge([shop])
        worker = make_worker(tmp_path, bridge, lambda request: httpx.Response(503))
        params = ({"local_shop_id": "a", "platform_shop_id": "123"} if skill == "douyin.category_schema"
                  else {"operation": "list" if skill == "douyin.merchant_products" else "rank"})
        if condition == "synthetic" and skill == "douyin.category_schema":
            params["skip_expired_session"] = True
        task = make_task(skill, shop, input_data=params)
        calls = []

        async def revision(local, platform):
            calls.append(1)
            return "b" * 64 if condition == "changed" and len(calls) > 1 else "a" * 64

        bridge.session_revision = revision

        async def execute(_task):
            return ExecutionResult(status="failed", error_code="SHOP_SESSION_EXPIRED",
                                   result={"http_status": None if condition == "synthetic" else 200})

        async def noop(*args):
            pass

        async def deliver():
            return True

        worker._send_immediate_heartbeat = noop
        worker._execute_with_selection_interval = execute
        worker._renew_lease = lambda _task: asyncio.Event().wait()
        worker._deliver_pending_terminals = deliver
        await worker._execute_task(task)
        # Synthetic skip exists only on precheck; other skills represent a real
        # explicit platform error even if their result has no HTTP metadata.
        expected = condition == "same" or (condition == "synthetic" and skill != "douyin.category_schema")
        assert bool(worker.session_recovery_outbox.pending()) is expected
        if not expected:
            assert worker.shop_session_health.report(shop)["sessionStatus"] is None
            return
        restarted = make_worker(tmp_path, bridge, lambda request: httpx.Response(503))
        restarted._restore_session_recoveries([shop])
        status = restarted.shop_session_health.report(shop)
        assert status["compassSessionStatus" if kind == "compass" else "sessionStatus"] == "invalid"
        assert restarted._take_pending_shop_refresh([shop]) == shop
        await restarted.shop_session_health.request_refresh(shop)
        assert bridge.refreshes[0][-1] is (kind == "compass")
        replacement = shop.model_copy(update={"session_revision": "c" * 64})
        restarted._restore_session_recoveries([replacement])
        assert restarted.session_recovery_outbox.pending() == []
        assert restarted.shop_session_health.report(replacement)["sessionStatus"] is None

    asyncio.run(scenario())


def test_other_shop_continues_while_same_shop_waits_for_asynchronous_rpa(tmp_path):
    async def scenario():
        shop, other = make_shop(), make_shop("b", "456", "b" * 64)
        bridge = Bridge([shop, other])
        bridge.auto_finish = False
        worker = make_worker(tmp_path, bridge, lambda request: httpx.Response(503))
        running = uuid4()
        worker._active_task_ids.add(running)
        worker._active_health_scopes[running] = ("456", True)
        worker.shop_session_health.record_explicit_failure(shop, "merchant")
        refresh = asyncio.create_task(worker._run_shop_refresh(shop))
        await asyncio.wait_for(bridge.refreshed.wait(), timeout=2)
        same_task = make_task("douyin.merchant_products", shop, input_data={"operation": "list"})
        other_task = make_task("douyin.merchant_products", other, input_data={"operation": "list"})
        waiting = asyncio.create_task(worker._wait_for_shop_refresh(same_task))
        await asyncio.wait_for(worker._wait_for_shop_refresh(other_task), timeout=1)
        assert not waiting.done()
        bridge.revisions["a"] = "c" * 64
        await asyncio.wait_for(refresh, timeout=5)
        await asyncio.wait_for(waiting, timeout=1)
        assert len(bridge.refreshes) == 1

    asyncio.run(scenario())
