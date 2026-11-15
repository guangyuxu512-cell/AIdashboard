import asyncio
from collections import Counter, deque
from datetime import UTC, datetime, timedelta
import json
from uuid import uuid4

import httpx

from app.client import WorkerApiClient
from app.config import WorkerSettings
from app.contracts import ExecutionResult, ExecutionStatus, RuntimeEventType, WorkerTask
from app.runtime_events import LocalRuntimeState, RuntimeEventBus
from app.worker import Worker


def test_five_independent_workers_run_three_tasks_for_five_shops(tmp_path):
    async def scenario():
        release = asyncio.Event()
        all_started = asyncio.Event()
        all_delivered = asyncio.Event()
        stop = asyncio.Event()
        active = Counter()
        active_by_shop = Counter()
        peak_by_shop = Counter()
        peak_by_worker = Counter()
        total_started = 0
        total_delivered = 0
        peak_total = 0

        class Updater:
            async def sync_when_idle(self, *args, **kwargs):
                return False

        class Runtime:
            updater = Updater()

            def descriptors(self):
                return ()

            def validate_entry(self, *args):
                pass

            def refresh(self):
                pass

            def has_skill(self, skill_id):
                return skill_id == "douyin.category_schema"

            async def execute(self, task):
                nonlocal total_started, peak_total
                worker_id, shop_id = task.input["worker"], task.input["platform_shop_id"]
                active[worker_id] += 1
                active_by_shop[(worker_id, shop_id)] += 1
                peak_by_worker[worker_id] = max(peak_by_worker[worker_id], active[worker_id])
                peak_by_shop[(worker_id, shop_id)] = max(peak_by_shop[(worker_id, shop_id)], active_by_shop[(worker_id, shop_id)])
                total_started += 1
                peak_total = max(peak_total, sum(active.values()))
                if total_started == 75:
                    all_started.set()
                await release.wait()
                active[worker_id] -= 1
                active_by_shop[(worker_id, shop_id)] -= 1
                return ExecutionResult(status=ExecutionStatus.SUCCESS, result={"ok": True})

        class Client:
            def __init__(self, worker_id):
                self.tasks = deque(WorkerTask(
                    task_id=uuid4(), skill_id="douyin.category_schema",
                    input={"worker": worker_id, "platform_shop_id": f"{worker_id}-{shop}"},
                    lease_until=datetime.now(UTC) + timedelta(minutes=5),
                ) for shop in range(5) for _ in range(3))
                self.delivered = set()

            async def heartbeat(self, **kwargs):
                pass

            async def report_skill_capabilities(self, snapshot):
                pass

            async def report_rpa_inventory(self, payload):
                pass

            async def claim(self):
                return self.tasks.popleft() if self.tasks else None

            async def claim_precheck(self):
                return self.tasks.popleft() if self.tasks else None

            async def complete_precheck(self, task_id, **kwargs):
                nonlocal total_delivered
                assert task_id not in self.delivered
                self.delivered.add(task_id)
                total_delivered += 1
                if total_delivered == 75:
                    all_delivered.set()

            async def renew(self, task_id):
                pass

            async def close(self):
                pass

        class Executor:
            def can_claim(self):
                return True

        runtime = Runtime()
        clients = [Client(i) for i in range(5)]
        workers = [Worker(WorkerSettings(server_url="https://test.invalid", device_id=uuid4(),
            device_token="synthetic", runtime_root=tmp_path / str(i), poll_interval_seconds=0.2),
            clients[i], Executor(), capability_runtime=runtime) for i in range(5)]
        runs = [asyncio.create_task(worker.run(stop)) for worker in workers]
        try:
            await asyncio.wait_for(all_started.wait(), 15)
            assert peak_total == 75
            assert list(peak_by_worker.values()) == [15] * 5
            assert len(peak_by_shop) == 25 and set(peak_by_shop.values()) == {3}
            release.set()
            await asyncio.wait_for(all_delivered.wait(), 15)
        finally:
            release.set()
            stop.set()
            await asyncio.wait_for(asyncio.gather(*runs), 15)
        assert all(len(client.delivered) == 15 for client in clients)

    asyncio.run(scenario())


def test_local_status_remains_busy_until_last_concurrent_task_finishes(tmp_path):
    path = tmp_path / "runtime.json"
    state = LocalRuntimeState(path=path, device_id=uuid4())
    bus = RuntimeEventBus()
    bus.subscribe(state.consume)
    tasks = [WorkerTask(task_id=uuid4(), skill_id="douyin.category_schema", input={},
                        lease_until=datetime.now(UTC) + timedelta(minutes=1)) for _ in range(3)]
    for task in tasks:
        state.begin_task(task, skill_display_name="商品预检")
    state.finish_task(tasks[-1].task_id)
    bus.emit(tasks[-1].task_id, RuntimeEventType.LOG, "late")
    current = json.loads(path.read_text(encoding="utf-8"))
    assert current["active_task_count"] == 2
    assert current["current_task_id"] in {str(tasks[0].task_id), str(tasks[1].task_id)}
    state.finish_task(tasks[0].task_id)
    state.finish_task(tasks[1].task_id)
    current = json.loads(path.read_text(encoding="utf-8"))
    assert current["active_task_count"] == 0 and current["current_task_id"] is None


