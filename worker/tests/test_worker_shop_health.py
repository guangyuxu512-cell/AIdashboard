import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import httpx

from app.client import WorkerApiClient
from app.config import WorkerSettings
from app.contracts import WorkerTask
from app.rpa_session_bridge import LocalShop
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

            def due(self, shops):
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
