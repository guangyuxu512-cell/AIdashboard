from enum import StrEnum


TASK_SKILL_ID_MAX_LENGTH = 200
TASK_SKILL_ID_PATTERN = r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$"


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    LOST = "lost"


TERMINAL_TASK_STATUSES = (
    TaskStatus.SUCCESS,
    TaskStatus.FAILED,
    TaskStatus.LOST,
)
TERMINAL_TASK_STATUS_VALUES = tuple(status.value for status in TERMINAL_TASK_STATUSES)


class TaskSkillId(StrEnum):
    SYSTEM_ECHO = "system.echo"
    SYSTEM_SLEEP = "system.sleep"
    YINGDAO_TEST = "yingdao.test"
    YINGDAO_DISCOVER = "yingdao.discover"
    YINGDAO_APP_RUN = "yingdao.app.run"


class TaskEventType(StrEnum):
    STATUS = "status"
    LOG = "log"
    PROGRESS = "progress"
    COMPLETED = "completed"
    FAILED = "failed"
