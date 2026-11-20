import asyncio
from types import SimpleNamespace

import pytest

from app.modules.schedules import scheduler


def test_paused_scheduler_does_not_access_database(monkeypatch) -> None:
    monkeypatch.setattr(
        scheduler, "get_settings",
        lambda: SimpleNamespace(worker_schedule_execution_enabled=False),
    )
    def unexpected_database_access():
        raise AssertionError("paused scheduler must not scan for tasks")
    monkeypatch.setattr(scheduler, "get_session_factory", unexpected_database_access)
    assert scheduler.trigger_due_schedules_once() == 0


def test_scheduler_loop_recovers_after_a_scan_error(monkeypatch, caplog) -> None:
    calls = 0

    async def fake_to_thread(function, **kwargs):
        nonlocal calls
        del function, kwargs
        calls += 1
        if calls == 1:
            raise RuntimeError("transient scan failure")
        raise asyncio.CancelledError

    monkeypatch.setattr(
        scheduler,
        "get_settings",
        lambda: SimpleNamespace(schedule_scan_interval_seconds=0),
    )
    monkeypatch.setattr(scheduler.asyncio, "to_thread", fake_to_thread)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(scheduler.trigger_due_schedules_forever())

    assert calls == 2
    assert "Schedule trigger scan failed" in caplog.text


def test_scheduler_loop_honors_normal_task_cancellation(monkeypatch) -> None:
    scans_started = 0
    first_scan_finished = asyncio.Event()

    async def fake_to_thread(function, **kwargs):
        nonlocal scans_started
        del function, kwargs
        scans_started += 1
        first_scan_finished.set()
        return 0

    monkeypatch.setattr(
        scheduler,
        "get_settings",
        lambda: SimpleNamespace(schedule_scan_interval_seconds=60),
    )
    monkeypatch.setattr(scheduler.asyncio, "to_thread", fake_to_thread)

    async def run_and_cancel() -> None:
        task = asyncio.create_task(scheduler.trigger_due_schedules_forever())
        await first_scan_finished.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run_and_cancel())
    assert scans_started == 1


def test_worker_scheduler_can_be_enabled_without_reviving_retired_collection(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("BACKEND_WORKER_SCHEDULE_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("BACKEND_PRODUCT_DATA_COLLECTION_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("BACKEND_PRODUCT_SELECTION_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("BACKEND_PRODUCT_SELECTION_SCHEDULE_ENABLED", "true")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.worker_schedule_execution_enabled is True
        assert settings.product_data_collection_execution_enabled is False
        assert not hasattr(settings, 'product_selection_execution_enabled')
        assert not hasattr(settings, 'product_selection_schedule_enabled')
    finally:
        get_settings.cache_clear()
