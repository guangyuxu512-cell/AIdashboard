from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.access.models import Team
from app.modules.devices.models import Device
from app.modules.tasks.enums import TaskStatus
from app.modules.tasks.models import Task, TaskEvent
from app.modules.tasks.service import TaskService


pytestmark = pytest.mark.integration


def _task(
    *,
    task_id: UUID,
    team_id: UUID,
    device_id: UUID,
    status: TaskStatus,
    created_at: datetime,
    name: str,
    finished_at: datetime | None = None,
) -> Task:
    values = {
        "task_id": task_id,
        "team_id": team_id,
        "created_by_user_id": None,
        "target_device_id": device_id,
        "skill_id": "system.echo",
        "execution_display_name": name,
        "status": status.value,
        "input_json": {"message": name},
        "error_code": "FIXTURE_FAILED" if status is TaskStatus.FAILED else None,
        "error_message": (
            "safe fixture error" if status is TaskStatus.FAILED else None
        ),
        "started_at": created_at if status is not TaskStatus.PENDING else None,
        "finished_at": finished_at,
        "created_at": created_at,
        "updated_at": finished_at or created_at,
    }
    if status is TaskStatus.SUCCESS:
        values["result_json"] = {"message": "kept"}
    return Task(
        **values,
    )


def _event(task_id: UUID, seq: int, at: datetime) -> TaskEvent:
    return TaskEvent(
        task_id=task_id,
        seq=seq,
        event_type="log",
        level="INFO",
        message=f"event {seq}",
        event_at=at,
        metadata_json={},
    )


def _actor(team_id: UUID) -> ActorContext:
    return ActorContext(
        user_id=uuid4(),
        user_display_name="Task query fixture",
        team_id=team_id,
        membership_id=uuid4(),
        role_code="member",
        data_scope=DataScope.TEAM,
    )


def _cleanup(engine: Engine, device_ids: set[UUID], *, team_id: UUID) -> None:
    with Session(engine) as session:
        task_ids = list(
            session.scalars(
                select(Task.task_id).where(Task.target_device_id.in_(device_ids)),
            ),
        )
        if task_ids:
            session.execute(delete(TaskEvent).where(TaskEvent.task_id.in_(task_ids)))
            session.execute(delete(Task).where(Task.task_id.in_(task_ids)))
        session.execute(delete(Device).where(Device.device_id.in_(device_ids)))
        session.execute(delete(Team).where(Team.team_id == team_id))
        session.commit()


