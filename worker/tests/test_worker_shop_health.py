import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import httpx

from app.client import WorkerApiClient
from app.config import WorkerSettings
from app.contracts import ExecutionResult, LocalShopContext, WorkerTask
from app.rpa_session_bridge import LocalCookie, LocalSession, LocalShop
from app.shop_session_health import ShopSessionHealth
from app.worker import Worker


def test_real_work_preempts_background_shop_verification(tmp_path):
    async def scenario():
        started = asyncio.Event()
        cancelled = asyncio.Event()
        executed = asyncio.Event()
        stop = asyncio.Event()
        local_shop = LocalShop(localShopId="local-a", platformShopId="123", shopName="A",
                               platform="douyin", sessionStored=True, sessionRevision="a" * 64)
        inventory = SimpleNamespace(installation_id=uuid4(), shops=[local_shop])
        task = WorkerTask(task_id=uuid4(), skill_id="system.echo", input={},
                          lease_until=datetime.now(UTC) + timedelta(minutes=1))

        class Bridge:
            async def list_shops(self):
                return inventory

        class Health:
            def missing_session_due(self, shops):
                return None

            def invalid_session_due(self, shops):
                return None

            def due(self, shops, *, excluded_platform_ids=frozenset()):
                return shops[0]

            def report(self, shop):
                return {"sessionStatus": None, "sessionCheckedAt": None}

            async def check(self, shop):
                started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()

        class Client:
            async def report_rpa_inventory(self, payload):
                assert payload["shops"][0]["sessionStatus"] is None

            async def claim(self):
                await started.wait()
                return task

            async def close(self):
                pass

        class Executor:
            def can_claim(self):
                return True

        worker = Worker(WorkerSettings(server_url="https://test.invalid", device_id=uuid4(),
            device_token="synthetic", runtime_root=tmp_path, poll_interval_seconds=0.2),
            Client(), Executor(), capability_runtime=object(), rpa_bridge=Bridge())
        worker.shop_session_health = Health()

        async def no_op(*args):
            pass

        async def deliver():
            return True

        async def execute(claimed):
            assert claimed.task_id == task.task_id
            assert cancelled.is_set()
            executed.set()
            stop.set()

        worker._heartbeat_supervisor = lambda event: event.wait()
        worker._refresh_capabilities_if_due = no_op
        worker._deliver_pending_terminals = deliver
        worker._execute_task = execute
        await asyncio.wait_for(worker.run(stop), timeout=5)
        assert executed.is_set()
        assert not worker._active_task_ids

    asyncio.run(scenario())


def test_busy_shop_does_not_block_other_shop_checks(tmp_path):
    async def scenario():
        checked = []
        stop = asyncio.Event()
        shops = [LocalShop(localShopId=f"local-{key}", platformShopId=key, shopName=key,
                           platform="douyin", sessionStored=True, sessionRevision="a" * 64)
                 for key in ("123", "456")]
        inventory = SimpleNamespace(installation_id=uuid4(), shops=shops)

        class Bridge:
            async def list_shops(self):
                return inventory

        class Client:
            async def report_rpa_inventory(self, payload):
                pass

        class Health:
            def missing_session_due(self, shops):
                return None

            def invalid_session_due(self, shops):
                return None

            def due(self, all_shops, *, excluded_platform_ids=frozenset()):
                assert len(all_shops) == 2
                assert excluded_platform_ids == {"123"}
                return next(shop for shop in all_shops if shop.platform_shop_id not in excluded_platform_ids)

            def report(self, shop):
                return {}

            async def check(self, shop):
                checked.append(shop.platform_shop_id)
                stop.set()
                return False

        worker = Worker(WorkerSettings(server_url="https://test.invalid", device_id=uuid4(),
            device_token="synthetic", runtime_root=tmp_path), Client(), object(), rpa_bridge=Bridge())
        worker.shop_session_health = Health()
        task_id = uuid4()
        worker._active_task_ids.add(task_id)
        worker._active_health_scopes[task_id] = ("123", True)
        await asyncio.wait_for(worker._rpa_inventory_loop(stop), timeout=5)
        await worker._cancel_shop_health_probe()
        assert checked == ["456"]

    asyncio.run(scenario())


