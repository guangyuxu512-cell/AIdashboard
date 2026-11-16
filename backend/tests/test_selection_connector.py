"""Selection domain remains testable while platform execution is paused."""

import asyncio
from threading import Barrier
from uuid import uuid4

import pytest
from app.core.config import Settings, get_settings
from app.modules.product_selection.exceptions import SelectionExecutionDisabledError
from app.modules.product_selection.platform_io import SelectionUnavailableIO


def test_disabled_consumer_has_no_database_or_platform_io(monkeypatch):
    from app.modules.product_selection import run_executor
    monkeypatch.setattr(run_executor, "build_selection_run_executor", lambda *_: pytest.fail("No executor/DB/platform must be started"))
    monkeypatch.setattr(run_executor, "get_settings", lambda: Settings(product_selection_execution_enabled=False))
    asyncio.run(run_executor.execute_selection_runs_forever())


@pytest.mark.parametrize("capacity", [1, 3])
def test_enabled_but_unconfirmed_consumer_only_recovers_expired_leases(monkeypatch, capacity):
    from app.modules.product_selection import run_executor
    recovered = []
    # The mocked idle cancellation must not abort sibling workers before their first pass.
    first_pass = Barrier(capacity)
    class Executor:
        def recover_only(self):
            recovered.append(True)
            first_pass.wait()
        def execute_available(self):
            pytest.fail("Unknown mapping cannot claim a run or issue HTTP")

    async def stop(_):
        raise asyncio.CancelledError()

    monkeypatch.setattr(run_executor, "get_settings", lambda: Settings(product_selection_execution_enabled=True, product_selection_concurrency=capacity))
    monkeypatch.setattr(run_executor, "selection_request_mapping_available", lambda: False)
    monkeypatch.setattr(run_executor, "build_selection_run_executor", lambda *_: Executor())
    monkeypatch.setattr(run_executor.asyncio, "sleep", stop)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_executor.execute_selection_runs_forever())
    assert recovered == [True] * capacity


@pytest.mark.parametrize("capacity", [1, 3])
def test_enabled_confirmed_consumer_uses_existing_executor(monkeypatch, capacity):
    from app.modules.product_selection import run_executor
    executed = []
    # The mocked idle cancellation must not abort sibling workers before their first pass.
    first_pass = Barrier(capacity)
    class Executor:
        def execute_available(self):
            executed.append(True)
            first_pass.wait()
            return 0
    async def stop(_):
        raise asyncio.CancelledError()
    monkeypatch.setattr(run_executor, "get_settings", lambda: Settings(product_selection_execution_enabled=True, product_selection_concurrency=capacity))
    monkeypatch.setattr(run_executor, "build_selection_run_executor", lambda *_: Executor())
    monkeypatch.setattr(run_executor.asyncio, "sleep", stop)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_executor.execute_selection_runs_forever())
    assert executed == [True] * capacity




def test_stale_selection_flags_cannot_reenable_server_execution(monkeypatch):
    monkeypatch.setenv("BACKEND_PRODUCT_SELECTION_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("BACKEND_PRODUCT_SELECTION_SCHEDULE_ENABLED", "true")
    monkeypatch.setenv("BACKEND_OPERATING_DASHBOARD_COLLECTION_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("BACKEND_OPERATING_DASHBOARD_DAILY_COLLECTION_ENABLED", "true")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.product_selection_execution_enabled is False
        assert settings.product_selection_schedule_enabled is False
        assert settings.operating_dashboard_collection_execution_enabled is False
        assert settings.operating_dashboard_daily_collection_enabled is False
    finally:
        get_settings.cache_clear()


def test_unavailable_selection_adapter_never_reads_session_or_requests_platform():
    adapter = SelectionUnavailableIO()
    for method, args in ((adapter.session_context, (uuid4(),)), (adapter.categories, (None,)),
                         (adapter.rank, (None, None, 1)), (adapter.basic_info, (None, "1"))):
        with pytest.raises(SelectionExecutionDisabledError):
            method(*args)
