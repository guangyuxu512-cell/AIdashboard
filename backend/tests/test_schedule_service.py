from datetime import UTC, datetime, time
from uuid import UUID, uuid4

from app.modules.schedules.enums import ScheduleRunTriggerResult
from app.modules.schedules.models import Schedule
from app.modules.schedules.service import ScheduleService
from app.modules.tasks.exceptions import TaskDeviceDisabledError
from app.modules.tasks.models import Task
from app.modules.tasks.service import PreparedTaskCreation
from tests.support import FakeSession


class FakeScheduleRepository:
    def __init__(self, schedule: Schedule | None = None) -> None:
        self.schedule = schedule
        self.runs: list[object] = []
        self.claimed = False

    def get_next_due(self, *, now: datetime) -> Schedule | None:
        if self.claimed or self.schedule is None:
            return None
        if not self.schedule.enabled or self.schedule.next_run_at is None:
            return None
        if self.schedule.next_run_at > now:
            return None
        self.claimed = True
        return self.schedule

    def add_run(self, run: object) -> None:
        self.runs.append(run)


class FakeScheduledTaskService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls = 0
        self.prepared_data: object | None = None
        self.created_data: object | None = None

    def prepare_scheduled_task(self, data: object) -> PreparedTaskCreation:
        self.prepared_data = data
        return PreparedTaskCreation(
            input_json={"app_id": "safe-app", "params": {}},
            execution_display_name="安全应用",
        )

    def create_for_schedule(self, data: object) -> Task:
        self.created_data = data
        self.calls += 1
        if self.error is not None:
            raise self.error
        return Task(
            task_id=uuid4(),
            target_device_id=uuid4(),
            skill_id="yingdao.app.run",
            execution_display_name="安全应用",
            status="pending",
            input_json={"app_id": "safe-app", "params": {}},
        )


def due_schedule() -> Schedule:
    return Schedule(
        schedule_id=UUID("61000000-0000-4000-8000-000000000001"),
        name="每日安全任务",
        enabled=True,
        target_device_id=uuid4(),
        shop_id=UUID("62000000-0000-4000-8000-000000000001"),
        skill_id="yingdao.app.run",
        execution_display_name="安全应用",
        schedule_type="daily",
        local_time=time(9, 30),
        timezone="Asia/Shanghai",
        task_input_json={"app_id": "safe-app", "params": {}},
        next_run_at=datetime(2026, 8, 20, 1, 30, tzinfo=UTC),
    )


def test_due_scan_coalesces_missed_days_and_creates_one_pending_task() -> None:
    schedule = due_schedule()
    repository = FakeScheduleRepository(schedule)
    task_service = FakeScheduledTaskService()
    session = FakeSession()
    result = ScheduleService(
        session,  # type: ignore[arg-type]
        repository,  # type: ignore[arg-type]
        task_service,  # type: ignore[arg-type]
    ).trigger_next_due(now=datetime(2026, 8, 24, 12, 0, tzinfo=UTC))

    assert result is not None
    assert result.trigger_result is ScheduleRunTriggerResult.TASK_CREATED
    assert result.scheduled_for == datetime(2026, 8, 24, 1, 30, tzinfo=UTC)
    assert result.task_id is not None
    assert task_service.calls == 1
    assert getattr(task_service.created_data, "shop_id") == schedule.shop_id
    assert schedule.next_run_at == datetime(2026, 8, 25, 1, 30, tzinfo=UTC)
    assert session.commits == 1
    assert len(repository.runs) == 1


def test_guard_failure_records_blocked_occurrence_and_advances_schedule() -> None:
    schedule = due_schedule()
    repository = FakeScheduleRepository(schedule)
    session = FakeSession()
    result = ScheduleService(
        session,  # type: ignore[arg-type]
        repository,  # type: ignore[arg-type]
        FakeScheduledTaskService(TaskDeviceDisabledError()),  # type: ignore[arg-type]
    ).trigger_next_due(now=datetime(2026, 8, 24, 12, 0, tzinfo=UTC))

    assert result is not None
    assert result.trigger_result is ScheduleRunTriggerResult.BLOCKED
    assert result.task_id is None
    run = repository.runs[0]
    assert getattr(run, "trigger_error_code") == "TASK_DEVICE_DISABLED"
    assert schedule.next_run_at == datetime(2026, 8, 25, 1, 30, tzinfo=UTC)


def test_no_due_schedule_rolls_back_read_transaction() -> None:
    session = FakeSession()
    result = ScheduleService(
        session,  # type: ignore[arg-type]
        FakeScheduleRepository(),  # type: ignore[arg-type]
        FakeScheduledTaskService(),  # type: ignore[arg-type]
    ).trigger_next_due(now=datetime(2026, 8, 24, 12, 0, tzinfo=UTC))

    assert result is None
    assert session.rollbacks == 1
