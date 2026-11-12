import asyncio
import hashlib
import json
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from app.client import WorkerApiClient
from app.config import WorkerSettings
from app.result_outbox import TerminalDelivery
from app.worker import Worker


def test_direct_delivery_survives_disconnect_without_repeating_platform_work(tmp_path):
    task_id, device_id = uuid4(), uuid4()
    token = "ccw_synthetic_worker_token"
    payload = {"kind": "douyin.category_schema", "category_id": "123", "items": [{"id": "1"}]}
    settings = WorkerSettings(server_url="https://central.test", device_id=device_id, device_token=token,
                              product_precheck_origin="https://product.test", runtime_root=tmp_path)
    events = []
    attempts = 0

    def product(request):
        nonlocal attempts
        attempts += 1
        events.append(("product", request))
        assert request.headers["authorization"] == "Bearer " + token
        assert request.headers["x-device-id"] == str(device_id)
        if attempts == 1:
            return httpx.Response(503)
        assert json.loads(request.content)["result"] == payload
        return httpx.Response(200, json={"task_id": str(task_id), "accepted": True})

    def central(request):
        events.append(("central", request))
        assert request.url.path == f"/api/v1/worker/tasks/{task_id}/precheck-delivered"
        body = json.loads(request.content)
        assert set(body) == {"status", "payload_sha256", "error_code"}
        assert body["status"] == "success" and body["error_code"] is None
        assert body["payload_sha256"] == hashlib.sha256(events[-2][1].content).hexdigest()
        return httpx.Response(200, json={"task_id": str(task_id), "status": "success"})

    async def scenario():
        async with httpx.AsyncClient(base_url="https://central.test", transport=httpx.MockTransport(central)) as c, \
                   httpx.AsyncClient(base_url="https://product.test", transport=httpx.MockTransport(product)) as p:
            api = WorkerApiClient(settings, client=c, product_client=p)
            worker = Worker(settings, api, executor=None)
            worker.result_outbox.store(TerminalDelivery(task_id=task_id, skill_id="douyin.category_schema",
                                         result_delivery="product", status="success", result=payload))
            assert json.loads((worker.result_outbox.root / f"{task_id}.json").read_text(encoding="utf-8"))["result_delivery"] == "product"
            assert not await worker._deliver_pending_terminals()
            assert len(worker.result_outbox.pending()) == 1
            # A restarted Worker replays only the saved result, not the platform operation.
            restarted = Worker(settings, api, executor=None)
            assert await restarted._deliver_pending_terminals()
            assert restarted.result_outbox.pending() == []

    asyncio.run(scenario())
    assert [name for name, _ in events] == ["product", "product", "central"]


def test_product_result_never_defaults_to_production_from_integration():
    settings = WorkerSettings(server_url="https://integration.test", device_id=uuid4(), device_token="synthetic")
    api = WorkerApiClient(settings)
    assert api.product_client is None
    asyncio.run(api.close())
    with pytest.raises(ValidationError):
        WorkerSettings(server_url="https://central.test", device_id=uuid4(), device_token="synthetic",
                       product_precheck_origin="http://product.test")


def test_lost_central_ack_replays_identical_product_result(tmp_path):
    task_id, device_id = uuid4(), uuid4()
    settings = WorkerSettings(server_url="https://central.test", device_id=device_id, device_token="synthetic",
                              product_precheck_origin="https://product.test", runtime_root=tmp_path)
    bodies = []
    acknowledgements = []

    def product(request):
        bodies.append(request.content)
        return httpx.Response(200, json={"task_id": str(task_id), "accepted": True})

    def central(request):
        acknowledgements.append(json.loads(request.content))
        return httpx.Response(503 if len(acknowledgements) == 1 else 200, json={})

    async def scenario():
        async with httpx.AsyncClient(base_url="https://central.test", transport=httpx.MockTransport(central)) as c, \
                   httpx.AsyncClient(base_url="https://product.test", transport=httpx.MockTransport(product)) as p:
            api = WorkerApiClient(settings, client=c, product_client=p)
            worker = Worker(settings, api, executor=None)
            worker.result_outbox.store(TerminalDelivery(task_id=task_id, skill_id="douyin.category_schema",
                                         result_delivery="product", status="success", result={"items": []}))
            assert not await worker._deliver_pending_terminals()
            assert len(worker.result_outbox.pending()) == 1
            assert await worker._deliver_pending_terminals()
            assert worker.result_outbox.pending() == []

    asyncio.run(scenario())
    assert len(bodies) == 2 and bodies[0] == bodies[1]
    assert len(acknowledgements) == 2 and acknowledgements[0] == acknowledgements[1]


def test_unsafe_failure_code_is_not_sent_to_central():
    task_id = uuid4()
    settings = WorkerSettings(server_url="https://central.test", device_id=uuid4(), device_token="synthetic")
    received = []

    def central(request):
        received.append(json.loads(request.content))
        return httpx.Response(200, json={})

    async def scenario():
        async with httpx.AsyncClient(base_url="https://central.test", transport=httpx.MockTransport(central)) as c:
            api = WorkerApiClient(settings, client=c)
            await api.acknowledge_product_precheck(task_id, status="failed", payload_sha256="a" * 64,
                                                    error_code="unsafe details")
    asyncio.run(scenario())
    assert received[0]["error_code"] == "PRECHECK_FAILED"
