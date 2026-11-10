import asyncio
from datetime import UTC, datetime, timedelta
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.contracts import ExecutionStatus, WorkerTask


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
