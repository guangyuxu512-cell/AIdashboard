from enum import StrEnum


class ScheduleType(StrEnum):
    DAILY = "daily"


class ScheduleRunTriggerResult(StrEnum):
    TASK_CREATED = "task_created"
    BLOCKED = "blocked"
