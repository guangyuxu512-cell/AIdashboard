from enum import StrEnum


class WorkerConnectionStatus(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"


class ProviderCode(StrEnum):
    YINGDAO = "yingdao"
