from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.tasks.enums import TaskSkillId, TaskStatus
from app.modules.tasks.models import Task


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_device_id: UUID
    skill_id: TaskSkillId
    input: dict[str, Any]


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: UUID
    target_device_id: UUID
    skill_id: TaskSkillId
    status: TaskStatus
    input: dict[str, Any]
    result: dict[str, Any] | None
    error_code: str | None
    error_message: str | None
    lease_until: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WorkerTaskRead(BaseModel):
    task_id: UUID
    skill_id: TaskSkillId
    input: dict[str, Any]
    lease_until: datetime


class TaskLeaseRead(BaseModel):
    task_id: UUID
    status: TaskStatus
    lease_until: datetime


class TaskComplete(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: dict[str, Any]


class TaskFail(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    error_code: str = Field(min_length=1, max_length=64)
    error_message: str = Field(min_length=1, max_length=2000)


def task_to_read(task: Task) -> TaskRead:
    return TaskRead(
        task_id=task.task_id,
        target_device_id=task.target_device_id,
        skill_id=task.skill_id,
        status=task.status,
        input=task.input_json,
        result=task.result_json,
        error_code=task.error_code,
        error_message=task.error_message,
        lease_until=task.lease_until,
        started_at=task.started_at,
        finished_at=task.finished_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )
