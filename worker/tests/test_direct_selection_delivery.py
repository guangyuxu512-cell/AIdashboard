import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx

from app.client import WorkerApiClient
from app.config import WorkerSettings
from app.contracts import WorkerTask
from app.result_outbox import TerminalDelivery
from app.worker import Worker


def test_merchant_results_are_durable_and_sent_only_to_the_matching_operations_endpoint(tmp_path):
    task_id, device_id = uuid4(), uuid4()
    settings = WorkerSettings(server_url='https://central.test', device_id=device_id,
                              device_token='synthetic-device-token', runtime_root=tmp_path)
    seen, online = [], False

    def central(request):
        if request.method == 'GET':
            return httpx.Response(200, json={'task_id': str(task_id), 'device_id': str(device_id),
                'skill_id': 'douyin.merchant_products', 'origin': 'https://operations.test'})
        seen.append(request.url.path)
        return httpx.Response(200, json={})

    def operations(request):
        seen.append(request.url.path)
        if not online:
            return httpx.Response(503)
        return httpx.Response(200, json={'task_id': str(task_id), 'accepted': True,
                                         'payload_sha256': hashlib.sha256(request.content).hexdigest()})

    async def scenario():
        nonlocal online
        async with httpx.AsyncClient(base_url='https://central.test', transport=httpx.MockTransport(central)) as c, \
                   httpx.AsyncClient(transport=httpx.MockTransport(operations)) as o:
            api = WorkerApiClient(settings, client=c, operations_client=o)
            worker = Worker(settings, api, executor=None)
            worker.merchant_outbox.store(TerminalDelivery(task_id=task_id, skill_id='douyin.merchant_products',
                result_delivery='operations', status='success', result={'data': {'items': []}}))
            assert not await worker._deliver_pending_terminals()
            assert worker.result_outbox.pending() == []  # 0.5.18 reads only this directory on rollback.
            assert [item.task_id for item in worker.merchant_outbox.pending()] == [task_id]
            online = True
            restarted = Worker(settings, api, executor=None)
            assert await restarted._deliver_pending_terminals()
            assert restarted.merchant_outbox.pending() == []
    asyncio.run(scenario())
    assert seen.count(f'/internal/worker/v1/store-product-results/{task_id}') == 2
    assert f'/api/v1/worker/tasks/{task_id}/selection-delivered' in seen


def test_operations_disconnect_keeps_result_and_does_not_block_product_delivery(tmp_path):
    selection_id, product_id, device_id = UUID(int=1), UUID(int=2), uuid4()
    settings = WorkerSettings(server_url='https://central.test', device_id=device_id,
                              device_token='synthetic-device-token', runtime_root=tmp_path)
    seen = []
    online = False

    def central(request):
        if request.method == 'GET':
            return httpx.Response(200, json={'task_id': str(selection_id), 'device_id': str(device_id),
                                            'origin': 'https://operations.test'})
        seen.append(request.url.path)
        return httpx.Response(200, json={})

    def operations(request):
        assert request.headers['x-device-id'] == str(device_id)
        assert request.headers['authorization'] == 'Bearer synthetic-device-token'
        seen.append('operations')
        if not online:
            return httpx.Response(503)
        body = json.loads(request.content)
        assert body['result']['data']['product_id'] == '123'
        return httpx.Response(200, json={'task_id': str(selection_id), 'accepted': True,
                                         'payload_sha256': hashlib.sha256(request.content).hexdigest()})

    def product(request):
        seen.append('product')
        return httpx.Response(200, json={'task_id': str(product_id), 'accepted': True})

    async def scenario():
        nonlocal online
        async with httpx.AsyncClient(base_url='https://central.test', transport=httpx.MockTransport(central)) as c, \
                   httpx.AsyncClient(transport=httpx.MockTransport(operations)) as o, \
                   httpx.AsyncClient(base_url='https://product.test', transport=httpx.MockTransport(product)) as p:
            api = WorkerApiClient(settings, client=c, product_client=p, operations_client=o)
            worker = Worker(settings, api, executor=None)
            worker.result_outbox.store(TerminalDelivery(task_id=selection_id, skill_id='douyin.compass_selection',
                result_delivery='operations', status='success', result={'data': {'product_id': '123'}}))
            worker.result_outbox.store(TerminalDelivery(task_id=product_id, skill_id='douyin.category_schema',
                result_delivery='product', status='success', result={'items': []}))
            assert not await worker._deliver_pending_terminals()
            assert [item.task_id for item in worker.result_outbox.pending()] == [selection_id]
            assert 'product' in seen
            assert f'/api/v1/worker/tasks/{selection_id}/selection-delivery-pending' in seen
            online = True
            restarted = Worker(settings, api, executor=None)
            assert await restarted._deliver_pending_terminals()
            assert restarted.result_outbox.pending() == []
    asyncio.run(scenario())
    assert seen.count('operations') == 2
    assert f'/api/v1/worker/tasks/{selection_id}/selection-delivered' in seen


def test_invalid_server_destination_never_receives_worker_credentials(tmp_path):
    task_id, device_id = uuid4(), uuid4()
    settings = WorkerSettings(server_url='https://central.test', device_id=device_id,
                              device_token='synthetic-device-token', runtime_root=tmp_path)
    calls = []

    async def scenario():
        async with httpx.AsyncClient(base_url='https://central.test', transport=httpx.MockTransport(lambda _r:
            httpx.Response(200, json={'task_id': str(task_id), 'device_id': str(device_id),
                                     'origin': 'http://untrusted.test'}))) as c, \
                   httpx.AsyncClient(transport=httpx.MockTransport(lambda request: calls.append(request))) as o:
            api = WorkerApiClient(settings, client=c, operations_client=o)
            worker = Worker(settings, api, executor=None)
            worker.result_outbox.store(TerminalDelivery(task_id=task_id, skill_id='douyin.compass_selection',
                result_delivery='operations', status='success', result={'data': {}}))
            assert not await worker._deliver_pending_terminals()
            assert len(worker.result_outbox.pending()) == 1
    asyncio.run(scenario())
    assert calls == []


def test_operations_outage_still_allows_product_prechecks_to_be_claimed(tmp_path):
    settings = WorkerSettings(server_url='https://central.test', device_id=uuid4(),
                              device_token='synthetic-device-token', runtime_root=tmp_path)
    selection_id, precheck_id = uuid4(), uuid4()
    seen = []
    stop = asyncio.Event()

    class Client:
        async def claim(self):
            await asyncio.sleep(0)
            seen.append('precheck')
            return WorkerTask(task_id=precheck_id, skill_id='douyin.category_schema', input={},
                              lease_until=datetime.now(UTC) + timedelta(seconds=60))
        async def close(self):
            pass

    async def scenario():
        worker = Worker(settings, Client(), executor=SimpleNamespace(can_claim=lambda: True))
        worker.result_outbox.store(TerminalDelivery(task_id=selection_id, skill_id='douyin.compass_selection',
            result_delivery='operations', status='success', result={'data': {}}))
        async def unavailable():
            return False
        async def heartbeat(event):
            await event.wait()
        async def execute(task):
            assert task.task_id == precheck_id
            stop.set()
        worker._deliver_pending_terminals = unavailable
        worker._heartbeat_supervisor = heartbeat
        worker._execute_claimed_task = execute
        await asyncio.wait_for(worker.run(stop), timeout=2)
    asyncio.run(scenario())
    assert seen and set(seen) == {'precheck'}


def test_unroutable_selection_result_is_retained_without_blocking_new_selection(tmp_path):
    settings = WorkerSettings(server_url='https://central.test', device_id=uuid4(),
                              device_token='synthetic', runtime_root=tmp_path)
    old_id, queued_id = uuid4(), uuid4()
    stop = asyncio.Event()

    class Client:
        async def claim(self):
            return WorkerTask(task_id=queued_id, skill_id='douyin.compass_selection',
                input={'operation':'categories'}, lease_until=datetime.now(UTC) + timedelta(seconds=60))
        async def close(self): pass

    async def scenario():
        worker = Worker(settings, Client(), executor=SimpleNamespace(can_claim=lambda: True))
        worker.result_outbox.store(TerminalDelivery(task_id=old_id, skill_id='douyin.compass_selection',
            result_delivery='operations', status='success', result={'data': {}}))
        attempts = []
        async def unavailable():
            attempts.append(True)
            return False
        async def heartbeat(event): await event.wait()
        async def execute(task):
            assert task.task_id == queued_id
            stop.set()
        worker._deliver_pending_terminals = unavailable
        worker._heartbeat_supervisor = heartbeat
        worker._execute_claimed_task = execute
        await asyncio.wait_for(worker.run(stop), timeout=2)
        assert attempts and [item.task_id for item in worker.result_outbox.pending()] == [old_id]
    asyncio.run(scenario())