def test_task_date_ranges_combine_with_status_device_and_search(
    postgresql_engine: Engine,
) -> None:
    device_a = uuid4()
    device_b = uuid4()
    device_ids = {device_a, device_b}
    team_id = uuid4()
    actor = _actor(team_id)
    search_marker = f"date-fixture-{device_a}"
    start_today = datetime.now(UTC).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    ids = {
        "today": UUID("31000000-0000-4000-8000-000000000001"),
        "today_second": UUID("31000000-0000-4000-8000-000000000002"),
        "yesterday": uuid4(),
        "six_days": uuid4(),
        "eight_days": uuid4(),
        "thirty_one_days": uuid4(),
    }
    try:
        with Session(postgresql_engine) as session:
            session.add(Team(team_id=team_id, name="Task Query Integration Team"))
            session.flush()
            session.add_all(
                [
                    Device(
                        device_id=device_a,
                        team_id=team_id,
                        display_name="日期设备 A",
                    ),
                    Device(
                        device_id=device_b,
                        team_id=team_id,
                        display_name="日期设备 B",
                    ),
                    _task(
                        task_id=ids["today"],
                        team_id=team_id,
                        device_id=device_a,
                        status=TaskStatus.FAILED,
                        created_at=start_today,
                        name=f"{search_marker}-today-failed",
                        finished_at=start_today + timedelta(minutes=1),
                    ),
                    _task(
                        task_id=ids["today_second"],
                        team_id=team_id,
                        device_id=device_a,
                        status=TaskStatus.SUCCESS,
                        created_at=start_today,
                        name=f"{search_marker}-today-success",
                        finished_at=start_today + timedelta(minutes=1),
                    ),
                    _task(
                        task_id=ids["yesterday"],
                        team_id=team_id,
                        device_id=device_a,
                        status=TaskStatus.FAILED,
                        created_at=start_today - timedelta(hours=23),
                        name=f"{search_marker}-target",
                        finished_at=start_today - timedelta(hours=22),
                    ),
                    _task(
                        task_id=ids["six_days"],
                        team_id=team_id,
                        device_id=device_b,
                        status=TaskStatus.PENDING,
                        created_at=start_today - timedelta(days=6),
                        name=f"{search_marker}-seven-day-boundary",
                    ),
                    _task(
                        task_id=ids["eight_days"],
                        team_id=team_id,
                        device_id=device_b,
                        status=TaskStatus.RUNNING,
                        created_at=start_today - timedelta(days=8),
                        name=f"{search_marker}-thirty-day",
                    ),
                    _task(
                        task_id=ids["thirty_one_days"],
                        team_id=team_id,
                        device_id=device_b,
                        status=TaskStatus.SUCCESS,
                        created_at=start_today - timedelta(days=31),
                        name=f"{search_marker}-all-history",
                        finished_at=start_today - timedelta(days=30),
                    ),
                ],
            )
            session.commit()

        with Session(postgresql_engine) as session:
            service = TaskService(session)

            def query(
                created_from: datetime | None,
                created_to: datetime | None,
                *,
                status: TaskStatus | None = None,
                device_id: UUID | None = None,
                search: str | None = search_marker,
            ) -> list[UUID]:
                return [
                    item.task_id
                    for item in service.list_management_tasks(
                        actor=actor,
                        page=1,
                        page_size=20,
                        status=status,
                        device_id=device_id,
                        search=search,
                        created_from=created_from,
                        created_to=created_to,
                    ).items
                ]

            today_ids = query(start_today, start_today + timedelta(days=1))
            yesterday_ids = query(
                start_today - timedelta(days=1),
                start_today,
            )
            seven_day_ids = query(
                start_today - timedelta(days=6),
                start_today + timedelta(days=1),
            )
            thirty_day_ids = query(
                start_today - timedelta(days=29),
                start_today + timedelta(days=1),
            )
            all_ids = query(None, None)
            combined = query(
                start_today - timedelta(days=1),
                start_today + timedelta(days=1),
                status=TaskStatus.FAILED,
                device_id=device_a,
                search=f"{search_marker}-target",
            )

        assert today_ids == [ids["today_second"], ids["today"]]
        assert yesterday_ids == [ids["yesterday"]]
        assert set(seven_day_ids) == {
            ids["today"],
            ids["today_second"],
            ids["yesterday"],
            ids["six_days"],
        }
        assert ids["eight_days"] in thirty_day_ids
        assert ids["thirty_one_days"] not in thirty_day_ids
        assert set(ids.values()) <= set(all_ids)
        assert combined == [ids["yesterday"]]
    finally:
        _cleanup(postgresql_engine, device_ids, team_id=team_id)


def test_runtime_event_sequence_pages_are_bounded_complete_and_ordered(
    postgresql_engine: Engine,
) -> None:
    device_id = uuid4()
    task_id = uuid4()
    team_id = uuid4()
    actor = _actor(team_id)
    now = datetime.now(UTC)
    try:
        with Session(postgresql_engine) as session:
            session.add(Team(team_id=team_id, name="Task Event Integration Team"))
            session.flush()
            session.add(
                Device(
                    device_id=device_id,
                    team_id=team_id,
                    display_name="日志分页设备",
                ),
            )
            session.add(
                _task(
                    task_id=task_id,
                    team_id=team_id,
                    device_id=device_id,
                    status=TaskStatus.SUCCESS,
                    created_at=now,
                    name="日志分页任务",
                    finished_at=now,
                ),
            )
            session.add_all([_event(task_id, seq, now) for seq in range(1, 251)])
            session.commit()

        with Session(postgresql_engine) as session:
            service = TaskService(session)
            latest = service.list_events(
                actor,
                task_id,
                after_seq=None,
                before_seq=None,
                limit=100,
            )
            middle = service.list_events(
                actor,
                task_id,
                after_seq=None,
                before_seq=latest.items[0].seq,
                limit=100,
            )
            earliest = service.list_events(
                actor,
                task_id,
                after_seq=None,
                before_seq=middle.items[0].seq,
                limit=100,
            )
            live = service.list_events(
                actor,
                task_id,
                after_seq=200,
                before_seq=None,
                limit=100,
            )

        combined = earliest.items + middle.items + latest.items
        assert [event.seq for event in latest.items] == list(range(151, 251))
        assert [event.seq for event in middle.items] == list(range(51, 151))
        assert [event.seq for event in earliest.items] == list(range(1, 51))
        assert [event.seq for event in combined] == list(range(1, 251))
        assert [event.seq for event in live.items] == list(range(201, 251))
        assert latest.has_more_before is True
        assert middle.has_more_before is True
        assert earliest.has_more_before is False
    finally:
        _cleanup(postgresql_engine, {device_id}, team_id=team_id)


