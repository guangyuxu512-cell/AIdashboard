import asyncio
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

import httpx
import pytest

from app.client import WorkerApiError
from app.config import WorkerSettings
from app.contracts import ExecutionResult, ExecutionStatus, WorkerTask
from app.result_outbox import OutboxError, ResultOutbox, TerminalDelivery
from app.worker import Worker


def test_terminal_survives_restart_and_ack_is_required(tmp_path):
    task_id = uuid4()
    item = TerminalDelivery(
        task_id=task_id, skill_id="douyin.category_schema", status="success",
        result={"category_id": "123", "items": [{"id": "1", "label": "颜色"}]},
    )
    ResultOutbox(tmp_path).store(item)
    # The legacy Worker rejects unknown keys when reading an outbox entry.
    assert "result_delivery" not in json.loads((tmp_path / f"{task_id}.json").read_text(encoding="utf-8"))

    reopened = ResultOutbox(tmp_path)
    assert reopened.pending() == [item]
    reopened.store(item)  # Recording the same result is idempotent.
    assert reopened.pending() == [item]
    reopened.acknowledge(item)
    assert reopened.pending() == []


def test_conflicting_result_cannot_overwrite_the_first(tmp_path):
    task_id = uuid4()
    first = TerminalDelivery(task_id=task_id, skill_id="demo.test",
                             status="success", result={"count": 1})
    second = TerminalDelivery(task_id=task_id, skill_id="demo.test",
                              status="success", result={"count": 2})
    outbox = ResultOutbox(tmp_path)
    outbox.store(first)
    with pytest.raises(OutboxError, match="conflicts"):
        outbox.store(second)
    with pytest.raises(OutboxError, match="changed"):
        outbox.acknowledge(second)
    assert outbox.pending() == [first]


def test_secret_fields_cannot_be_persisted(tmp_path):
    with pytest.raises(ValueError, match="sensitive"):
        TerminalDelivery(task_id=uuid4(), skill_id="demo.test", status="success",
                         result={"nested": [{"cookies": [{"value": "test-only"}]}]})
    assert list(tmp_path.iterdir()) == []


def test_corrupt_terminal_is_preserved_and_blocks_silent_loss(tmp_path):
    path = tmp_path / f"{uuid4()}.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(OutboxError, match="unreadable"):
        ResultOutbox(tmp_path).pending()
    assert path.exists()


def test_worker_restarts_and_only_resends_stored_result(tmp_path):
    class Executor:
        calls = 0

        async def execute(self, task):
            self.calls += 1
            return ExecutionResult(status=ExecutionStatus.SUCCESS,
                                   result={"category": "test", "cookie": "test-secret"})

    class Client:
        calls = 0
        received = []

        async def heartbeat(self, **_):
            pass

        async def complete(self, task_id, result):
            self.calls += 1
            if self.calls == 1:
                # Model a result committed on the server whose response was lost.
                self.received.append((task_id, result))
                raise httpx.ConnectError("connection lost")
            assert self.received == [(task_id, result)]

    settings = WorkerSettings(server_url="https://example.test", device_id=uuid4(),
                              device_token="test-token", runtime_root=tmp_path,
                              lease_renew_interval_seconds=60)
    task = WorkerTask(task_id=uuid4(), skill_id="system.echo", input={},
                      lease_until=datetime.now(UTC) + timedelta(minutes=1))
    client, executor = Client(), Executor()
    first = Worker(settings, client, executor)
    asyncio.run(first._execute_task(task))
    pending = first.result_outbox.pending()
    assert len(pending) == 1
    assert pending[0].result == {"category": "test", "cookie": "[REDACTED]"}
    assert "test-secret" not in next((tmp_path / "result-outbox").glob("*.json")).read_text()

    restarted = Worker(settings, client, executor)
    assert asyncio.run(restarted._deliver_pending_terminals()) is True
    assert restarted.result_outbox.pending() == []
    assert executor.calls == 1
    assert client.calls == 2


