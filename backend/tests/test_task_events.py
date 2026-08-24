from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.modules.tasks.enums import TaskStatus
from app.modules.tasks.exceptions import TaskEventForbiddenError
from app.modules.tasks.models import Task, TaskEvent
from app.modules.tasks.repository import TaskEventPage
from app.modules.tasks.schemas import TaskEventBatchWrite
from app.modules.tasks.service import TaskService
from app.modules.workers.service import WorkerPrincipal
from tests.support import FakeSession


class FakeTaskEventRepository:
    def __init__(self, task: Task) -> None:
        self.task = task
        self.events: dict[tuple[UUID, int], TaskEvent] = {}

    def get(self, task_id: UUID) -> Task | None:
        return self.task if task_id == self.task.task_id else None

    def insert_events(
        self,
        *,
        task_id: UUID,
        events: list[dict[str, object]],
    ) -> int:
        accepted = 0
        for payload in events:
            key = (task_id, int(payload["seq"]))
            if key in self.events:
                continue
            event = TaskEvent(
                event_id=uuid4(),
                task_id=task_id,
                **payload,
            )
            event.created_at = datetime.now(UTC)
            self.events[key] = event
            accepted += 1
        return accepted

    def list_events(
        self,
        *,
        task_id: UUID,
        after_seq: int | None,
        before_seq: int | None,
        limit: int,
    ) -> TaskEventPage:
        events = [
            event
            for (_, seq), event in sorted(self.events.items())
            if event.task_id == task_id
            and (after_seq is None or seq > after_seq)
            and (before_seq is None or seq < before_seq)
        ]
        if after_seq is not None:
            return TaskEventPage(items=events[:limit], has_more_before=False)
        return TaskEventPage(
            items=events[-limit:],
            has_more_before=len(events) > limit,
        )

    def get_active_for_device(self, device_id: UUID) -> Task | None:
        return self.task if self.task.target_device_id == device_id else None

    def get_latest_event(self, task_id: UUID) -> TaskEvent | None:
        page = self.list_events(
            task_id=task_id,
            after_seq=0,
            before_seq=None,
            limit=100,
        )
        return page.items[-1] if page.items else None


def make_service() -> tuple[TaskService, FakeTaskEventRepository, UUID, UUID]:
    device_id = uuid4()
    task_id = uuid4()
    now = datetime.now(UTC)
    task = Task(
        task_id=task_id,
        target_device_id=device_id,
        skill_id="yingdao.test",
        execution_display_name="影刀无副作用测试",
        status=TaskStatus.RUNNING.value,
        input_json={},
        lease_until=now + timedelta(minutes=1),
        started_at=now,
    )
    task.created_at = now
    task.updated_at = now
    repository = FakeTaskEventRepository(task)
    service = TaskService(
        FakeSession(),  # type: ignore[arg-type]
        repository,  # type: ignore[arg-type]
    )
    return service, repository, device_id, task_id


def batch() -> TaskEventBatchWrite:
    now = datetime.now(UTC)
    return TaskEventBatchWrite.model_validate(
        {
            "events": [
                {
                    "seq": 1,
                    "event_type": "status",
                    "level": "worker",
                    "message": "launching token=plain-secret",
                    "event_at": now.isoformat(),
                    "metadata": {"app_uuid": "app-1", "cookie": "secret"},
                },
                {
                    "seq": 2,
                    "event_type": "log",
                    "level": "L2",
                    "message": "robot task Test started",
                    "event_at": now.isoformat(),
                    "metadata": {},
                },
            ],
        },
    )


def test_event_batch_is_idempotent_redacted_and_incremental() -> None:
    service, repository, device_id, task_id = make_service()
    principal = WorkerPrincipal(device_id=device_id)

    first = service.append_events(principal, task_id, batch())
    duplicate = service.append_events(principal, task_id, batch())
    page = service.list_events(task_id, after_seq=1, limit=10)

    assert first.accepted_count == 2
    assert duplicate.accepted_count == 0
    assert page.next_after_seq == 2
    assert [event.seq for event in page.items] == [2]
    first_event = repository.events[(task_id, 1)]
    assert "plain-secret" not in first_event.message
    assert first_event.metadata_json["cookie"] == "[REDACTED]"


def test_event_history_uses_bounded_sequence_cursor_in_ascending_order() -> None:
    service, _, device_id, task_id = make_service()
    principal = WorkerPrincipal(device_id=device_id)
    now = datetime.now(UTC)
    service.append_events(
        principal,
        task_id,
        TaskEventBatchWrite.model_validate(
            {
                "events": [
                    {
                        "seq": seq,
                        "event_type": "log",
                        "level": "INFO",
                        "message": f"event {seq}",
                        "event_at": now.isoformat(),
                        "metadata": {},
                    }
                    for seq in range(1, 7)
                ],
            },
        ),
    )

    latest = service.list_events(
        task_id,
        after_seq=None,
        before_seq=None,
        limit=2,
    )
    earlier = service.list_events(
        task_id,
        after_seq=None,
        before_seq=latest.next_before_seq,
        limit=2,
    )
    incremental = service.list_events(
        task_id,
        after_seq=4,
        before_seq=None,
        limit=2,
    )

    assert [event.seq for event in latest.items] == [5, 6]
    assert latest.has_more_before is True
    assert latest.next_before_seq == 5
    assert [event.seq for event in earlier.items] == [3, 4]
    assert earlier.next_before_seq == 3
    assert [event.seq for event in incremental.items] == [5, 6]
    assert incremental.has_more_before is False


def test_worker_cannot_write_another_devices_task() -> None:
    service, _, _, task_id = make_service()

    with pytest.raises(TaskEventForbiddenError):
        service.append_events(
            WorkerPrincipal(device_id=uuid4()),
            task_id,
            batch(),
        )


def test_active_summary_uses_latest_runtime_event() -> None:
    service, _, device_id, task_id = make_service()
    service.append_events(WorkerPrincipal(device_id=device_id), task_id, batch())

    summary = service.get_active_summary(device_id)

    assert summary is not None
    assert summary.task_id == task_id
    assert summary.latest_event is not None
    assert summary.latest_event.seq == 2
