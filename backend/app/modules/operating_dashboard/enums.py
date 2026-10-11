from enum import StrEnum

SESSION_RESTORE_DEDUPE_PREFIX = "session-restored:"


class OperatingCollectionJobKind(StrEnum):
    INITIAL_BACKFILL = "initial_backfill"
    REENABLE_BACKFILL = "reenable_backfill"
    MANUAL_REFRESH = "manual_refresh"
    DAILY = "daily"
    RETRY = "retry"


class OperatingCollectionJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL_FAILED = "partial_failed"
    FAILED = "failed"


class OperatingCollectionItemStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    PAUSED_REAUTHORIZATION = "paused_reauthorization"


class OperatingCollectionFailureStage(StrEnum):
    QUEUED = "queued"
    SESSION_PREPARATION = "session_preparation"
    SIGNING = "signing"
    PLATFORM_RESPONSE = "platform_response"
    RESPONSE_PARSE = "response_parse"
    SESSION_PERSISTENCE = "session_persistence"
    EXECUTION = "execution"


ACTIVE_COLLECTION_ITEM_STATUSES = (
    OperatingCollectionItemStatus.PENDING,
    OperatingCollectionItemStatus.RUNNING,
    OperatingCollectionItemStatus.PAUSED_REAUTHORIZATION,
)

TERMINAL_COLLECTION_ITEM_STATUSES = (
    OperatingCollectionItemStatus.SUCCEEDED,
    OperatingCollectionItemStatus.FAILED,
    OperatingCollectionItemStatus.SKIPPED,
)
