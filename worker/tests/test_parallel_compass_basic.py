import asyncio
from collections import Counter, deque
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx

from app.client import WorkerApiClient
from app.config import WorkerSettings
from app.contracts import ExecutionResult, ExecutionStatus, WorkerTask
from app.worker import Worker


def test_five_shops_run_mixed_selection_in_parallel_and_prechecks_continue(tmp_path):
    async def scenario():
        stop, delivered = asyncio.Event(), asyncio.Event()
        active, peaks, windows = Counter(), Counter(), {}
        active_total = peak_total = 0
        precheck_started_with_basic = False

        def selection(shop, product, operation):
            return WorkerTask(task_id=uuid4(), skill_id='douyin.compass_selection',
                input={'operation': operation, 'product_id': str(product), 'page_no': 1},
                local_shops=[{'local_shop_id': shop, 'platform': 'douyin', 'platform_shop_id': shop}],
                result_delivery='operations', lease_until=datetime.now(UTC) + timedelta(minutes=2))

        class Runtime:
            class updater:
                @staticmethod
                async def sync_when_idle(*args, **kwargs): return False
            def descriptors(self): return ()
            def refresh(self): pass
            def validate_entry(self, *args): pass
            def has_skill(self, _skill): return True
            async def execute(self, task):
                nonlocal active_total, peak_total, precheck_started_with_basic
                if task.skill_id == 'douyin.category_schema':
                    precheck_started_with_basic = precheck_started_with_basic or active_total > 0
                    await asyncio.sleep(0.01)
                    return ExecutionResult(status=ExecutionStatus.SUCCESS, result={'ok': True})
                shop = task.local_shops[0].local_shop_id
                active[shop] += 1
                active_total += 1
                peaks[shop] = max(peaks[shop], active[shop])
                peak_total = max(peak_total, active_total)
                start = asyncio.get_running_loop().time()
                await asyncio.sleep(0.03)
                end = asyncio.get_running_loop().time()
                windows.setdefault(shop, []).append((start, end))
                active[shop] -= 1
                active_total -= 1
                return ExecutionResult(status=ExecutionStatus.SUCCESS,
                    result={'kind': 'douyin.compass_selection', 'operation': task.input['operation'],
                            'platform_shop_id': shop, 'data': {'product_id': task.input['product_id']}})

        class Client:
            def __init__(self):
                operations = ('rank', 'categories', 'basic', 'rank', 'categories')
                self.basics = deque(selection(f'shop-{shop}', item * 10 + shop,
                    operations[shop] if item == 0 else 'basic')
                    for item in range(2) for shop in range(5))
                self.prechecks = deque(WorkerTask(task_id=uuid4(), skill_id='douyin.category_schema',
                    input={'platform_shop_id': f'precheck-{i}'},
                    lease_until=datetime.now(UTC) + timedelta(minutes=2)) for i in range(2))
                self.results = {}
            async def heartbeat(self, **kwargs): pass
            async def report_skill_capabilities(self, snapshot): pass
            async def report_rpa_inventory(self, payload): pass
            async def claim(self): return self.basics.popleft() if self.basics else None
            async def claim_parallel(self, kind):
                queue = self.prechecks if kind == 'precheck' else self.basics
                return queue.popleft() if queue else None
            async def deliver_operations_selection(self, task_id, **kwargs):
                self.results[task_id] = kwargs['result']
                return 'a' * 64
            async def acknowledge_operations_selection(self, task_id, **kwargs):
                if len(self.results) == 10: delivered.set()
            async def complete_precheck(self, task_id, **kwargs): pass
            async def renew(self, task_id): pass
            async def close(self): pass

        client = Client()
        settings = WorkerSettings(server_url='https://central.test', device_id=uuid4(), device_token='synthetic',
            runtime_root=tmp_path, poll_interval_seconds=0.2, compass_basic_shop_interval_seconds=0.06,
            compass_shop_max_interval_seconds=0.06)
        worker = Worker(settings, client, executor=type('Executor', (), {'can_claim': lambda self: True})(),
                        capability_runtime=Runtime())
        running = asyncio.create_task(worker.run(stop))
        try:
            await asyncio.wait_for(delivered.wait(), 5)
        finally:
            stop.set()
            await asyncio.wait_for(running, 5)
        assert peak_total == 5
        assert set(peaks.values()) == {1}
        assert len(windows) == 5 and all(len(times) == 2 for times in windows.values())
        assert all(times[1][0] - times[0][1] >= 0.055 for times in windows.values())
        assert precheck_started_with_basic
        assert len(client.results) == 10 and not worker.result_outbox.pending()

    asyncio.run(scenario())


