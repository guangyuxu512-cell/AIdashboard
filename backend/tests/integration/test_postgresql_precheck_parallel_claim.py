from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.modules.access.models import Team
from app.modules.devices.models import Device
from app.modules.tasks.models import Task
from app.modules.tasks.service import TaskService
from app.modules.users.models import User
from app.modules.workers.service import WorkerPrincipal


pytestmark = pytest.mark.integration
PRECHECK = "douyin.category_schema"


@pytest.fixture
def devices(postgresql_engine):
    team_id, user_id = uuid4(), uuid4()
    ids = [uuid4() for _ in range(5)]
    with Session(postgresql_engine) as session:
        session.add_all([Team(team_id=team_id, name="parallel fixture"),
                         User(user_id=user_id, display_name="parallel fixture")])
        session.flush()
        session.add_all([Device(device_id=i, team_id=team_id, display_name="parallel fixture") for i in ids])
        session.commit()
    yield postgresql_engine, team_id, user_id, ids
    with Session(postgresql_engine) as session:
        session.execute(delete(Task).where(Task.target_device_id.in_(ids)))
        session.execute(delete(Device).where(Device.device_id.in_(ids)))
        session.execute(delete(User).where(User.user_id == user_id))
        session.execute(delete(Team).where(Team.team_id == team_id))
        session.commit()


def enqueue(session, team_id, user_id, device_id, shop, created, *, skill=PRECHECK):
    task = Task(task_id=uuid4(), team_id=team_id, created_by_user_id=user_id,
        target_device_id=device_id, skill_id=skill, execution_display_name="fixture",
        status="pending", input_json={"platform_shop_id": shop} if shop else {},
        created_at=created)
    session.add(task)
    return task.task_id


def claim(engine, device_id, *, precheck_only=True):
    with Session(engine, expire_on_commit=False) as session:
        result = TaskService(session).claim_with_context(
            WorkerPrincipal(device_id=device_id), precheck_only=precheck_only)
        return result.task if result else None


def test_five_devices_reach_75_without_a_global_cap(devices):
    engine, team_id, user_id, ids = devices
    now = datetime.now(UTC)
    with Session(engine) as session:
        for device_index, device_id in enumerate(ids):
            for shop_index in range(20):
                for item in range(4):
                    enqueue(session, team_id, user_id, device_id,
                            f"{team_id}-{device_index}-{shop_index}",
                            now + timedelta(microseconds=shop_index * 10 + item))
        session.commit()
    barrier = Barrier(5)

    def fill(device_id):
        barrier.wait(timeout=10)
        return [claim(engine, device_id) for _ in range(15)]

    with ThreadPoolExecutor(max_workers=5) as pool:
        all_claims = list(pool.map(fill, ids))
    for device_claims in all_claims:
        assert len(device_claims) == 15 and all(device_claims)
        counts = {}
        for task in device_claims:
            key = task.input_json["platform_shop_id"]
            counts[key] = counts.get(key, 0) + 1
        assert len(counts) == 5 and set(counts.values()) == {3}
    assert all(claim(engine, device_id) is None for device_id in ids)
    with Session(engine) as session:
        completed = session.get(Task, all_claims[0][0].task_id)
        completed.status = "success"
        completed.finished_at = datetime.now(UTC)
        session.commit()
    replacement = claim(engine, ids[0])
    assert replacement is not None
    assert replacement.input_json["platform_shop_id"] == all_claims[0][0].input_json["platform_shop_id"]


def test_same_store_is_capped_at_three_across_devices(devices):
    engine, team_id, user_id, ids = devices
    now = datetime.now(UTC)
    shared_shop = f"shared-{team_id}"
    with Session(engine) as session:
        for device_id in ids[:2]:
            for item in range(10):
                enqueue(session, team_id, user_id, device_id, shared_shop,
                        now + timedelta(microseconds=item))
        session.commit()
    barrier = Barrier(10)

    def race(index):
        barrier.wait(timeout=10)
        return claim(engine, ids[index % 2])

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(race, range(10)))
    assert sum(task is not None for task in results) == 3
    with Session(engine) as session:
        running = session.scalars(select(Task).where(
            Task.target_device_id.in_(ids), Task.status == "running")).all()
        assert len(running) == 3
        enqueue(session, team_id, user_id, ids[0], f"other-{team_id}", now + timedelta(seconds=1))
        session.commit()
    other = claim(engine, ids[0])
    assert other is not None and other.input_json["platform_shop_id"] == f"other-{team_id}"


def test_ordinary_task_waits_for_active_prechecks_without_starvation(devices):
    engine, team_id, user_id, ids = devices
    device_id = ids[0]
    now = datetime.now(UTC)
    with Session(engine) as session:
        first = enqueue(session, team_id, user_id, device_id, f"a-{team_id}", now)
        second = enqueue(session, team_id, user_id, device_id, f"b-{team_id}", now + timedelta(seconds=1))
        normal = enqueue(session, team_id, user_id, device_id, None, now + timedelta(seconds=2), skill="system.echo")
        later = enqueue(session, team_id, user_id, device_id, f"c-{team_id}", now + timedelta(seconds=3))
        session.commit()
    assert claim(engine, device_id, precheck_only=False).task_id == first
    assert claim(engine, device_id).task_id == second
    assert claim(engine, device_id) is None
    with Session(engine) as session:
        for task_id in (first, second):
            session.get(Task, task_id).status = "success"
        session.commit()
    assert claim(engine, device_id, precheck_only=False).task_id == normal
    assert claim(engine, device_id) is None
    with Session(engine) as session:
        session.get(Task, normal).status = "success"
        session.commit()
    assert claim(engine, device_id, precheck_only=False).task_id == later
