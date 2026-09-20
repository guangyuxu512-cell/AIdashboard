from datetime import UTC, datetime
from uuid import UUID, uuid4


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
            "team_id",
            "membership_id",
            "shop_id",
            "device_id",
            "credential_id",
            "session_id",
            "run_id",
            "task_id",
            "schedule_id",
        ):
            if hasattr(entity, identifier) and getattr(entity, identifier) is None:
                setattr(entity, identifier, uuid4())
                break
        now = datetime.now(UTC)
        if hasattr(entity, "created_at") and getattr(entity, "created_at") is None:
            setattr(entity, "created_at", now)
        if hasattr(entity, "updated_at"):
            setattr(entity, "updated_at", now)


class AllowExecutionResources:
    """Test double for task-focused tests that do not exercise Team grants."""

    def require_execution_resources(
        self,
        *,
        team_id: UUID,
        device_id: UUID,
        shop_ids: list[UUID],
    ) -> None:
        del team_id, device_id, shop_ids
