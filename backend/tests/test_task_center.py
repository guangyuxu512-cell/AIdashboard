from datetime import UTC, datetime
from uuid import uuid4

from app.modules.tasks.enums import TaskStatus
from app.modules.tasks.models import Task
from app.modules.tasks.repository import TaskListRecord
from app.modules.tasks.service import TaskService
from tests.support import FakeSession


class FakeTaskListRepository:
    def __init__(self, records: list[TaskListRecord]) -> None:
        self.records = records
        self.arguments: dict[str, object] = {}

    def list_management_tasks(self, **kwargs: object) -> tuple[list[TaskListRecord], int]:
        self.arguments = kwargs
        return self.records, len(self.records)


def make_task(*, status: TaskStatus, error_message: str | None = None) -> Task:
    now = datetime.now(UTC)
    task = Task(
        task_id=uuid4(),
        target_device_id=uuid4(),
        skill_id="system.sleep",
        execution_display_name="安全等待",
        status=status.value,
        input_json={"seconds": 1},
        error_message=error_message,
        started_at=now if status is not TaskStatus.PENDING else None,
        finished_at=now if status in {TaskStatus.SUCCESS, TaskStatus.FAILED} else None,
    )
    task.created_at = now
    task.updated_at = now
    return task


def test_task_list_maps_structured_progress_and_normalizes_search() -> None:
    task = make_task(status=TaskStatus.RUNNING)
    repository = FakeTaskListRepository(
        [
            TaskListRecord(
                task=task,
                device_display_name="PC-11",
                skill_display_name="系统等待",
                progress_message="正在处理第 3 项",
                progress_metadata={"current": 3, "total": 10},
                status_message="执行中",
                log_message="普通日志",
            ),
        ],
    )
    service = TaskService(
        FakeSession(),  # type: ignore[arg-type]
        repository,  # type: ignore[arg-type]
    )

    page = service.list_management_tasks(
        page=2,
        page_size=20,
        status=TaskStatus.RUNNING,
        device_id=task.target_device_id,
        search="  安全等待  ",
    )

    assert page.total == 1
    assert page.items[0].progress is not None
    assert page.items[0].progress.current == 3
    assert page.items[0].progress.total == 10
    assert page.items[0].current_message == "正在处理第 3 项"
    assert repository.arguments == {
        "offset": 20,
        "limit": 20,
        "status": TaskStatus.RUNNING,
        "device_id": task.target_device_id,
        "search": "安全等待",
    }


def test_task_list_rejects_invalid_progress_and_uses_status_then_log() -> None:
    task = make_task(status=TaskStatus.RUNNING)
    repository = FakeTaskListRepository(
        [
            TaskListRecord(
                task=task,
                device_display_name="PC-11",
                skill_display_name=None,
                progress_message="",
                progress_metadata={"current": 11, "total": 10},
                status_message="正在启动运行时",
                log_message="日志回退",
            ),
        ],
    )
    service = TaskService(
        FakeSession(),  # type: ignore[arg-type]
        repository,  # type: ignore[arg-type]
    )

    page = service.list_management_tasks(
        page=1,
        page_size=10,
        status=None,
        device_id=None,
        search=None,
    )

    assert page.items[0].progress is None
    assert page.items[0].current_message == "正在启动运行时"


def test_terminal_task_uses_redacted_error_and_success_fallback() -> None:
    failed = make_task(
        status=TaskStatus.FAILED,
        error_message="request token=plain-secret failed",
    )
    succeeded = make_task(status=TaskStatus.SUCCESS)
    repository = FakeTaskListRepository(
        [
            TaskListRecord(
                task=failed,
                device_display_name="PC-11",
                skill_display_name=None,
                progress_message="旧进度",
                progress_metadata=None,
                status_message=None,
                log_message=None,
            ),
            TaskListRecord(
                task=succeeded,
                device_display_name="PC-12",
                skill_display_name=None,
                progress_message=None,
                progress_metadata=None,
                status_message=None,
                log_message=None,
            ),
        ],
    )
    service = TaskService(
        FakeSession(),  # type: ignore[arg-type]
        repository,  # type: ignore[arg-type]
    )

    page = service.list_management_tasks(
        page=1,
        page_size=10,
        status=None,
        device_id=None,
        search=None,
    )

    assert page.items[0].current_message == "request token=[REDACTED] failed"
    assert page.items[1].current_message == "完成"
