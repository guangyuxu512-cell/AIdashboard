import asyncio
from datetime import UTC, datetime, timedelta
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.contracts import ExecutionStatus, WorkerTask
from app.rpa_session_bridge import RpaBridgeError


path = Path(__file__).resolve().parents[1] / "capabilities" / "douyin_category_schema" / "capability.py"
spec = importlib.util.spec_from_file_location("douyin_capability_for_test", path)
capability = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capability)


class Host:
    device_id = uuid4()
    platform_calls = 0

    def __init__(self, code):
        self.code = code

    async def read_session(self, local_shop_id, platform_shop_id):
        return SimpleNamespace(user_agent="synthetic-agent")

    def cookie_header(self, session):
        return "session=synthetic-cookie"

    async def sign_precheck(self, task_id, cookie, user_agent):
        return {"url": "synthetic", "body": "synthetic"}

    async def post_schema(self, signed, cookie, user_agent, params):
        self.platform_calls += 1
        return 200, {"code": self.code, "data": {"model": {"category_properties": {"items": [
            {"id": "size", "label": "规格", "rules": [{"type": "max_input_num", "value": 3}],
             "ignored": "must-not-persist", "options": [{"id": 1, "name": "小"}]}
        ]}}}}


def task():
    return WorkerTask(task_id=uuid4(), skill_id="douyin.category_schema",
        input={"category_id": "1000005146", "title": "demo", "local_shop_id": "a", "platform_shop_id": "123"},
        lease_until=datetime.now(UTC) + timedelta(seconds=60))


@pytest.mark.parametrize("platform_code", [0, "0"])
def test_success_normalizes_numeric_code_and_keeps_only_safe_fields(platform_code):
    host = Host(platform_code)
    result = asyncio.run(capability.execute(host, task()))
    assert result.status is ExecutionStatus.SUCCESS
    assert result.result["platform_code"] == 0
    assert result.result["items"][0]["rules"] == [{"type": "max_input_num", "value": 3}]
    assert "ignored" not in result.result["items"][0]
    assert "synthetic-cookie" not in repr(result)
    assert host.platform_calls == 1


@pytest.mark.parametrize(("platform_code", "expected"), [(True, None), ("00", "00"), ("E_600.2-A", "E_600.2-A")])
def test_business_rejection_preserves_safe_code(platform_code, expected):
    result = asyncio.run(capability.execute(Host(platform_code), task()))
    assert result.status is ExecutionStatus.FAILED
    assert result.result["platform_code"] == expected
    assert result.result["error_stage"] == "platform"


@pytest.mark.parametrize(("message", "expected"), [
    ("登录状态已过期，请重新登录", "SHOP_SESSION_EXPIRED"),
    ("请先登录", "SHOP_SESSION_EXPIRED"),
    ("无权访问此接口", "PLATFORM_BUSINESS_REJECTED"),
    ("本次请求存在安全风险", "PLATFORM_BUSINESS_REJECTED"),
    ("网络异常，请稍后重试", "PLATFORM_BUSINESS_REJECTED"),
])
def test_only_explicit_login_failures_invalidate_a_session(message, expected):
    class RejectedHost(Host):
        async def post_schema(self, signed, cookie, user_agent, params):
            return 200, {"code": 10004, "msg": message}

    result = asyncio.run(capability.execute(RejectedHost(10004), task()))
    assert result.status is ExecutionStatus.FAILED
    assert result.error_code == expected


@pytest.mark.parametrize("http_status", [403, 500, 503])
def test_http_or_network_failure_alone_does_not_invalidate_session(http_status):
    class NetworkHost(Host):
        async def post_schema(self, signed, cookie, user_agent, params):
            raise TimeoutError()

    class ForbiddenHost(Host):
        async def post_schema(self, signed, cookie, user_agent, params):
            return http_status, {"code": 10004, "msg": "请先登录"}

    assert asyncio.run(capability.execute(NetworkHost(0), task())).error_code == "PLATFORM_REQUEST_FAILED"
    assert asyncio.run(capability.execute(ForbiddenHost(0), task())).error_code == "PLATFORM_BUSINESS_REJECTED"


def test_unauthorized_with_explicit_login_message_invalidates_session():
    class UnauthorizedHost(Host):
        async def post_schema(self, signed, cookie, user_agent, params):
            return 401, {"code": 10004, "msg": "请先登录"}

    assert asyncio.run(capability.execute(UnauthorizedHost(0), task())).error_code == "SHOP_SESSION_EXPIRED"


def test_queued_known_expired_snapshot_never_calls_platform():
    class NoRequestHost(Host):
        async def read_session(self, local_shop_id, platform_shop_id):
            raise AssertionError("known-expired session must not be read")

    queued = task()
    queued.input["skip_expired_session"] = True
    host = NoRequestHost(0)
    result = asyncio.run(capability.execute(host, queued))
    assert result.error_code == "SHOP_SESSION_EXPIRED"
    assert host.platform_calls == 0


def test_session_bridge_timeout_is_reported_without_signing_or_platform_request():
    class TimedOutHost(Host):
        async def read_session(self, local_shop_id, platform_shop_id):
            raise RpaBridgeError("RPA_BRIDGE_SESSION_TIMEOUT")

        async def sign_precheck(self, *args):
            raise AssertionError("signer must not be called")

    host = TimedOutHost(0)
    result = asyncio.run(capability.execute(host, task()))
    assert result.status is ExecutionStatus.FAILED
    assert result.result["error_stage"] == "session"
    assert result.result["safe_error_code"] == "RPA_BRIDGE_SESSION_TIMEOUT"
    assert host.platform_calls == 0
