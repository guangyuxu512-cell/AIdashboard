from datetime import UTC, datetime, timedelta

from app.core.config import Settings
from app.modules.tasks.repository import TaskEventPurgeBatch
from app.modules.tasks.service import TaskService
from tests.support import FakeSession


class FakeRetentionRepository:
    def __init__(self, batches: list[TaskEventPurgeBatch]) -> None:
        self.batches = iter(batches)
        self.arguments: list[dict[str, object]] = []

    def purge_expired_event_batch(
        self,
        **kwargs: object,
    ) -> TaskEventPurgeBatch:
        self.arguments.append(kwargs)
        return next(
            self.batches,
            TaskEventPurgeBatch(tasks_purged=0, events_deleted=0),
        )


def test_retention_uses_configured_cutoff_and_commits_short_batches() -> None:
    now = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
    session = FakeSession()
    repository = FakeRetentionRepository(
        [
            TaskEventPurgeBatch(tasks_purged=2, events_deleted=12),
            TaskEventPurgeBatch(tasks_purged=1, events_deleted=3),
            TaskEventPurgeBatch(tasks_purged=0, events_deleted=0),
        ],
    )
    service = TaskService(
        session,  # type: ignore[arg-type]
        repository,  # type: ignore[arg-type]
        Settings(
            task_event_retention_days=90,
            task_event_retention_batch_size=25,
        ),
    )

    result = service.purge_expired_events(now=now)

    assert result.cutoff == now - timedelta(days=90)
    assert result.tasks_purged == 3
    assert result.events_deleted == 15
    assert session.commits == 2
    assert session.rollbacks == 1
    assert len(repository.arguments) == 3
    assert all(item["batch_size"] == 25 for item in repository.arguments)
    assert all(item["purged_at"] == now for item in repository.arguments)


def test_repeated_empty_cleanup_is_idempotent() -> None:
    session = FakeSession()
    repository = FakeRetentionRepository([])
    service = TaskService(
        session,  # type: ignore[arg-type]
        repository,  # type: ignore[arg-type]
    )

    first = service.purge_expired_events()
    second = service.purge_expired_events()

    assert first.tasks_purged == second.tasks_purged == 0
    assert first.events_deleted == second.events_deleted == 0
    assert session.commits == 0
    assert session.rollbacks == 2
