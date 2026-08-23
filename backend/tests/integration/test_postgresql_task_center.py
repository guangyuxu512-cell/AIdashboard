from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, delete, event, select
from sqlalchemy.orm import Session

from app.modules.devices.models import Device
from app.modules.tasks.enums import TaskStatus
from app.modules.tasks.models import Task, TaskEvent
from app.modules.tasks.service import TaskService


pytestmark = pytest.mark.integration


def _cleanup(engine: Engine, device_ids: set[UUID]) -> None:
    with Session(engine) as session:
        task_ids = list(
            session.scalars(
                select(Task.task_id).where(Task.target_device_id.in_(device_ids)),
            ),
        )
        if task_ids:
            session.execute(delete(TaskEvent).where(TaskEvent.task_id.in_(task_ids)))
        session.execute(delete(Task).where(Task.target_device_id.in_(device_ids)))
        session.execute(delete(Device).where(Device.device_id.in_(device_ids)))
        session.commit()


def test_task_center_query_is_stable_summarized_and_has_no_n_plus_one(
    postgresql_engine: Engine,
) -> None:
    device_a = uuid4()
    device_b = uuid4()
    device_ids = {device_a, device_b}
    task_a = UUID("20000000-0000-4000-8000-000000000001")
    task_b = UUID("20000000-0000-4000-8000-000000000002")
    task_failed = uuid4()
    task_pending = uuid4()
    now = datetime.now(UTC)
    try:
        with Session(postgresql_engine) as session:
            deleted_device = Device(
                device_id=device_b,
                display_name="历史设备",
                deleted_at=now,
            )
            session.add_all(
                [
                    Device(device_id=device_a, display_name="PC-11"),
                    deleted_device,
                    Task(
                        task_id=task_a,
                        target_device_id=device_a,
                        skill_id="system.sleep",
                        execution_display_name="进度测试 A",
                        status=TaskStatus.RUNNING.value,
                        input_json={"seconds": 5},
                        started_at=now,
                        created_at=now,
                        updated_at=now,
                    ),
                    Task(
                        task_id=task_b,
                        target_device_id=device_a,
                        skill_id="system.echo",
                        execution_display_name="进度测试 B",
                        status=TaskStatus.SUCCESS.value,
                        input_json={"message": "ok"},
                        result_json={"message": "ok"},
                        started_at=now,
                        finished_at=now + timedelta(seconds=1),
                        created_at=now,
                        updated_at=now,
                    ),
                    Task(
                        task_id=task_failed,
                        target_device_id=device_b,
                        skill_id="yingdao.test",
                        execution_display_name="历史影刀测试",
                        status=TaskStatus.FAILED.value,
                        input_json={},
                        error_code="RUNTIME_FAILED",
                        error_message="执行失败 token=secret",
                        started_at=now - timedelta(minutes=1),
                        finished_at=now,
                        created_at=now - timedelta(minutes=1),
                        updated_at=now,
                    ),
                    Task(
                        task_id=task_pending,
                        target_device_id=device_a,
                        skill_id="yingdao.app.run",
                        execution_display_name="待执行应用",
                        status=TaskStatus.PENDING.value,
                        input_json={"app_id": "fixture", "params": {}},
                        created_at=now - timedelta(minutes=2),
                        updated_at=now - timedelta(minutes=2),
                    ),
                    TaskEvent(
                        task_id=task_a,
                        seq=1,
                        event_type="status",
                        level="worker",
                        message="开始执行",
                        event_at=now,
                        metadata_json={},
                    ),
                    TaskEvent(
                        task_id=task_a,
                        seq=2,
                        event_type="progress",
                        level="worker",
                        message="正在处理第 3 项",
                        event_at=now,
                        metadata_json={"current": 3, "total": 10},
                    ),
                    TaskEvent(
                        task_id=task_a,
                        seq=3,
                        event_type="log",
                        level="INFO",
                        message="后续普通日志",
                        event_at=now,
                        metadata_json={},
                    ),
                ],
            )
            session.commit()

        select_count = 0

        def count_selects(
            _connection: object,
            _cursor: object,
            statement: str,
            _parameters: object,
            _context: object,
            _executemany: object,
        ) -> None:
            nonlocal select_count
            if statement.lstrip().upper().startswith("SELECT"):
                select_count += 1

        event.listen(postgresql_engine, "before_cursor_execute", count_selects)
        try:
            with Session(postgresql_engine) as session:
                page = TaskService(session).list_management_tasks(
                    page=1,
                    page_size=20,
                    status=None,
                    device_id=device_a,
                    search=None,
                )
        finally:
            event.remove(postgresql_engine, "before_cursor_execute", count_selects)

        assert select_count == 2
        assert page.total == 3
        assert [item.task_id for item in page.items[:2]] == [task_b, task_a]
        running = next(item for item in page.items if item.task_id == task_a)
        assert running.progress is not None
        assert running.progress.model_dump() == {"current": 3, "total": 10}
        assert running.current_message == "正在处理第 3 项"
        pending = next(item for item in page.items if item.task_id == task_pending)
        assert pending.started_at is None

        with Session(postgresql_engine) as session:
            service = TaskService(session)
            running_page = service.list_management_tasks(
                page=1,
                page_size=20,
                status=TaskStatus.RUNNING,
                device_id=device_a,
                search="进度测试",
            )
            id_search_page = service.list_management_tasks(
                page=1,
                page_size=20,
                status=None,
                device_id=None,
                search=str(task_failed),
            )

        assert [item.task_id for item in running_page.items] == [task_a]
        assert [item.task_id for item in id_search_page.items] == [task_failed]
        assert id_search_page.items[0].device_display_name == "历史设备"
        assert id_search_page.items[0].current_message == "执行失败 token=[REDACTED]"
    finally:
        _cleanup(postgresql_engine, device_ids)
