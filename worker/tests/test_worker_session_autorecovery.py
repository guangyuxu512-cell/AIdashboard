import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from app.config import WorkerSettings
from app.contracts import ExecutionResult, LocalShopContext, WorkerTask
from app.rpa_session_bridge import LocalCookie, LocalRefreshStatus, LocalSession, LocalShop, RpaBridgeError
from app.result_outbox import TerminalDelivery
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

    async def session_identity(self, local_id, platform_id):
        return str(self.inventory.installation_id), await self.session_revision(local_id, platform_id)

    async def read_session(self, local_id, platform_id):
        return LocalSession(localShopId=local_id, platformShopId=platform_id, platform="douyin",
                            userAgent="test", cookies=[LocalCookie(name="test", value="synthetic",
                                domain="fxg.jinritemai.com", path="/")])

    async def session_refresh_status(self, *args):
        return self.status

    async def request_session_refresh(self, *args, **_kwargs):
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


def test_changed_snapshot_forces_fresh_inventory_without_reporting_old_status(tmp_path):
    async def scenario():
        shop = make_shop()
        bridge = Bridge([shop])
        worker = make_worker(tmp_path, bridge, lambda request: httpx.Response(503))
        worker._force_inventory_read = False
        bridge.revisions["a"] = "b" * 64
        assert worker.shop_session_health.prioritize(shop, {"merchant"})
        await worker._verify_local_shop(bridge.inventory, shop)
        assert worker._force_inventory_read is True
        assert worker._rpa_inventory_wakeup.is_set()
        assert worker.shop_session_health.report(shop)["sessionStatus"] is None
        assert bridge.refreshes == []

    asyncio.run(scenario())


def test_changed_mapping_forces_inventory_without_triggering_login(tmp_path):
    async def scenario():
        shop = make_shop()
        bridge = Bridge([shop])
        worker = make_worker(tmp_path, bridge, lambda request: httpx.Response(503))
        worker._force_inventory_read = False

        async def mismatch(*args):
            raise RpaBridgeError('RPA_SHOP_IDENTITY_MISMATCH')

        bridge.read_session = mismatch
        assert worker.shop_session_health.prioritize(shop, {'merchant'})
        await worker._verify_local_shop(bridge.inventory, shop)
        assert worker._force_inventory_read
        assert not bridge.refreshes
        worker._force_inventory_read = False
        worker._queue_session_recheck(make_task('douyin.merchant_products', shop),
                                      ExecutionResult(status='failed', error_code='RPA_SHOP_IDENTITY_MISMATCH'))
        assert worker._force_inventory_read
        assert not worker._pending_shop_refresh

    asyncio.run(scenario())


def test_force_requested_during_inventory_read_is_not_lost(tmp_path):
    async def scenario():
        inventory = SimpleNamespace(installation_id=uuid4(), shops=[])
        started, release, stop = asyncio.Event(), asyncio.Event(), asyncio.Event()
        class BlockingBridge:
            calls = 0
            async def list_shops(self):
                self.calls += 1
                if self.calls == 1:
                    started.set()
                    await release.wait()
                else:
                    stop.set()
                return inventory
        bridge = BlockingBridge()
        bridge.inventory = inventory
        worker = make_worker(tmp_path, bridge, lambda request: httpx.Response(503))
        loop = asyncio.create_task(worker._rpa_inventory_loop(stop))
        await started.wait()
        worker._force_inventory_read = True
        worker._rpa_inventory_wakeup.set()
        release.set()
        await asyncio.wait_for(loop, timeout=2)
        assert bridge.calls == 2

    asyncio.run(scenario())


def test_unavailable_report_is_ordered_after_inflight_available_report(tmp_path):
    async def scenario():
        bridge = Bridge([make_shop()])
        worker = make_worker(tmp_path, bridge, lambda request: httpx.Response(503))
        started, release = asyncio.Event(), asyncio.Event()
        order = []
        class Client:
            async def report_rpa_inventory(self, payload):
                if payload['available']:
                    started.set()
                    await release.wait()
                order.append(payload['available'])
        worker.client = Client()
        first = asyncio.create_task(worker._report_rpa_inventory(bridge.inventory))
        await started.wait()
        worker._last_rpa_inventory = None
        second = asyncio.create_task(worker._report_inventory_unavailable())
        await asyncio.sleep(0.01)
        assert order == []
        release.set()
        await asyncio.gather(first, second)
        assert order == [True, False]

    asyncio.run(scenario())


