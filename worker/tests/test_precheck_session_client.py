import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from app.client import WorkerApiClient, WorkerApiError
from app.config import WorkerSettings


def test_session_client_uses_task_shop_route_and_masks_cookie():
    async def run():
        device_id, task_id, shop_id = uuid4(), uuid4(), uuid4()
        def handler(request):
            assert request.method == "POST"
            assert request.url.path == f"/api/v1/worker/tasks/{task_id}/shop-sessions/{shop_id}"
            return httpx.Response(200, json={
                "shop_id": str(shop_id), "platform": "douyin", "session_version": 3,
                "task_lease_until": (datetime.now(UTC) + timedelta(minutes=1)).isoformat(),
                "cookies": [{"name": "sessionid", "value": "synthetic-cookie"}],
            })
        settings = WorkerSettings(server_url="https://central.example.test", device_id=device_id,
                                  device_token=SecretStr("synthetic-token"))
        async with httpx.AsyncClient(base_url="https://central.example.test",
                                     transport=httpx.MockTransport(handler)) as http:
            result = await WorkerApiClient(settings, http).read_precheck_shop_session(task_id, shop_id)
        assert result.shop_id == shop_id and result.session_version == 3
        assert result.cookies[0].value.get_secret_value() == "synthetic-cookie"
        assert "synthetic-cookie" not in repr(result)
        assert "synthetic-cookie" not in result.model_dump_json()
    asyncio.run(run())


def test_session_client_refuses_http_before_sending_any_request():
    async def run():
        def handler(request):
            raise AssertionError("insecure request must not be sent")
        settings = WorkerSettings(server_url="http://central.example.test", device_id=uuid4(),
                                  device_token=SecretStr("synthetic-token"))
        async with httpx.AsyncClient(base_url="http://central.example.test",
                                     transport=httpx.MockTransport(handler)) as http:
            with pytest.raises(WorkerApiError, match="HTTPS_REQUIRED"):
                await WorkerApiClient(settings, http).read_precheck_shop_session(uuid4(), uuid4())
    asyncio.run(run())


def test_session_client_rejects_wrong_shop_and_does_not_reflect_error_details():
    async def run():
        expected, actual = uuid4(), uuid4()
        replies = [
            httpx.Response(200, json={
                "shop_id": str(actual), "platform": "douyin", "session_version": 1,
                "task_lease_until": (datetime.now(UTC) + timedelta(minutes=1)).isoformat(),
                "cookies": [{"name": "sessionid", "value": "synthetic-cookie"}],
            }),
            httpx.Response(500, json={"code": "SECRET", "message": "synthetic-cookie"}),
        ]
        settings = WorkerSettings(server_url="https://central.example.test", device_id=uuid4(),
                                  device_token=SecretStr("synthetic-token"))
        async with httpx.AsyncClient(base_url="https://central.example.test",
                transport=httpx.MockTransport(lambda request: replies.pop(0))) as http:
            client = WorkerApiClient(settings, http)
            for _ in range(2):
                with pytest.raises(WorkerApiError) as error:
                    await client.read_precheck_shop_session(uuid4(), expected)
                assert "synthetic-cookie" not in str(error.value)
    asyncio.run(run())


def test_session_client_does_not_follow_https_downgrade():
    async def run():
        requests = []
        def handler(request):
            requests.append(request.url.scheme)
            return httpx.Response(302, headers={"Location": "http://attacker.invalid/"})
        settings = WorkerSettings(server_url="https://central.example.test", device_id=uuid4(),
                                  device_token=SecretStr("synthetic-token"))
        async with httpx.AsyncClient(base_url="https://central.example.test",
                transport=httpx.MockTransport(handler), follow_redirects=True) as http:
            with pytest.raises(WorkerApiError, match="UNAVAILABLE"):
                await WorkerApiClient(settings, http).read_precheck_shop_session(uuid4(), uuid4())
        assert requests == ["https"]
    asyncio.run(run())


def test_session_client_rejects_session_received_after_lease_expires():
    async def run():
        shop_id = uuid4()
        def handler(request):
            return httpx.Response(200, json={
                "shop_id": str(shop_id), "platform": "douyin", "session_version": 1,
                "task_lease_until": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
                "cookies": [{"name": "sessionid", "value": "synthetic-expired-cookie"}],
            })
        settings = WorkerSettings(server_url="https://central.example.test", device_id=uuid4(),
                                  device_token=SecretStr("synthetic-token"))
        async with httpx.AsyncClient(base_url="https://central.example.test",
                transport=httpx.MockTransport(handler)) as http:
            with pytest.raises(WorkerApiError, match="LEASE_EXPIRED") as error:
                await WorkerApiClient(settings, http).read_precheck_shop_session(uuid4(), shop_id)
            assert "synthetic-expired-cookie" not in str(error.value)
    asyncio.run(run())


def test_session_client_exposes_retryable_authorization_contention_without_server_text():
    async def run():
        requests = []
        def handler(request):
            requests.append(request)
            return httpx.Response(409, json={
                "code": "PRECHECK_SESSION_AUTHORIZATION_BUSY",
                "message": "synthetic-sensitive-server-text",
            })
        settings = WorkerSettings(server_url="https://central.example.test", device_id=uuid4(),
                                  device_token=SecretStr("synthetic-token"))
        async with httpx.AsyncClient(base_url="https://central.example.test",
                transport=httpx.MockTransport(handler)) as http:
            with pytest.raises(WorkerApiError) as error:
                await WorkerApiClient(settings, http).read_precheck_shop_session(uuid4(), uuid4())
        assert error.value.code == "PRECHECK_SESSION_AUTHORIZATION_BUSY"
        assert "synthetic-sensitive-server-text" not in str(error.value)
        assert len(requests) == 1
    asyncio.run(run())