def test_retention_only_purges_expired_terminal_events_and_keeps_tasks(
    postgresql_engine: Engine,
) -> None:
    device_id = uuid4()
    team_id = uuid4()
    actor = _actor(team_id)
    now = datetime.now(UTC)
    old = now - timedelta(days=91)
    recent = now - timedelta(days=89)
    task_ids = {
        status: uuid4()
        for status in ["success", "failed", "lost", "running", "pending"]
    }
    no_event_id = uuid4()
    recent_id = uuid4()
    try:
        with Session(postgresql_engine) as session:
            session.add(Team(team_id=team_id, name="Task Retention Integration Team"))
            session.flush()
            session.add(
                Device(
                    device_id=device_id,
                    team_id=team_id,
                    display_name="Retention 设备",
                ),
            )
            for status in (
                TaskStatus.SUCCESS,
                TaskStatus.FAILED,
                TaskStatus.LOST,
                TaskStatus.RUNNING,
                TaskStatus.PENDING,
            ):
                terminal = status in {
                    TaskStatus.SUCCESS,
                    TaskStatus.FAILED,
                    TaskStatus.LOST,
                }
                task_id = task_ids[status.value]
                session.add(
                    _task(
                        task_id=task_id,
                        team_id=team_id,
                        device_id=device_id,
                        status=status,
                        created_at=old,
                        name=f"Retention {status.value}",
                        finished_at=old if terminal else None,
                    ),
                )
                session.add(_event(task_id, 1, old))
            session.add(
                _task(
                    task_id=no_event_id,
                    team_id=team_id,
                    device_id=device_id,
                    status=TaskStatus.SUCCESS,
                    created_at=old,
                    name="无日志历史任务",
                    finished_at=old,
                ),
            )
            session.add(
                _task(
                    task_id=recent_id,
                    team_id=team_id,
                    device_id=device_id,
                    status=TaskStatus.SUCCESS,
                    created_at=recent,
                    name="保留期内任务",
                    finished_at=recent,
                ),
            )
            session.add(_event(recent_id, 1, recent))
            session.commit()

        settings = Settings(
            task_event_retention_days=90,
            task_event_retention_batch_size=2,
        )
        with Session(postgresql_engine) as session:
            first = TaskService(session, settings=settings).purge_expired_events(
                now=now,
            )
        with Session(postgresql_engine) as session:
            second = TaskService(session, settings=settings).purge_expired_events(
                now=now,
            )

        with Session(postgresql_engine) as session:
            tasks = {
                task.task_id: task
                for task in session.scalars(
                    select(Task).where(Task.target_device_id == device_id),
                )
            }
            remaining_event_task_ids = set(
                session.scalars(
                    select(TaskEvent.task_id).where(
                        TaskEvent.task_id.in_(tasks),
                    ),
                ),
            )

            assert first.tasks_purged == 3
            assert first.events_deleted == 3
            assert second.tasks_purged == 0
            assert second.events_deleted == 0
            assert len(tasks) == 7
            for status in ("success", "failed", "lost"):
                assert tasks[task_ids[status]].runtime_events_purged_at == now
                assert task_ids[status] not in remaining_event_task_ids
            assert tasks[no_event_id].runtime_events_purged_at is None
            assert task_ids["running"] in remaining_event_task_ids
            assert task_ids["pending"] in remaining_event_task_ids
            assert recent_id in remaining_event_task_ids
            assert tasks[task_ids["success"]].result_json == {"message": "kept"}
            assert tasks[task_ids["failed"]].error_message == "safe fixture error"

            session.add(_event(task_ids["success"], 2, now))
            session.commit()

        with Session(postgresql_engine) as session:
            partial = TaskService(session).list_events(
                actor,
                task_ids["success"],
                after_seq=None,
                before_seq=None,
                limit=100,
            )
            purged_task = session.get(Task, task_ids["success"])

        assert [event.seq for event in partial.items] == [2]
        assert purged_task is not None
        assert purged_task.runtime_events_purged_at is not None
    finally:
        _cleanup(postgresql_engine, {device_id}, team_id=team_id)