def test_worker_update_waits_even_when_refresh_task_has_not_started(tmp_path):
    async def scenario():
        worker = make_worker(tmp_path, Bridge([]), lambda request: httpx.Response(503))
        worker.base_updater = object()
        worker._shop_refresh_task = asyncio.create_task(asyncio.Event().wait())
        assert not await worker._update_base_if_idle()
        worker._shop_refresh_task.cancel()
        await asyncio.gather(worker._shop_refresh_task, return_exceptions=True)

    asyncio.run(scenario())


def test_worker_update_rechecks_refresh_after_download(tmp_path, monkeypatch):
    async def scenario():
        worker = make_worker(tmp_path, Bridge([]), lambda request: httpx.Response(503))
        started, release = asyncio.Event(), asyncio.Event()
        class Updater:
            async def stage_when_idle(self, *args, **kwargs):
                started.set()
                await release.wait()
                return object()
        worker.base_updater = Updater()
        called = []
        monkeypatch.setattr('app.base_update_handoff.start_handoff', lambda *args: called.append(True))
        update = asyncio.create_task(worker._update_base_if_idle())
        await started.wait()
        worker._shop_refresh_task = asyncio.create_task(asyncio.Event().wait())
        release.set()
        assert not await update
        assert not called
        worker._shop_refresh_task.cancel()
        await asyncio.gather(worker._shop_refresh_task, return_exceptions=True)

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
        if worker._shop_refresh_task is not None:
            await worker._shop_refresh_task
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


def test_one_shops_slow_refresh_does_not_block_other_shop_health(tmp_path, monkeypatch):
    async def scenario():
        monkeypatch.setattr("app.worker._HEALTH_BETWEEN_SHOPS_SECONDS", 0.01)
        first, second = make_shop(), make_shop("b", "456", "b" * 64)
        bridge = Bridge([first, second])
        bridge.auto_finish = False
        stop = asyncio.Event()
        checked = asyncio.Event()

        async def read(local, platform):
            return LocalSession(localShopId=local, platformShopId=platform, platform="douyin", userAgent=platform,
                cookies=[LocalCookie(name="test", value="synthetic", domain="jinritemai.com", path="/")])

        bridge.read_session = read
        def identity(request):
            shop_id = request.headers["user-agent"]
            return (httpx.Response(200, json={"st": 0, "data": {"shop_id": shop_id}})
                    if request.url.host == "compass.jinritemai.com" else
                    httpx.Response(200, json={"code": 0, "data": {"id": shop_id}}))

        worker = make_worker(tmp_path, bridge, identity)
        worker.shop_session_health.record_explicit_failure(first, "merchant")
        class Client:
            async def report_rpa_inventory(self, payload):
                row = next(item for item in payload["shops"] if item["localShopId"] == "b")
                if row.get("sessionStatus") == "valid" and row.get("compassSessionStatus") == "valid":
                    checked.set()
                    stop.set()

        worker.client = Client()
        loop = asyncio.create_task(worker._rpa_inventory_loop(stop))
        await asyncio.wait_for(bridge.refreshed.wait(), timeout=2)
        await asyncio.wait_for(checked.wait(), timeout=2)
        assert not worker._shop_refresh_task.done()
        assert bridge.refreshes[0][0] == "a"
        await asyncio.wait_for(loop, timeout=2)
        worker._shop_refresh_task.cancel()
        await asyncio.gather(worker._shop_refresh_task, return_exceptions=True)

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
        worker._prepare_and_execute = execute
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
        recorded_at = restarted.session_recovery_outbox.pending()[0].result["observed_at"]
        restarted._restore_session_recoveries([shop])
        status = restarted.shop_session_health.report(shop)
        assert status["compassSessionStatus" if kind == "compass" else "sessionStatus"] == "invalid"
        time_field = "compassSessionCheckedAt" if kind == "compass" else "sessionCheckedAt"
        assert status[time_field] == recorded_at
        restarted.shop_session_health.now = lambda: datetime.now(UTC) + timedelta(hours=1)
        restarted._restore_session_recoveries([shop])
        assert restarted.shop_session_health.report(shop)[time_field] == recorded_at
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
        bridge.status = LocalRefreshStatus("saved", datetime.now(UTC))
        await asyncio.wait_for(refresh, timeout=5)
        await asyncio.wait_for(waiting, timeout=1)
        assert len(bridge.refreshes) == 1

    asyncio.run(scenario())


