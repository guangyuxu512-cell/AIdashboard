import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.config import WorkerSettings
from app.contracts import WorkerTask
from app.runtime_events import LocalRuntimeState
from app.worker import Worker


def setup_worker(tmp_path):
    state = LocalRuntimeState(path=tmp_path / "runtime-status.json", device_id=uuid4())
    settings = WorkerSettings(server_url="https://example.invalid", device_id=uuid4(),
                              device_token="fixture", runtime_root=tmp_path / "runtime")
    worker = Worker(settings, object(), object(), local_runtime_state=state)
    task = WorkerTask(task_id=uuid4(), skill_id="system.echo", input={},
                      lease_until=datetime.now(UTC) + timedelta(minutes=2))
    async def heartbeat():
        return None
    worker._send_immediate_heartbeat = heartbeat
    return worker, state, task


def test_durable_activity_write_failure_prevents_business_execution(tmp_path, monkeypatch):
    worker, state, task = setup_worker(tmp_path)
    attempted = []
    async def execute(_):
        attempted.append(True)
    worker._execute_with_selection_interval = execute
    def fail_sync(_):
        raise OSError("test fsync failure")
    monkeypatch.setattr("app.runtime_events.os.fsync", fail_sync)
    with pytest.raises(RuntimeError, match="persist task activity"):
        asyncio.run(worker._execute_task(task))
    assert attempted == []
    assert state.ready_for_task() is False
    monkeypatch.undo()
    assert state.ready_for_task() is True
    payload = json.loads(state.path.read_text("utf8"))
    assert payload["active_task_count"] == 0


def test_execution_without_durable_result_remains_uncertain(tmp_path):
    worker, state, task = setup_worker(tmp_path)
    async def execute(_):
        raise OSError("result unavailable")
    async def renew(_):
        await asyncio.sleep(30)
    worker._execute_with_selection_interval = execute
    worker._renew_lease = renew
    with pytest.raises(OSError, match="result unavailable"):
        asyncio.run(worker._execute_task(task))
    payload = json.loads(state.path.read_text("utf8"))
    assert payload["active_task_count"] == 0
    assert payload["watchdog_uncertain"] is True


def test_worker_does_not_claim_if_initial_checkpoint_is_unwritable(tmp_path):
    parent = tmp_path / "unwritable"
    parent.write_text("fixture", encoding="utf8")
    state = LocalRuntimeState(path=parent / "runtime-status.json", device_id=uuid4())
    assert state.ready_for_task() is False
    parent.rename(tmp_path / "previous-file")
    parent.mkdir()
    assert state.ready_for_task() is True
