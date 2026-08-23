from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.tasks.enums import TaskEventType, TaskSkillId, TaskStatus
from app.modules.tasks.models import Task, TaskEvent


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
    execution_display_name: str
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


class TaskEventWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seq: int = Field(gt=0)
    event_type: TaskEventType
    level: str = Field(min_length=1, max_length=16)
    message: str = Field(max_length=10_000)
    event_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskEventBatchWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[TaskEventWrite] = Field(min_length=1, max_length=100)


class TaskEventBatchResult(BaseModel):
    task_id: UUID
    accepted_count: int
    highest_seq: int


class TaskEventRead(BaseModel):
    event_id: UUID
    task_id: UUID
    seq: int
    event_type: TaskEventType
    level: str
    message: str
    event_at: datetime
    metadata: dict[str, Any]
    created_at: datetime


class TaskEventListRead(BaseModel):
    task_id: UUID
    after_seq: int
    next_after_seq: int
    items: list[TaskEventRead]


class ActiveTaskSummaryRead(BaseModel):
    task_id: UUID
    target_device_id: UUID
    skill_id: TaskSkillId
    execution_display_name: str
    status: TaskStatus
    started_at: datetime | None
    created_at: datetime
    latest_event: TaskEventRead | None


class TaskProgressSummaryRead(BaseModel):
    current: int = Field(ge=0)
    total: int | None = Field(default=None, gt=0)


class TaskListItemRead(BaseModel):
    task_id: UUID
    target_device_id: UUID
    device_display_name: str
    skill_id: TaskSkillId
    skill_display_name: str | None
    execution_display_name: str
    status: TaskStatus
    progress: TaskProgressSummaryRead | None
    current_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


def task_to_read(task: Task) -> TaskRead:
    return TaskRead(
        task_id=task.task_id,
        target_device_id=task.target_device_id,
        skill_id=task.skill_id,
        execution_display_name=task.execution_display_name,
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


def task_event_to_read(event: TaskEvent) -> TaskEventRead:
    return TaskEventRead(
        event_id=event.event_id,
        task_id=event.task_id,
        seq=event.seq,
        event_type=event.event_type,
        level=event.level,
        message=event.message,
        event_at=event.event_at,
        metadata=event.metadata_json,
        created_at=event.created_at,
    )
