from enum import StrEnum


class ScheduleType(StrEnum):
    DAILY = "daily"


class ScheduleExecutionType(StrEnum):
    YINGDAO_APPLICATION = "yingdao_application"
    BUSINESS_SKILL = "business_skill"


class ScheduleRunTriggerResult(StrEnum):
    TASK_CREATED = "task_created"
    BLOCKED = "blocked"
