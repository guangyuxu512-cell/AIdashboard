from enum import StrEnum


class WorkerConnectionStatus(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"


class ProviderCode(StrEnum):
    YINGDAO = "yingdao"


class SkillClassification(StrEnum):
    INTERNAL = "internal"
    BUSINESS = "business"


LEGACY_INTERNAL_SKILL_IDS = frozenset(
    {
        "system.echo",
        "system.sleep",
        "yingdao.app.run",
        "yingdao.test",
        "yingdao.discover",
    },
)
