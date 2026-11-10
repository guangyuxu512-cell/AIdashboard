from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.tasks.enums import TaskStatus
from app.modules.tasks.exceptions import TaskStateConflictError
from app.modules.tasks.schemas import TaskComplete, TaskFail
from app.modules.tasks.service import TaskService
from app.modules.workers.service import WorkerPrincipal


class _Session:
    def __init__(self):
        self.rollbacks = 0
        self.commits = 0

    def rollback(self):
        self.rollbacks += 1

    def commit(self):
        self.commits += 1


class _Repository:
    def __init__(self, task):
        self.task = task

    def complete(self, **_):
        return None

    def get(self, task_id):
        return self.task if self.task.task_id == task_id else None


def _service(task):
    return TaskService(_Session(), repository=_Repository(task))


def test_success_ack_replay_is_idempotent_for_same_device():
    task = SimpleNamespace(task_id=uuid4(), target_device_id=uuid4(),
                           status=TaskStatus.SUCCESS.value,
                           result_json={"items": [{"id": "1"}]},
                           error_code=None, error_message=None)
    service = _service(task)
    assert service.complete(WorkerPrincipal(task.target_device_id), task.task_id,
                            TaskComplete(result={"items": [{"id": "1"}]})) is task
    assert service.session.rollbacks == 1
    assert service.session.commits == 0


def test_success_replay_with_other_result_or_device_is_conflict():
    task = SimpleNamespace(task_id=uuid4(), target_device_id=uuid4(),
                           status=TaskStatus.SUCCESS.value, result_json={"value": 1},
                           error_code=None, error_message=None)
    service = _service(task)
    with pytest.raises(TaskStateConflictError):
        service.complete(WorkerPrincipal(task.target_device_id), task.task_id,
                         TaskComplete(result={"value": 2}))
    with pytest.raises(TaskStateConflictError):
        service.complete(WorkerPrincipal(uuid4()), task.task_id,
                         TaskComplete(result={"value": 1}))


def test_failure_ack_replay_and_lost_task_remain_distinct():
    task = SimpleNamespace(task_id=uuid4(), target_device_id=uuid4(),
                           status=TaskStatus.FAILED.value, result_json=None,
                           error_code="TEST_FAILED", error_message="safe failure")
    service = _service(task)
    principal = WorkerPrincipal(task.target_device_id)
    data = TaskFail(error_code="TEST_FAILED", error_message="safe failure")
    assert service.fail(principal, task.task_id, data) is task
    task.status = TaskStatus.LOST.value
    with pytest.raises(TaskStateConflictError):
        service.fail(principal, task.task_id, data)
