from datetime import UTC, datetime
from uuid import uuid4


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def flush(self) -> None:
        pass

    def refresh(self, entity: object) -> None:
        for identifier in (
            "user_id",
            "shop_id",
            "device_id",
            "credential_id",
            "session_id",
            "task_id",
        ):
            if hasattr(entity, identifier) and getattr(entity, identifier) is None:
                setattr(entity, identifier, uuid4())
        now = datetime.now(UTC)
        if hasattr(entity, "created_at") and getattr(entity, "created_at") is None:
            setattr(entity, "created_at", now)
        if hasattr(entity, "updated_at"):
            setattr(entity, "updated_at", now)