def test_result_is_durable_before_terminal_event_flush(tmp_path):
    class Executor:
        calls = 0

        async def execute(self, task):
            self.calls += 1
            return ExecutionResult(status=ExecutionStatus.SUCCESS, result={"items": ["ok"]})

    class Client:
        calls = 0

        async def heartbeat(self, **_):
            pass

        async def complete(self, task_id, result):
            self.calls += 1
            assert result == {"items": ["ok"]}

    class InterruptedReporter:
        async def flush_task(self, task_id):
            # Simulate a process being interrupted before the network flush.
            raise asyncio.CancelledError()

    settings = WorkerSettings(server_url="https://example.test", device_id=uuid4(),
                              device_token="test-token", runtime_root=tmp_path,
                              lease_renew_interval_seconds=60)
    task = WorkerTask(task_id=uuid4(), skill_id="system.echo", input={},
                      lease_until=datetime.now(UTC) + timedelta(minutes=1))
    client, executor = Client(), Executor()
    first = Worker(settings, client, executor, event_reporter=InterruptedReporter())
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(first._execute_task(task))
    assert len(first.result_outbox.pending()) == 1
    assert client.calls == 0
    restarted = Worker(settings, client, executor)
    assert asyncio.run(restarted._deliver_pending_terminals()) is True
    assert client.calls == 1
    assert executor.calls == 1


def test_explicit_conflict_is_preserved_without_automatic_retry(tmp_path):
    class Client:
        calls = 0

        async def complete(self, task_id, result):
            self.calls += 1
            raise WorkerApiError("TASK_STATE_CONFLICT", "changed", 409)

    class Executor:
        pass

    settings = WorkerSettings(server_url="https://example.test", device_id=uuid4(),
                              device_token="test-token", runtime_root=tmp_path)
    client = Client()
    worker = Worker(settings, client, Executor())
    item = TerminalDelivery(task_id=uuid4(), skill_id="system.echo",
                            status="success", result={"ok": True})
    worker.result_outbox.store(item)
    assert asyncio.run(worker._deliver_pending_terminals()) is True
    assert asyncio.run(worker._deliver_pending_terminals()) is True
    assert client.calls == 1
    assert worker.result_outbox.pending() == []
    assert (tmp_path / "result-outbox" / "rejected" / f"{item.task_id}.json").exists()


def test_result_survives_real_process_termination_after_delivery_failure(tmp_path):
    """Kill an isolated Worker after a simulated connection loss, then restart it."""
    program = tmp_path / "isolated_worker.py"
    program.write_text('''\
import asyncio
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sys
from uuid import UUID, uuid4
import httpx
from app.config import WorkerSettings
from app.contracts import ExecutionResult, ExecutionStatus, WorkerTask
from app.worker import Worker

mode, root, task_id = sys.argv[1], Path(sys.argv[2]), UUID(sys.argv[3])
class Executor:
    async def execute(self, task):
        with (root / "executions.txt").open("a", encoding="utf-8") as stream:
            stream.write("executed\\n")
        return ExecutionResult(status=ExecutionStatus.SUCCESS, result={"items": ["synthetic"]})
class Client:
    async def heartbeat(self, **kwargs):
        pass
    async def complete(self, task_id, result):
        if mode == "first":
            raise httpx.ConnectError("simulated loss")
        (root / "receipt.json").write_text(json.dumps(result), encoding="utf-8")
settings = WorkerSettings(server_url="https://example.test", device_id=uuid4(),
    device_token="synthetic-token", runtime_root=root / "runtime", lease_renew_interval_seconds=60)
worker = Worker(settings, Client(), Executor())
async def run():
    if mode == "first":
        task = WorkerTask(task_id=task_id, skill_id="system.echo", input={},
            lease_until=datetime.now(UTC) + timedelta(minutes=1))
        await worker._execute_task(task)
        (root / "ready").write_text("ready", encoding="ascii")
        await asyncio.sleep(60)
    else:
        assert await worker._deliver_pending_terminals()
asyncio.run(run())
''', encoding="utf-8")
    task_id = str(uuid4())
    worker_root = Path(__file__).resolve().parents[1]
    command = [sys.executable, str(program), "first", str(tmp_path), task_id]
    process = subprocess.Popen(command, cwd=worker_root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        deadline = time.monotonic() + 15
        while not (tmp_path / "ready").exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert (tmp_path / "ready").exists(), "isolated Worker did not persist its result"
        assert (tmp_path / "runtime/result-outbox" / f"{task_id}.json").is_file()
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=10)

    restarted = subprocess.run([sys.executable, str(program), "second", str(tmp_path), task_id],
                               cwd=worker_root, capture_output=True, timeout=15,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    assert restarted.returncode == 0
    assert json.loads((tmp_path / "receipt.json").read_text(encoding="utf-8")) == {"items": ["synthetic"]}
    assert (tmp_path / "executions.txt").read_text(encoding="utf-8").splitlines() == ["executed"]
    assert not (tmp_path / "runtime/result-outbox" / f"{task_id}.json").exists()
