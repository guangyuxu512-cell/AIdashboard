from datetime import date, datetime, time
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.schedules.enums import (
    ScheduleExecutionType,
    ScheduleRunTriggerResult,
    ScheduleType,
)
from app.modules.schedules.time_rules import (
    get_schedule_timezone,
    normalize_weekdays,
    validate_schedule_rule,
)
from app.modules.tasks.enums import (
    TASK_SKILL_ID_MAX_LENGTH,
    TASK_SKILL_ID_PATTERN,
    TaskStatus,
)


class ScheduleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    target_device_id: UUID
    shop_ids: list[UUID] = Field(default_factory=list, max_length=100)
    execution_type: ScheduleExecutionType = (
        ScheduleExecutionType.YINGDAO_APPLICATION
    )
    application_id: str | None = Field(default=None, min_length=1, max_length=200)
    parameter_preset_id: UUID | None = None
    skill_id: str | None = Field(
        default=None,
        min_length=3,
        max_length=TASK_SKILL_ID_MAX_LENGTH,
        pattern=TASK_SKILL_ID_PATTERN,
    )
    parameters: dict[str, Any] = Field(default_factory=dict)
    schedule_type: ScheduleType = ScheduleType.DAILY
    local_time: time
    timezone: str = Field(min_length=1, max_length=100)
    local_date: date | None = None
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_execution_target(self) -> "ScheduleCreate":
        if self.execution_type is ScheduleExecutionType.YINGDAO_APPLICATION:
            if self.application_id is None or self.skill_id is not None:
                raise ValueError("Yingdao schedules require only application_id")
        elif (
            self.skill_id is None
            or self.application_id is not None
            or self.parameter_preset_id is not None
        ):
            raise ValueError("Business Skill schedules require only skill_id")
        self.local_date, self.weekdays = validate_schedule_rule(
            self.schedule_type,
            self.local_date,
            self.weekdays,
        )
        return self

    @field_validator("shop_ids")
    @classmethod
    def reject_duplicate_shops(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("shop_ids must not contain duplicates")
        return value

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

    @field_validator("weekdays")
    @classmethod
    def validate_weekdays(cls, value: list[int]) -> list[int]:
        return normalize_weekdays(value)


class ScheduleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=200)
    target_device_id: UUID | None = None
    shop_ids: list[UUID] | None = Field(default=None, max_length=100)
    execution_type: ScheduleExecutionType | None = None
    application_id: str | None = Field(default=None, min_length=1, max_length=200)
    parameter_preset_id: UUID | None = None
    skill_id: str | None = Field(
        default=None,
        min_length=3,
        max_length=TASK_SKILL_ID_MAX_LENGTH,
        pattern=TASK_SKILL_ID_PATTERN,
    )
    parameters: dict[str, Any] | None = None
    schedule_type: ScheduleType | None = None
    local_time: time | None = None
    timezone: str | None = Field(default=None, min_length=1, max_length=100)
    local_date: date | None = None
    weekdays: list[int] | None = Field(default=None, max_length=7)
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
            if field_name not in {"local_date", "parameter_preset_id"} and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        if "application_id" in self.model_fields_set and "skill_id" in self.model_fields_set:
            raise ValueError("application_id and skill_id cannot be updated together")
        if self.execution_type is ScheduleExecutionType.YINGDAO_APPLICATION and (
            "skill_id" in self.model_fields_set
        ):
            raise ValueError("Yingdao schedules cannot select a Business Skill")
        if self.execution_type is ScheduleExecutionType.BUSINESS_SKILL and (
            "application_id" in self.model_fields_set
        ):
            raise ValueError("Business Skill schedules cannot select an application")
        return self

    @field_validator("shop_ids")
    @classmethod
    def reject_duplicate_shops(cls, value: list[UUID] | None) -> list[UUID] | None:
        if value is not None and len(value) != len(set(value)):
            raise ValueError("shop_ids must not contain duplicates")
        return value

    @field_validator("weekdays")
    @classmethod
    def validate_weekdays(cls, value: list[int] | None) -> list[int] | None:
        return normalize_weekdays(value) if value is not None else None


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
    shop_ids: list[UUID]
    device_display_name: str
    execution_type: ScheduleExecutionType
    skill_id: str
    execution_display_name: str
    schedule_type: ScheduleType
    local_time: time
    timezone: str
    local_date: date | None = None
    weekdays: list[int] = Field(default_factory=list)
    next_run_at: datetime | None
    latest_run: ScheduleRunRead | None
    created_at: datetime
    updated_at: datetime


class ScheduleRead(ScheduleListItemRead):
    application_id: str | None
    parameter_preset_id: UUID | None = None
    parameters: dict[str, Any]


class ScheduleTriggerSummary(BaseModel):
    run_id: UUID
    schedule_id: UUID
    scheduled_for: datetime
    trigger_result: ScheduleRunTriggerResult
    task_id: UUID | None
