from datetime import datetime, time
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.schedules.enums import ScheduleRunTriggerResult, ScheduleType
from app.modules.schedules.time_rules import get_schedule_timezone
from app.modules.tasks.enums import TaskSkillId, TaskStatus


class ScheduleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    target_device_id: UUID
    application_id: str = Field(min_length=1, max_length=200)
    parameters: dict[str, Any] = Field(default_factory=dict)
    schedule_type: ScheduleType = ScheduleType.DAILY
    local_time: time
    timezone: str = Field(min_length=1, max_length=100)
    enabled: bool = True

    @field_validator("local_time")
    @classmethod
    def normalize_local_time(cls, value: time) -> time:
        if value.tzinfo is not None:
            raise ValueError("local_time must not include an offset")
        return value.replace(second=0, microsecond=0)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        get_schedule_timezone(value)
        return value


class ScheduleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=200)
    target_device_id: UUID | None = None
    application_id: str | None = Field(default=None, min_length=1, max_length=200)
    parameters: dict[str, Any] | None = None
    schedule_type: ScheduleType | None = None
    local_time: time | None = None
    timezone: str | None = Field(default=None, min_length=1, max_length=100)
    enabled: bool | None = None

    @field_validator("local_time")
    @classmethod
    def normalize_local_time(cls, value: time | None) -> time | None:
        if value is None:
            return None
        if value.tzinfo is not None:
            raise ValueError("local_time must not include an offset")
        return value.replace(second=0, microsecond=0)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is not None:
            get_schedule_timezone(value)
        return value

    @model_validator(mode="after")
    def validate_patch(self) -> "ScheduleUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class ScheduleRunRead(BaseModel):
    run_id: UUID
    schedule_id: UUID
    scheduled_for: datetime
    task_id: UUID | None
    task_status: TaskStatus | None
    trigger_result: ScheduleRunTriggerResult
    trigger_error_code: str | None
    trigger_error_message: str | None
    created_at: datetime


class ScheduleListItemRead(BaseModel):
    schedule_id: UUID
    name: str
    enabled: bool
    target_device_id: UUID
    device_display_name: str
    skill_id: TaskSkillId
    execution_display_name: str
    schedule_type: ScheduleType
    local_time: time
    timezone: str
    next_run_at: datetime | None
    latest_run: ScheduleRunRead | None
    created_at: datetime
    updated_at: datetime


class ScheduleRead(ScheduleListItemRead):
    application_id: str
    parameters: dict[str, Any]


class ScheduleTriggerSummary(BaseModel):
    run_id: UUID
    schedule_id: UUID
    scheduled_for: datetime
    trigger_result: ScheduleRunTriggerResult
    task_id: UUID | None
