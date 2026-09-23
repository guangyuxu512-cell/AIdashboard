from __future__ import annotations

from datetime import UTC, datetime, time

from app.core.config import Settings
from app.modules.operating_dashboard import scheduler


class _SessionContext:
    def __enter__(self) -> object:
        return object()

    def __exit__(self, *_: object) -> None:
        return None


def _settings(**values: object) -> Settings:
    defaults: dict[str, object] = {
        "operating_dashboard_collection_execution_enabled": True,
        "operating_dashboard_daily_collection_enabled": True,
        "operating_dashboard_daily_collection_local_time": time(hour=9),
    }
    return Settings(_env_file=None, **(defaults | values))


def test_daily_scheduler_uses_shanghai_nine_and_yesterday_gap_plan(
    monkeypatch,
) -> None:
    calls: list[dict[str, object]] = []

    class Service:
        def __init__(self, session: object, *, settings: Settings) -> None:
            del session, settings

        def enqueue_daily_collection(
            self,
            *,
            business_date: object,
            now: object,
        ) -> None:
            calls.append({"business_date": business_date, "now": now})

    monkeypatch.setattr(scheduler, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        scheduler,
        "get_session_factory",
        lambda: lambda: _SessionContext(),
    )
    monkeypatch.setattr(scheduler, "OperatingDashboardService", Service)

    assert scheduler.enqueue_due_daily_operating_collection_once(
        now=datetime(2026, 9, 23, 0, 59, tzinfo=UTC),
    ) is False
    assert calls == []

    assert scheduler.enqueue_due_daily_operating_collection_once(
        now=datetime(2026, 9, 23, 1, 0, tzinfo=UTC),
    ) is True
    assert calls == [
        {
            "business_date": datetime(2026, 9, 22, tzinfo=UTC).date(),
            "now": datetime(2026, 9, 23, 1, 0, tzinfo=UTC),
        },
    ]


def test_automatic_scheduler_helpers_do_nothing_when_execution_is_disabled(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        scheduler,
        "get_settings",
        lambda: _settings(operating_dashboard_collection_execution_enabled=False),
    )
    monkeypatch.setattr(
        scheduler,
        "get_session_factory",
        lambda: (_ for _ in ()).throw(AssertionError("must not open a session")),
    )

    assert scheduler.enqueue_due_daily_operating_collection_once() is False
    assert scheduler.recover_operating_data_collections_on_startup_once() is False


def test_startup_recovery_uses_the_existing_service_only_after_both_switches_enable(
    monkeypatch,
) -> None:
    calls: list[object] = []

    class Service:
        def __init__(self, session: object, *, settings: Settings) -> None:
            del session, settings

        def recover_after_backend_startup(self, *, now: object) -> None:
            calls.append(now)

    now = datetime(2026, 9, 23, 1, 0, tzinfo=UTC)
    monkeypatch.setattr(scheduler, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        scheduler,
        "get_session_factory",
        lambda: lambda: _SessionContext(),
    )
    monkeypatch.setattr(scheduler, "OperatingDashboardService", Service)

    assert scheduler.recover_operating_data_collections_on_startup_once(now=now) is True
    assert calls == [now]