def test_shop_checks_run_only_in_safe_selection_gaps_and_never_with_precheck(tmp_path):
    async def scenario():
        worker = Worker(WorkerSettings(server_url="https://test.invalid", device_id=uuid4(),
            device_token="synthetic", runtime_root=tmp_path), object(), object())
        selection_id = uuid4()
        worker._active_task_ids.add(selection_id)
        worker._active_health_scopes[selection_id] = ("123", True)
        assert not worker._health_shop_available("123")
        worker._selection_shop_waiting["123"] = asyncio.get_running_loop().time() + 45
        assert worker._health_shop_available("123")
        precheck_id = uuid4()
        worker._active_task_ids.add(precheck_id)
        worker._active_health_scopes[precheck_id] = ("123", False)
        assert not worker._health_shop_available("123")
        worker._active_task_ids.remove(precheck_id)
        worker._selection_shop_waiting["123"] = asyncio.get_running_loop().time() + 10
        assert not worker._health_shop_available("123")
        worker._active_health_scopes[selection_id] = None
        assert not worker._health_shop_available("456")

    asyncio.run(scenario())


def test_only_conflicting_work_preempts_shop_probe(tmp_path):
    async def scenario():
        worker = Worker(WorkerSettings(server_url="https://test.invalid", device_id=uuid4(),
            device_token="synthetic", runtime_root=tmp_path), object(), object())
        cancelled = asyncio.Event()

        async def probe():
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        worker._shop_health_probe_shop = "123"
        worker._shop_health_probe = asyncio.create_task(probe())
        await asyncio.sleep(0)
        other = WorkerTask(task_id=uuid4(), skill_id="douyin.category_schema", input={"platform_shop_id": "456"},
                           lease_until=datetime.now(UTC) + timedelta(minutes=1))
        worker._active_task_ids.add(other.task_id)
        worker._active_health_scopes[other.task_id] = ("456", False)
        await worker._preempt_health_for_task(other)
        assert not cancelled.is_set()
        same = WorkerTask(task_id=uuid4(), skill_id="douyin.compass_selection", input={"operation": "basic"},
                          local_shops=[LocalShopContext(local_shop_id="local-a", platform="douyin", platform_shop_id="123")],
                          lease_until=datetime.now(UTC) + timedelta(minutes=1))
        worker._active_task_ids.add(same.task_id)
        worker._active_health_scopes[same.task_id] = ("123", True)
        await worker._preempt_health_for_task(same)
        assert cancelled.is_set()

    asyncio.run(scenario())


def test_selection_cancels_same_shop_probe_before_platform_request(tmp_path, monkeypatch):
    async def scenario():
        worker = Worker(WorkerSettings(server_url="https://test.invalid", device_id=uuid4(),
            device_token="synthetic", runtime_root=tmp_path, compass_basic_shop_interval_seconds=0.2,
            compass_shop_max_interval_seconds=0.2), object(), object())
        now = asyncio.get_running_loop().time()
        worker._selection_shop_last["123"] = (now, None, None)
        cancelled = asyncio.Event()
        task = WorkerTask(task_id=uuid4(), skill_id="douyin.compass_selection", input={"operation": "basic"},
                          local_shops=[LocalShopContext(local_shop_id="local-a", platform="douyin", platform_shop_id="123")],
                          lease_until=datetime.now(UTC) + timedelta(minutes=1))
        worker._active_task_ids.add(task.task_id)
        worker._active_health_scopes[task.task_id] = ("123", True)

        async def probe():
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        async def execute(claimed):
            assert cancelled.is_set()
            assert asyncio.get_running_loop().time() - now >= 0.19
            return ExecutionResult(status="success")

        worker._prepare_and_execute = execute
        selection = asyncio.create_task(worker._execute_with_selection_interval(task))
        await asyncio.sleep(0.02)
        assert "123" in worker._selection_shop_waiting
        worker._shop_health_probe_shop = "123"
        worker._shop_health_probe = asyncio.create_task(probe())
        await asyncio.sleep(0)
        await asyncio.wait_for(selection, timeout=2)
        assert cancelled.is_set()
        assert "123" not in worker._selection_shop_waiting

    asyncio.run(scenario())