def test_old_delivery_retries_while_new_selection_finishes(tmp_path):
    old_id, new_id, device_id = UUID(int=1), UUID(int=2), uuid4()
    settings = WorkerSettings(server_url='https://central.test', device_id=device_id,
        device_token='synthetic', runtime_root=tmp_path, poll_interval_seconds=0.2)
    stop, recovered, delivered = asyncio.Event(), False, []

    def central(request):
        task_id = request.url.path.split('/')[5]
        if request.method == 'GET':
            return httpx.Response(200, json={'task_id':task_id,'device_id':str(device_id),
                                              'origin':'https://operations.test'})
        return httpx.Response(200, json={})

    def operations(request):
        task_id = request.url.path.rsplit('/',1)[-1]
        if task_id == str(old_id) and not recovered:
            return httpx.Response(503)
        delivered.append(task_id)
        return httpx.Response(200, json={'task_id':task_id,'accepted':True,
            'payload_sha256':hashlib.sha256(request.content).hexdigest()})

    async def scenario():
        nonlocal recovered
        async with httpx.AsyncClient(base_url='https://central.test',transport=httpx.MockTransport(central)) as c, \
                   httpx.AsyncClient(transport=httpx.MockTransport(operations)) as o:
            api=WorkerApiClient(settings,client=c,operations_client=o)
            class Client:
                def __getattr__(self,name): return getattr(api,name)
                async def claim(self):
                    return WorkerTask(task_id=new_id,skill_id='douyin.compass_selection',
                        input={'operation':'categories'},lease_until=datetime.now(UTC)+timedelta(seconds=60))
                async def close(self): pass
            worker=Worker(settings,Client(),executor=SimpleNamespace(can_claim=lambda:True))
            def store(task_id):
                worker.result_outbox.store(TerminalDelivery(task_id=task_id,skill_id='douyin.compass_selection',
                    result_delivery='operations',status='success',result={'data':{}}))
            store(old_id)
            async def heartbeat(event): await event.wait()
            async def execute(task):
                nonlocal recovered
                assert task.task_id == new_id
                store(new_id)
                assert not await worker._deliver_pending_terminals()
                assert [item.task_id for item in worker.result_outbox.pending()] == [old_id]
                recovered=True
                assert await worker._deliver_pending_terminals()
                assert not worker.result_outbox.pending()
                stop.set()
            worker._heartbeat_supervisor=heartbeat
            worker._execute_claimed_task=execute
            await asyncio.wait_for(worker.run(stop),timeout=2)
    asyncio.run(scenario())
    assert delivered == [str(new_id),str(old_id)]


def test_pending_operations_result_does_not_block_idle_worker_update(tmp_path):
    settings = WorkerSettings(server_url='https://central.test', device_id=uuid4(),
                              device_token='synthetic', runtime_root=tmp_path)
    old_id = uuid4()
    stop = asyncio.Event()
    async def scenario():
        worker = Worker(settings, SimpleNamespace(close=lambda: asyncio.sleep(0)),
                        executor=SimpleNamespace(can_claim=lambda: True))
        worker.result_outbox.store(TerminalDelivery(task_id=old_id, skill_id='douyin.compass_selection',
            result_delivery='operations', status='success', result={'data': {}}))
        async def unavailable(): return False
        async def heartbeat(event): await event.wait()
        async def update():
            assert [item.task_id for item in worker.result_outbox.pending()] == [old_id]
            return True
        worker._deliver_pending_terminals = unavailable
        worker._heartbeat_supervisor = heartbeat
        worker._update_base_if_idle = update
        await asyncio.wait_for(worker.run(stop), timeout=2)
        assert [item.task_id for item in worker.result_outbox.pending()] == [old_id]
    asyncio.run(scenario())


def test_non_operations_result_still_blocks_new_claims(tmp_path):
    settings = WorkerSettings(server_url='https://central.test', device_id=uuid4(),
        device_token='synthetic', runtime_root=tmp_path, poll_interval_seconds=0.2)
    pending_id, stop = uuid4(), asyncio.Event()
    claimed = []
    class Client:
        async def claim(self): claimed.append(True)
        async def close(self): pass
    async def scenario():
        worker = Worker(settings, Client(), executor=SimpleNamespace(can_claim=lambda: True))
        worker.result_outbox.store(TerminalDelivery(task_id=pending_id, skill_id='douyin.category_schema',
            result_delivery='product', status='success', result={'items':[]}))
        async def unavailable(): return False
        async def heartbeat(event): await event.wait()
        worker._deliver_pending_terminals = unavailable
        worker._heartbeat_supervisor = heartbeat
        async def finish():
            await asyncio.sleep(0.35)
            stop.set()
        trigger = asyncio.create_task(finish())
        await asyncio.wait_for(worker.run(stop), timeout=2)
        await trigger
        assert [item.task_id for item in worker.result_outbox.pending()] == [pending_id]
    asyncio.run(scenario())
    assert not claimed