def test_snapshot_is_captured_after_refresh_wait(tmp_path):
    async def scenario():
        shop = make_shop()
        bridge = Bridge([shop])
        worker = make_worker(tmp_path, bridge, lambda request: httpx.Response(503))
        ready = asyncio.Event()
        worker._refresh_done["123"] = ready
        task = make_task("douyin.merchant_products", shop, input_data={"operation": "list"})

        async def fail(_task):
            return ExecutionResult(status="failed", error_code="SHOP_SESSION_EXPIRED")

        worker._prepare_and_execute = fail
        execution = asyncio.create_task(worker._execute_with_selection_interval(task))
        await asyncio.sleep(0.02)
        bridge.revisions["a"] = "b" * 64
        worker._refresh_done.pop("123")
        ready.set()
        await asyncio.wait_for(execution, timeout=1)
        assert worker._task_expiry_revisions[task.task_id] == "b" * 64

    asyncio.run(scenario())


@pytest.mark.parametrize('old_installation', [None, str(uuid4())])
def test_unbound_recovery_does_not_mark_new_installation_invalid_or_log_in(tmp_path, old_installation):
    shop = make_shop()
    bridge = Bridge([shop])
    worker = make_worker(tmp_path, bridge, lambda request: httpx.Response(503))
    result = {'local_shop_id': 'a', 'platform_shop_id': '123', 'kind': 'merchant',
              'snapshot_revision': 'a' * 64, 'observed_at': datetime.now(UTC).isoformat()}
    if old_installation is not None:
        result['installation_id'] = old_installation
    worker.session_recovery_outbox.store(TerminalDelivery(task_id=uuid4(),
        skill_id='douyin.merchant_products', status='failed', result=result,
        error_code='SHOP_SESSION_EXPIRED', error_message='synthetic'))
    worker._restore_session_recoveries([shop])
    assert worker.shop_session_health.report(shop)['sessionStatus'] is None
    assert worker._pending_shop_refresh == {}
    assert worker._session_rechecks == {('a', '123'): {'merchant'}}
    assert bridge.refreshes == []
    worker._session_rechecks.clear()
    worker._restore_session_recoveries([shop])
    assert worker._session_rechecks == {}  # One conservative recheck per process.
    assert len(worker.session_recovery_outbox.pending()) == 1


def test_expiry_from_old_installation_is_not_attached_to_new_installation(tmp_path):
    async def scenario():
        shop = make_shop()
        bridge = Bridge([shop])
        worker = make_worker(tmp_path, bridge, lambda request: httpx.Response(503))
        task = make_task('douyin.merchant_products', shop, input_data={'operation': 'list'})
        async def execute(_task):
            bridge.inventory = SimpleNamespace(installation_id=uuid4(), shops=[shop])
            worker._last_rpa_inventory = bridge.inventory
            return ExecutionResult(status='failed', error_code='SHOP_SESSION_EXPIRED')
        worker._prepare_and_execute = execute
        await worker._execute_with_snapshot_evidence(task)
        assert task.task_id not in worker._task_expiry_revisions
        assert task.task_id not in worker._task_expiry_installations
    asyncio.run(scenario())


def test_explicit_expiry_is_recorded_while_inventory_is_temporarily_unavailable(tmp_path):
    async def scenario():
        shop = make_shop()
        bridge = Bridge([shop])
        worker = make_worker(tmp_path, bridge, lambda request: httpx.Response(503))
        worker._last_rpa_inventory = None
        task = make_task('douyin.merchant_products', shop, input_data={'operation': 'list'})
        async def execute(_task):
            return ExecutionResult(status='failed', error_code='SHOP_SESSION_EXPIRED')
        worker._prepare_and_execute = execute
        await worker._execute_with_snapshot_evidence(task)
        assert worker._task_expiry_revisions[task.task_id] == shop.session_revision
        assert worker._task_expiry_installations[task.task_id] == str(bridge.inventory.installation_id)
    asyncio.run(scenario())


def test_old_installation_inflight_refresh_does_not_block_new_installation(tmp_path):
    async def scenario():
        shop = make_shop()
        bridge = Bridge([shop])
        worker = make_worker(tmp_path, bridge, lambda request: httpx.Response(503))
        done = asyncio.Event()
        worker._refresh_done['123'] = done
        marker = TerminalDelivery(task_id=uuid4(), skill_id='system.rpa_session_refresh', status='failed',
            result={'local_shop_id': 'a', 'platform_shop_id': '123', 'snapshot_revision': 'a' * 64,
                    'started_at': datetime.now(UTC).isoformat(), 'installation_id': str(uuid4())},
            error_code='RPA_REFRESH_PENDING', error_message='synthetic')
        worker.session_refresh_outbox.store(marker)
        await asyncio.wait_for(worker._monitor_refresh(marker, done), timeout=1)
        assert done.is_set()
        assert worker.session_refresh_outbox.pending() == [marker]
        assert bridge.refreshes == []
    asyncio.run(scenario())


def test_inconsistent_success_is_never_treated_as_expired(tmp_path):
    async def scenario():
        shop = make_shop()
        bridge = Bridge([shop])
        worker = make_worker(tmp_path, bridge, lambda request: httpx.Response(503))
        task = make_task("douyin.merchant_products", shop, input_data={"operation": "list"})

        async def inconsistent(_task):
            return ExecutionResult(status="success", error_code="SHOP_SESSION_EXPIRED")

        worker._prepare_and_execute = inconsistent
        result = await worker._execute_with_selection_interval(task)
        worker._queue_session_recheck(task, result)
        assert task.task_id not in worker._task_expiry_revisions
        assert not worker._session_rechecks
        assert not worker._pending_shop_refresh

    asyncio.run(scenario())


@pytest.mark.parametrize("acknowledgement", ["accepted", "lost"])
def test_restart_keeps_inflight_refresh_and_busy_does_not_release_shop(tmp_path, acknowledgement):
    async def scenario():
        shop = make_shop()
        bridge = Bridge([shop])
        bridge.auto_finish = False
        if acknowledgement == "lost":
            async def lost_ack(*args, **_kwargs):
                bridge.refreshes.append(args)
                bridge.refreshed.set()
                raise OSError("ack lost after launch")
            bridge.request_session_refresh = lost_ack
        first = make_worker(tmp_path, bridge, lambda request: httpx.Response(503))
        first.shop_session_health.record_explicit_failure(shop, "merchant")
        running = asyncio.create_task(first._run_shop_refresh(shop))
        await asyncio.wait_for(bridge.refreshed.wait(), timeout=2)
        running.cancel()
        with pytest.raises(asyncio.CancelledError):
            await running
        assert len(first.session_refresh_outbox.pending()) == 1

        bridge.status = LocalRefreshStatus("busy", datetime.now(UTC))
        restarted = make_worker(tmp_path, bridge, lambda request: httpx.Response(503))
        assert "123" in restarted._refresh_done  # Restored before run/claim.
        assert not restarted._refresh_budget_available(shop)
        restarted._force_inventory_read = False
        marker = restarted._resumable_refreshes[0]
        monitor = asyncio.create_task(restarted._monitor_refresh(marker, restarted._refresh_done["123"]))
        same = make_task("douyin.merchant_products", shop, input_data={"operation": "list"})
        waiting = asyncio.create_task(restarted._wait_for_shop_refresh(same))
        await asyncio.sleep(0.05)
        assert not waiting.done()
        assert len(bridge.refreshes) == 1  # Restart did not relaunch RPA.
        bridge.revisions["a"] = "c" * 64
        await asyncio.sleep(0.05)
        assert not waiting.done()  # Saving precedes RPA closing its window.
        bridge.status = LocalRefreshStatus("saved", datetime.now(UTC))
        await asyncio.wait_for(monitor, timeout=5)
        await asyncio.wait_for(waiting, timeout=1)
        assert restarted.session_refresh_outbox.pending() == []
        assert restarted._force_inventory_read

    asyncio.run(scenario())