def test_rank_pages_are_fast_but_other_same_shop_tasks_wait_and_other_shops_run(tmp_path, monkeypatch):
    async def scenario():
        active, peaks, windows = Counter(), Counter(), {}
        active_total = peak_total = 0
        def task(shop, operation, page=1):
            return WorkerTask(task_id=uuid4(), skill_id='douyin.compass_selection',
                input={'operation': operation, 'page_no': page, 'category_id': '1'},
                local_shops=[{'local_shop_id': shop, 'platform': 'douyin', 'platform_shop_id': shop}],
                result_delivery='operations', lease_until=datetime.now(UTC) + timedelta(minutes=2))
        class Runtime:
            def has_skill(self, _skill): return True
            async def execute(self, item):
                nonlocal active_total, peak_total
                shop = item.local_shops[0].platform_shop_id
                active[shop] += 1
                active_total += 1
                peak_total = max(peak_total, active_total)
                peaks[shop] = max(peaks[shop], active[shop])
                start = asyncio.get_running_loop().time()
                await asyncio.sleep(0.01)
                windows.setdefault(shop, []).append((item.input['operation'], item.input['page_no'],
                                                    start, asyncio.get_running_loop().time()))
                active[shop] -= 1
                active_total -= 1
                return ExecutionResult(status=ExecutionStatus.SUCCESS, result={})
        monkeypatch.setattr('app.worker.random.uniform', lambda a, b: a)
        settings = WorkerSettings(server_url='https://central.test', device_id=uuid4(), device_token='synthetic',
            runtime_root=tmp_path, compass_basic_shop_interval_seconds=0.08,
            compass_shop_max_interval_seconds=0.12, compass_page_min_interval_seconds=0.02,
            compass_page_max_interval_seconds=0.04)
        worker = Worker(settings, client=None, executor=None, capability_runtime=Runtime())
        a1, a2, a3, b1 = task('a','rank',1), task('a','rank',2), task('a','basic'), task('b','categories')
        await asyncio.gather(*(worker._execute_with_selection_interval(t) for t in (a1,a2,a3,b1)))
        assert set(peaks.values()) == {1}
        a = windows['a']
        assert [row[:2] for row in a] == [('rank',1),('rank',2),('basic',1)]
        assert 0.018 <= a[1][2] - a[0][3] < 0.07
        assert a[2][2] - a[1][3] >= 0.075
        assert peak_total == 2
    asyncio.run(scenario())


def test_parallel_claim_is_safe_with_an_older_backend(tmp_path):
    async def scenario():
        settings = WorkerSettings(server_url='https://central.test', device_id=uuid4(),
                                  device_token='synthetic', runtime_root=tmp_path)
        async with httpx.AsyncClient(base_url='https://central.test', transport=httpx.MockTransport(
                lambda request: httpx.Response(404))) as client:
            api = WorkerApiClient(settings, client=client)
            assert await api.claim_parallel('basic') is None
            assert api.parallel_claim_supported is False
    asyncio.run(scenario())


def test_selection_claim_falls_back_to_basic_on_old_backend(tmp_path):
    async def scenario():
        settings = WorkerSettings(server_url='https://central.test', device_id=uuid4(),
                                  device_token='synthetic', runtime_root=tmp_path)
        calls = []
        def respond(request):
            calls.append(request.url.params['kind'])
            return httpx.Response(422 if calls[-1] == 'selection' else 204)
        async with httpx.AsyncClient(base_url='https://central.test', transport=httpx.MockTransport(respond)) as client:
            api = WorkerApiClient(settings, client=client)
            assert await api.claim_parallel('selection') is None
        assert calls == ['selection', 'basic']
    asyncio.run(scenario())
