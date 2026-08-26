from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.modules.credentials.schemas import TaskAccountPayload
from app.modules.tasks.enums import (
    TASK_SKILL_ID_MAX_LENGTH,
    TASK_SKILL_ID_PATTERN,
    TaskEventType,
    TaskStatus,
)
from app.modules.tasks.models import Task, TaskEvent


TASK_EVENT_DEFAULT_LIMIT = 100
TASK_EVENT_MAX_LIMIT = 200


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_device_id: UUID
    shop_ids: list[UUID] = Field(default_factory=list, max_length=100)
    asset_ids: list[UUID] = Field(default_factory=list, max_length=100)
    skill_id: str = Field(
        min_length=3,
        max_length=TASK_SKILL_ID_MAX_LENGTH,
        pattern=TASK_SKILL_ID_PATTERN,
    )
    input: dict[str, Any]

    @field_validator("shop_ids")
    @classmethod
    def reject_duplicate_shops(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("shop_ids must not contain duplicates")
        return value

    @field_validator("asset_ids")
    @classmethod
    def reject_duplicate_assets(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("asset_ids must not contain duplicates")
        return value


class TaskCreatedRange(BaseModel):
    created_from: AwareDatetime | None = None
    created_to: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_order(self) -> "TaskCreatedRange":
        if (
            self.created_from is not None
            and self.created_to is not None
            and self.created_from >= self.created_to
        ):
            raise ValueError("created_from must be earlier than created_to")
        return self


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: UUID
    target_device_id: UUID
    shop_ids: list[UUID]
    asset_ids: list[UUID]
    skill_id: str
    execution_display_name: str
    status: TaskStatus
    input: dict[str, Any]
    result: dict[str, Any] | None
    error_code: str | None
    error_message: str | None
    lease_until: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    runtime_events_purged_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WorkerTaskAssetRead(BaseModel):
    asset_id: UUID
    filename: str
    position: int = Field(ge=0)
    content_type: str
    size_bytes: int = Field(gt=0)
    sha256: str = Field(min_length=64, max_length=64)
    download_path: str


class WorkerTaskRead(BaseModel):
    task_id: UUID
    skill_id: str
    input: dict[str, Any]
    lease_until: datetime
    accounts: list[TaskAccountPayload] = Field(default_factory=list, repr=False)
    assets: list[WorkerTaskAssetRead] = Field(default_factory=list)


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


class TaskEventCursor(BaseModel):
    after_seq: int | None = Field(default=None, ge=0)
    before_seq: int | None = Field(default=None, gt=0)
    limit: int = Field(default=TASK_EVENT_DEFAULT_LIMIT, ge=1, le=TASK_EVENT_MAX_LIMIT)

    @model_validator(mode="after")
    def validate_direction(self) -> "TaskEventCursor":
        if self.after_seq is not None and self.before_seq is not None:
            raise ValueError("after_seq and before_seq cannot be used together")
        return self


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
    after_seq: int | None
    before_seq: int | None
    next_after_seq: int
    next_before_seq: int | None
    has_more_before: bool
    items: list[TaskEventRead]


class TaskEventPurgeRead(BaseModel):
    cutoff: datetime
    tasks_purged: int
    events_deleted: int


class ActiveTaskSummaryRead(BaseModel):
    task_id: UUID
    target_device_id: UUID
    skill_id: str
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
    skill_id: str
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
        shop_ids=task.shop_ids,
        asset_ids=task.asset_ids,
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
        runtime_events_purged_at=task.runtime_events_purged_at,
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