def test_capacity_refills_and_normal_shutdown_waits_for_running_tasks(tmp_path):
    async def scenario():
        started_15, started_16, release_one, release_rest, stop = (asyncio.Event() for _ in range(5))
        started = 0
        active = 0
        peak = 0

        class Runtime:
            class updater:
                @staticmethod
                async def sync_when_idle(*args, **kwargs):
                    return False

            def descriptors(self): return ()
            def refresh(self): pass
            def validate_entry(self, *args): pass
            def has_skill(self, skill_id): return True

            async def execute(self, task):
                nonlocal started, active, peak
                started += 1
                active += 1
                peak = max(peak, active)
                if started == 15: started_15.set()
                if started == 16: started_16.set()
                await (release_one if task.input["index"] == 0 else release_rest).wait()
                active -= 1
                return ExecutionResult(status=ExecutionStatus.SUCCESS, result={"ok": True})

        class Client:
            def __init__(self):
                self.tasks = deque(WorkerTask(task_id=uuid4(), skill_id="douyin.category_schema",
                    input={"index": index, "platform_shop_id": str(index % 6)},
                    lease_until=datetime.now(UTC) + timedelta(minutes=5)) for index in range(16))
                self.delivered = []
                self.closed = False

            async def heartbeat(self, **kwargs): pass
            async def report_skill_capabilities(self, snapshot): pass
            async def report_rpa_inventory(self, payload): pass
            async def renew(self, task_id): pass
            async def claim(self): return self.tasks.popleft() if self.tasks else None
            async def claim_precheck(self): return self.tasks.popleft() if self.tasks else None
            async def complete_precheck(self, task_id, **kwargs): self.delivered.append(task_id)
            async def close(self): self.closed = True

        class Executor:
            def can_claim(self): return True

        client = Client()
        worker = Worker(WorkerSettings(server_url="https://test.invalid", device_id=uuid4(),
            device_token="synthetic", runtime_root=tmp_path, poll_interval_seconds=0.2),
            client, Executor(), capability_runtime=Runtime())
        run = asyncio.create_task(worker.run(stop))
        try:
            await asyncio.wait_for(started_15.wait(), 5)
            await asyncio.sleep(0.3)
            assert started == peak == 15 and len(client.tasks) == 1
            release_one.set()
            await asyncio.wait_for(started_16.wait(), 5)
            assert peak == 15
            stop.set()
            await asyncio.sleep(0.1)
            assert not run.done() and not client.closed
        finally:
            release_one.set()
            release_rest.set()
            stop.set()
            await asyncio.wait_for(run, 10)
        assert len(client.delivered) == 16 and len(set(client.delivered)) == 16

    asyncio.run(scenario())


def test_old_backend_does_not_claim_an_unrelated_task_for_a_parallel_slot():
    async def scenario():
        paths = []

        def route(request):
            paths.append(request.url.path)
            return httpx.Response(404)

        settings = WorkerSettings(server_url="https://test.invalid", device_id=uuid4(), device_token="synthetic")
        async with httpx.AsyncClient(base_url="https://test.invalid", transport=httpx.MockTransport(route)) as client:
            api = WorkerApiClient(settings, client=client)
            assert await api.claim_precheck() is None
        assert paths == ["/api/v1/worker/tasks/claim-precheck"]

    asyncio.run(scenario())


def test_parallel_results_survive_disconnect_and_reach_product_once(tmp_path):
    async def scenario():
        executions = Counter()

        class Runtime:
            def has_skill(self, skill_id): return True

            async def execute(self, task):
                executions[task.task_id] += 1
                return ExecutionResult(status=ExecutionStatus.SUCCESS, result={"ok": True})

        class Client:
            connected = False
            delivered = Counter()
            acknowledged = Counter()

            async def heartbeat(self, **kwargs): pass
            async def renew(self, task_id): pass

            async def deliver_product_precheck(self, task_id, **kwargs):
                if not self.connected:
                    raise httpx.ConnectError("synthetic offline")
                self.delivered[task_id] += 1
                return "a" * 64

            async def acknowledge_product_precheck(self, task_id, **kwargs):
                self.acknowledged[task_id] += 1

        client = Client()
        worker = Worker(WorkerSettings(server_url="https://test.invalid", device_id=uuid4(),
            device_token="synthetic", runtime_root=tmp_path), client, object(), capability_runtime=Runtime())
        tasks = [WorkerTask(task_id=uuid4(), skill_id="douyin.category_schema", input={},
            result_delivery="product", lease_until=datetime.now(UTC) + timedelta(minutes=5)) for _ in range(3)]
        await asyncio.gather(*(worker._execute_task(task) for task in tasks))
        assert len(worker.result_outbox.pending()) == 3
        client.connected = True
        assert all(await asyncio.gather(*(worker._deliver_pending_terminals() for _ in range(3))))
        assert worker.result_outbox.pending() == []
        assert set(executions.values()) == {1}
        assert set(client.delivered.values()) == {1} and len(client.delivered) == 3
        assert set(client.acknowledged.values()) == {1} and len(client.acknowledged) == 3

    asyncio.run(scenario())
