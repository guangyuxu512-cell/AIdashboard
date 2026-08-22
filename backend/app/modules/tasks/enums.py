from enum import StrEnum


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    LOST = "lost"


class TaskSkillId(StrEnum):
    SYSTEM_ECHO = "system.echo"
    SYSTEM_SLEEP = "system.sleep"
    YINGDAO_TEST = "yingdao.test"
    YINGDAO_DISCOVER = "yingdao.discover"


class TaskEventType(StrEnum):
    STATUS = "status"
    LOG = "log"
    PROGRESS = "progress"
    COMPLETED = "completed"
    FAILED = "failed"
