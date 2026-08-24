import asyncio
from types import SimpleNamespace

import pytest

from app.modules.schedules import scheduler


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
