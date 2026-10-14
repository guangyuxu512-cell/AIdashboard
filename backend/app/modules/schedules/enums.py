from enum import StrEnum


class ScheduleType(StrEnum):
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"


class ScheduleExecutionType(StrEnum):
    YINGDAO_APPLICATION = "yingdao_application"
    BUSINESS_SKILL = "business_skill"


class ScheduleRunTriggerResult(StrEnum):
    TASK_CREATED = "task_created"
    BLOCKED = "blocked"
    SELECTION_RUN = "selection_run"