def test_busy_selection_revalidates_same_shop_during_wait_without_overlapping(tmp_path, monkeypatch):
    async def scenario():
        monkeypatch.setattr("app.worker._HEALTH_MIN_SELECTION_GAP", 0.03)
        stopped = asyncio.Event()
        requests = []
        local_shop = LocalShop(localShopId="local-a", platformShopId="123", shopName="A",
                               platform="douyin", sessionStored=True, sessionRevision="a" * 64)
        inventory = SimpleNamespace(installation_id=uuid4(), shops=[local_shop])

        class Bridge:
            async def list_shops(self):
                return inventory

            async def session_revision(self, *_args):
                return "a" * 64

            async def read_session(self, *_args):
                return LocalSession(localShopId="local-a", platformShopId="123", platform="douyin",
                    userAgent="test-agent", cookies=[LocalCookie(name="test", value="synthetic",
                                                                   domain="jinritemai.com", path="/")])

        class Client:
            async def report_rpa_inventory(self, payload):
                if payload["shops"][0].get("compassSessionStatus") == "valid":
                    stopped.set()

        def identity(request):
            requests.append(request.url.host)
            if request.url.host == "compass.jinritemai.com":
                return httpx.Response(200, json={"st": 0, "data": {"shop_id": "123"}})
            return httpx.Response(200, json={"code": 0, "data": {"id": "123"}})

        bridge = Bridge()
        worker = Worker(WorkerSettings(server_url="https://test.invalid", device_id=uuid4(),
            device_token="synthetic", runtime_root=tmp_path, compass_basic_shop_interval_seconds=0.3,
            compass_shop_max_interval_seconds=0.3), Client(), object(), rpa_bridge=bridge)
        worker.shop_session_health = ShopSessionHealth(bridge, transport=httpx.MockTransport(identity))
        now = asyncio.get_running_loop().time()
        worker._selection_shop_last["123"] = (now, None, None)
        task = WorkerTask(task_id=uuid4(), skill_id="douyin.compass_selection", input={"operation": "basic"},
                          local_shops=[LocalShopContext(local_shop_id="local-a", platform="douyin", platform_shop_id="123")],
                          lease_until=datetime.now(UTC) + timedelta(minutes=1))
        worker._active_task_ids.add(task.task_id)
        worker._active_health_scopes[task.task_id] = ("123", True)

        async def execute(_task):
            assert stopped.is_set()
            assert worker._shop_health_probe is None
            assert asyncio.get_running_loop().time() - now >= 0.29
            return ExecutionResult(status="success")

        worker._prepare_and_execute = execute
        selection = asyncio.create_task(worker._execute_with_selection_interval(task))
        await asyncio.sleep(0.01)
        await asyncio.wait_for(worker._rpa_inventory_loop(stopped), timeout=2)
        await asyncio.wait_for(selection, timeout=2)
        assert requests == ["compass.jinritemai.com", "fxg.jinritemai.com"]
        assert worker.shop_session_health.report(local_shop)["compassSessionStatus"] == "valid"

    asyncio.run(scenario())