def test_refresh_does_not_launch_into_a_different_installation(tmp_path):
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()
        shop = make_shop()
        class ChangingBridge(Bridge):
            async def session_refresh_status(self, *args):
                started.set()
                await release.wait()
                return None
            async def request_session_refresh(self, *args, expected_installation_id=None):
                if expected_installation_id != str(self.inventory.installation_id):
                    raise RpaBridgeError('RPA_IDENTITY_MISMATCH')
                self.refreshes.append(args)
                return True
        bridge = ChangingBridge([shop])
        worker = make_worker(tmp_path, bridge, lambda request: httpx.Response(503))
        worker.shop_session_health.record_explicit_failure(shop, 'merchant')
        refresh = asyncio.create_task(worker._run_shop_refresh(shop))
        await started.wait()
        bridge.inventory = SimpleNamespace(installation_id=uuid4(), shops=[shop])
        worker._last_rpa_inventory = bridge.inventory
        release.set()
        await asyncio.wait_for(refresh, timeout=2)
        assert bridge.refreshes == []
        assert worker.session_refresh_outbox.pending() == []
    asyncio.run(scenario())


@pytest.mark.parametrize('next_inventory', ['unavailable', 'other_installation'])
def test_queued_refresh_cannot_rebind_when_inventory_changes(tmp_path, next_inventory):
    async def scenario():
        shop = make_shop()
        bridge = Bridge([shop])
        worker = make_worker(tmp_path, bridge, lambda request: httpx.Response(503))
        old_owner = str(bridge.inventory.installation_id)
        queued = asyncio.create_task(worker._run_shop_refresh(shop, expected_installation_id=old_owner))
        worker._last_rpa_inventory = (None if next_inventory == 'unavailable' else
            SimpleNamespace(installation_id=uuid4(), shops=[shop]))
        await queued
        assert bridge.refreshes == []
        assert worker.session_refresh_outbox.pending() == []
        assert worker._force_inventory_read
    asyncio.run(scenario())


def test_retry_budget_survives_restart_and_resaved_snapshots(tmp_path, monkeypatch):
    async def scenario():
        shop = make_shop()
        bridge = Bridge([shop])
        worker = make_worker(tmp_path, bridge, lambda request: httpx.Response(503))
        now = datetime.now(UTC)
        for index in range(3):
            started = now - timedelta(minutes=6 * (index + 1))
            worker.session_refresh_attempts.store(TerminalDelivery(
                task_id=uuid4(), skill_id="system.rpa_session_attempt", status="failed",
                result={"local_shop_id": "a", "platform_shop_id": "123", "snapshot_revision": "a" * 64,
                        "helper_digest": None, "started_at": started.isoformat()},
                error_code="RPA_REFRESH_ATTEMPT", error_message="attempt"))
        restarted = make_worker(tmp_path, bridge, lambda request: httpx.Response(503))
        assert not restarted._refresh_budget_available(shop)
        assert not restarted._refresh_budget_available(shop.model_copy(update={"session_revision": "b" * 64}))

        class Later(datetime):
            @classmethod
            def now(cls, tz=None):
                return now + timedelta(hours=6, minutes=1)

        monkeypatch.setattr("app.worker.datetime", Later)
        assert restarted._refresh_budget_available(shop)
        assert restarted.session_refresh_attempts.pending() == []
        for index in range(3):
            started = Later.now(UTC) - timedelta(minutes=6 * (index + 1))
            restarted.session_refresh_attempts.store(TerminalDelivery(
                task_id=uuid4(), skill_id="system.rpa_session_attempt", status="failed",
                result={"local_shop_id": "a", "platform_shop_id": "123", "snapshot_revision": "a" * 64,
                        "helper_digest": None, "started_at": started.isoformat()},
                error_code="RPA_REFRESH_ATTEMPT", error_message="attempt"))
            assert restarted._refresh_budget_available(shop) is (index < 2)

    asyncio.run(scenario())
