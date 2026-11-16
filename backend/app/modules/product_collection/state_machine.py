"""Pure state rules shared by services and database constraint tests."""

from enum import StrEnum


class RequestState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PARTIAL = "partial"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class ItemState(StrEnum):
    PENDING_DISPATCH = "pending_dispatch"
    DISPATCHING = "dispatching"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    RECEIVED = "received"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class DispatchState(StrEnum):
    PENDING_DELIVERY = "pending_delivery"
    DELIVERING = "delivering"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    COMPLETED = "completed"
    DELIVERY_FAILED = "delivery_failed"
    EXECUTION_FAILED = "execution_failed"
    CANCELED = "canceled"


class AttemptState(StrEnum):
    REGISTERED = "registered"
    RUNNING = "running"
    RECEIVED = "received"
    PROCESSING = "processing"
    PERSISTED = "persisted"
    FAILED = "failed"
    SUPERSEDED = "superseded"
    CANCELED = "canceled"


class UploadReceiptState(StrEnum):
    RECEIVED = "received"
    PROCESSING = "processing"
    PERSISTED = "persisted"
    FAILED = "failed"
    SUPERSEDED = "superseded"


class PersistOutcome(StrEnum):
    APPLIED = "applied"
    NOT_APPLIED = "not_applied"
    SUPERSEDED = "superseded"


class SettlementState(StrEnum):
    PENDING = "pending"
    DELIVERING = "delivering"
    SETTLED = "settled"
    FAILED = "failed"


REQUEST_TERMINAL = frozenset(
    {RequestState.PARTIAL, RequestState.SUCCEEDED, RequestState.FAILED, RequestState.CANCELED},
)
ITEM_TERMINAL = frozenset({ItemState.SUCCEEDED, ItemState.FAILED, ItemState.CANCELED})
DISPATCH_TERMINAL = frozenset(
    {
        DispatchState.COMPLETED,
        DispatchState.DELIVERY_FAILED,
        DispatchState.EXECUTION_FAILED,
        DispatchState.CANCELED,
    },
)
DISPATCH_ACTIVE = frozenset(
    {
        DispatchState.PENDING_DELIVERY,
        DispatchState.DELIVERING,
        DispatchState.DISPATCHED,
        DispatchState.RUNNING,
    },
)
ATTEMPT_TERMINAL = frozenset(
    {AttemptState.PERSISTED, AttemptState.FAILED, AttemptState.SUPERSEDED, AttemptState.CANCELED},
)
ATTEMPT_ACTIVE = frozenset(
    {AttemptState.REGISTERED, AttemptState.RUNNING, AttemptState.RECEIVED, AttemptState.PROCESSING},
)
UPLOAD_TERMINAL = frozenset(
    {UploadReceiptState.PERSISTED, UploadReceiptState.FAILED, UploadReceiptState.SUPERSEDED},
)


REQUEST_TRANSITIONS = {
    RequestState.PENDING: frozenset({RequestState.RUNNING, RequestState.FAILED, RequestState.CANCELED}),
    RequestState.RUNNING: REQUEST_TERMINAL,
}
ITEM_TRANSITIONS = {
    ItemState.PENDING_DISPATCH: frozenset(
        {ItemState.DISPATCHING, ItemState.FAILED, ItemState.CANCELED},
    ),
    ItemState.DISPATCHING: frozenset(
        {ItemState.DISPATCHED, ItemState.FAILED, ItemState.CANCELED},
    ),
    ItemState.DISPATCHED: frozenset({ItemState.RUNNING, ItemState.FAILED, ItemState.CANCELED}),
    ItemState.RUNNING: frozenset({ItemState.RECEIVED, ItemState.FAILED, ItemState.CANCELED}),
    ItemState.RECEIVED: frozenset({ItemState.PROCESSING, ItemState.FAILED, ItemState.CANCELED}),
    ItemState.PROCESSING: ITEM_TERMINAL,
}
DISPATCH_TRANSITIONS = {
    DispatchState.PENDING_DELIVERY: frozenset(
        {DispatchState.DELIVERING, DispatchState.DELIVERY_FAILED, DispatchState.CANCELED},
    ),
    DispatchState.DELIVERING: frozenset(
        {DispatchState.DISPATCHED, DispatchState.DELIVERY_FAILED, DispatchState.CANCELED},
    ),
    DispatchState.DISPATCHED: frozenset(
        {DispatchState.RUNNING, DispatchState.EXECUTION_FAILED, DispatchState.CANCELED},
    ),
    DispatchState.RUNNING: frozenset(
        {DispatchState.COMPLETED, DispatchState.EXECUTION_FAILED, DispatchState.CANCELED},
    ),
}
ATTEMPT_TRANSITIONS = {
    AttemptState.REGISTERED: frozenset(
        {AttemptState.RUNNING, AttemptState.FAILED, AttemptState.SUPERSEDED, AttemptState.CANCELED},
    ),
    AttemptState.RUNNING: frozenset(
        {AttemptState.RECEIVED, AttemptState.FAILED, AttemptState.SUPERSEDED, AttemptState.CANCELED},
    ),
    AttemptState.RECEIVED: frozenset(
        {AttemptState.PROCESSING, AttemptState.FAILED, AttemptState.SUPERSEDED, AttemptState.CANCELED},
    ),
    AttemptState.PROCESSING: ATTEMPT_TERMINAL,
}
UPLOAD_TRANSITIONS = {
    UploadReceiptState.RECEIVED: frozenset(
        {UploadReceiptState.PROCESSING, UploadReceiptState.FAILED, UploadReceiptState.SUPERSEDED},
    ),
    UploadReceiptState.PROCESSING: UPLOAD_TERMINAL,
}
SETTLEMENT_TRANSITIONS = {
    SettlementState.PENDING: frozenset({SettlementState.DELIVERING, SettlementState.FAILED}),
    SettlementState.DELIVERING: frozenset({SettlementState.SETTLED, SettlementState.FAILED}),
    SettlementState.FAILED: frozenset({SettlementState.DELIVERING}),
}


def can_transition(current: StrEnum, target: StrEnum) -> bool:
    maps = {
        RequestState: REQUEST_TRANSITIONS,
        ItemState: ITEM_TRANSITIONS,
        DispatchState: DISPATCH_TRANSITIONS,
        AttemptState: ATTEMPT_TRANSITIONS,
        UploadReceiptState: UPLOAD_TRANSITIONS,
        SettlementState: SETTLEMENT_TRANSITIONS,
    }
    if type(current) is not type(target):
        return False
    transitions = maps.get(type(current))
    return transitions is not None and target in transitions.get(current, frozenset())
