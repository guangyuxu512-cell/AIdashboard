import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.contracts import RuntimeEventType, WorkerTask
from app.runtime_events import (
    BackendEventReporter,
    LocalRuntimeState,
    RuntimeEventBuffer,
    RuntimeEventBus,
)


class FlakyEventClient:
    def __init__(self) -> None:
        self.calls = 0
        self.uploaded: list[int] = []

    async def report_task_events(self, task_id: object, events: list[object]) -> None:
        del task_id
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("backend unavailable")
        self.uploaded.extend(event.seq for event in events)  # type: ignore[attr-defined]


def test_event_bus_sequences_each_task_and_redacts_sensitive_values() -> None:
    bus = RuntimeEventBus()
    received = []
    bus.subscribe(received.append)
    task_id = uuid4()

    first = bus.emit(
        task_id,
        RuntimeEventType.LOG,
        "token=plain-secret",
        metadata={"cookie": "plain-cookie", "app_name": "Safe"},
    )
    second = bus.emit(task_id, RuntimeEventType.PROGRESS, "next")

    assert [event.seq for event in received] == [1, 2]
    assert "plain-secret" not in first.message
    assert first.metadata == {"cookie": "[REDACTED]", "app_name": "Safe"}
    assert second.seq == 2


def test_event_buffer_retries_without_duplicate_or_task_failure() -> None:
    async def scenario() -> None:
        bus = RuntimeEventBus()
        buffer = RuntimeEventBuffer(100)
        bus.subscribe(buffer.append)
        task_id = uuid4()
        bus.emit(task_id, RuntimeEventType.STATUS, "one")
        bus.emit(task_id, RuntimeEventType.LOG, "two")
        client = FlakyEventClient()
        reporter = BackendEventReporter(  # type: ignore[arg-type]
            client,
            buffer,
            flush_interval_seconds=0.1,
            batch_size=20,
            retry_count=3,
        )

        assert await reporter.flush_once() is False
        assert len(buffer) == 2
        assert await reporter.flush_task(task_id) is True
        assert client.uploaded == [1, 2]
        assert len(buffer) == 0

    asyncio.run(scenario())


def test_runtime_snapshot_is_atomic_bounded_and_contains_no_secrets(
    tmp_path: Path,
) -> None:
    path = tmp_path / "runtime-status.json"
    device_id = uuid4()
    task_id = uuid4()
    state = LocalRuntimeState(path=path, device_id=device_id, recent_limit=2)
    bus = RuntimeEventBus()
    bus.subscribe(state.consume)
    state.begin_task(
        WorkerTask(
            task_id=task_id,
            skill_id="system.echo",
            input={"token": "must-not-be-snapshotted"},
            lease_until=datetime.now(UTC),
        ),
        skill_display_name="Echo",
    )
    for message in ("first", "second", "third"):
        bus.emit(task_id, RuntimeEventType.LOG, message)

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["device_id"] == str(device_id)
    assert payload["skill_display_name"] == "Echo"
    assert [event["message"] for event in payload["recent_events"]] == [
        "second",
        "third",
    ]
    assert "must-not-be-snapshotted" not in path.read_text(encoding="utf-8")


def test_late_provider_event_does_not_reactivate_finished_local_task(
    tmp_path: Path,
) -> None:
    path = tmp_path / "runtime-status.json"
    task_id = uuid4()
    state = LocalRuntimeState(path=path, device_id=uuid4())
    bus = RuntimeEventBus()
    bus.subscribe(state.consume)
    task = WorkerTask(
        task_id=task_id,
        skill_id="yingdao.app.run",
        input={},
        lease_until=datetime.now(UTC),
    )
    state.begin_task(task, skill_display_name="运行影刀应用")
    state.finish_task(task_id)

    bus.emit(
        task_id,
        RuntimeEventType.LOG,
        "底层影刀在Task超时后才结束",
        metadata={"provider": "yingdao", "phase": "failed"},
    )
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["current_task_id"] is None
    assert payload["phase"] is None
    assert payload["recent_events"][-1]["message"] == "底层影刀在Task超时后才结束"