def test_refresh_discovered_during_other_work_is_deferred_until_idle(tmp_path):
    async def scenario():
        local_shop = LocalShop(localShopId="local-a", platformShopId="123", shopName="A",
                               platform="douyin", sessionStored=True, sessionRevision="a" * 64)
        inventory = SimpleNamespace(installation_id=uuid4(), shops=[local_shop])
        refreshed = []

        class Client:
            async def report_rpa_inventory(self, _payload):
                pass

        class Health:
            async def check(self, _shop):
                return True

            async def request_refresh(self, shop):
                refreshed.append(shop.platform_shop_id)

            def report(self, _shop):
                return {}

        worker = Worker(WorkerSettings(server_url="https://test.invalid", device_id=uuid4(),
            device_token="synthetic", runtime_root=tmp_path), Client(), object())
        worker.shop_session_health = Health()
        worker._last_rpa_inventory = inventory
        worker._active_task_ids.add(uuid4())
        await worker._verify_local_shop(inventory, local_shop)
        assert refreshed == []
        worker._active_task_ids.clear()
        assert worker._take_pending_shop_refresh([local_shop]) is local_shop
        assert worker._take_pending_shop_refresh([local_shop]) is None
        worker._pending_shop_refresh[(local_shop.local_shop_id, local_shop.platform_shop_id)] = local_shop
        replacement = local_shop.model_copy(update={"session_revision": "b" * 64})
        assert worker._take_pending_shop_refresh([replacement]) is None

    asyncio.run(scenario())


def test_new_worker_keeps_inventory_compatible_with_old_backend(tmp_path, monkeypatch):
    async def scenario():
        now = [100.0]
        supports_status = [False]
        requests = []
        monkeypatch.setattr("app.client.monotonic", lambda: now[0])

        def handler(request):
            import json
            body = json.loads(request.content)
            extended = "sessionStatus" in body["shops"][0] or "compassSessionVerified" in body["shops"][0]
            requests.append(extended)
            return httpx.Response(422 if extended and not supports_status[0] else 204)

        settings = WorkerSettings(server_url="https://test.invalid", device_id=uuid4(),
                                  device_token="synthetic", runtime_root=tmp_path)
        payload = {"available": True, "installation_id": str(uuid4()), "shops": [
            {"localShopId": "a", "platformShopId": "1", "shopName": "A", "platform": "douyin",
             "sessionStatus": "valid", "sessionCheckedAt": datetime.now(UTC).isoformat(),
             "compassSessionVerified": True},
        ]}
        async with httpx.AsyncClient(base_url="https://test.invalid", transport=httpx.MockTransport(handler)) as http:
            client = WorkerApiClient(settings, client=http)
            await client.report_rpa_inventory(payload)
            await client.report_rpa_inventory(payload)
            assert requests == [True, False, False]
            supports_status[0] = True
            now[0] += 301
            await client.report_rpa_inventory(payload)
            assert requests[-1] is True
            assert payload["shops"][0]["sessionStatus"] == "valid"
            assert payload["shops"][0]["compassSessionVerified"] is True

    asyncio.run(scenario())


def test_compass_observation_falls_back_to_previous_server_without_losing_merchant_status(tmp_path):
    async def scenario():
        bodies = []

        def handler(request):
            import json
            body = json.loads(request.content)
            bodies.append(body)
            return httpx.Response(422 if "compassSessionStatus" in body["shops"][0] else 204)

        settings = WorkerSettings(server_url="https://test.invalid", device_id=uuid4(),
                                  device_token="synthetic", runtime_root=tmp_path)
        payload = {"available": True, "installation_id": str(uuid4()), "shops": [{
            "localShopId": "a", "platformShopId": "1", "shopName": "A", "platform": "douyin",
            "sessionStatus": "valid", "sessionCheckedAt": datetime.now(UTC).isoformat(),
            "compassSessionVerified": True, "compassSessionStatus": "valid",
            "compassSessionCheckedAt": datetime.now(UTC).isoformat(),
        }]}
        async with httpx.AsyncClient(base_url="https://test.invalid", transport=httpx.MockTransport(handler)) as http:
            client = WorkerApiClient(settings, client=http)
            await client.report_rpa_inventory(payload)
            await client.report_rpa_inventory(payload)
        assert len(bodies) == 3
        assert bodies[1]["shops"][0]["sessionStatus"] == "valid"
        assert bodies[1]["shops"][0]["compassSessionVerified"] is True
        assert "compassSessionStatus" not in bodies[1]["shops"][0]
        assert "compassSessionStatus" not in bodies[2]["shops"][0]

    asyncio.run(scenario())
