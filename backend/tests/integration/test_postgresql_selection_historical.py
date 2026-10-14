"""Assigned Feature PostgreSQL, synthetic platform, no live request evidence."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.modules.product_selection.exceptions import SelectionRunLeaseLostError
from app.modules.product_selection.run_service import SelectionRunService
from app.platforms.douyin.product_selection import CompassSelectionBusinessError
from app.platforms.exceptions import PlatformSignerFailedError, PlatformRequestTimeoutError
from tests.integration.test_postgresql_product_selection import selection_context, _product, _api_client
from tests.integration.test_postgresql_selection_runs import _input, _get, _executor, _claim, SETTINGS
from tests.integration.test_postgresql_selection_windows import _submit, WindowPlatform
from tests.integration.test_postgresql_selection_strategies import _save

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("period,policy", [("1d", "shanghai_1d_yesterday"), ("30d", "shanghai_30d_complete_days")])
@pytest.mark.parametrize("products", [(), (_product(rank=1),)])
def test_historical_saved_strategy_success_empty_and_database_provenance(selection_context, period, policy, products):
    context = selection_context
    original = _input(context, period=period, rank_from=1, rank_to=10)
    strategy = _save(context, conditions={"version": 1, "request": original.original().model_dump(mode="json", exclude={"shop_id"})})
    receipt = _submit(context, _input(context, period=period, rank_from=1, rank_to=10, strategy_id=strategy.strategy_id, strategy_version=strategy.version))
    platform = WindowPlatform(receipt.execution.request_conditions, {("primary", 1): products})
    _executor(context, platform).execute_available()
    run = _get(context, receipt)
    assert run.request_conditions.version == 5 and run.status == "succeeded"
    assert run.result_count == run.saved_count == len(products)
    assert platform.rank_calls == [("primary", 1)]
    assert run.request_conditions.date_outcome.state == "primary"
    with _api_client(context) as client:
        page = client.get("/api/v1/product-selection/candidates", headers={"X-Team-ID": str(context[1][0])}).json()
        assert page["total"] == len(products)
        if products:
            row = page["items"][0]
            assert row["period_begin"] == str(run.request_conditions.scope.period_begin)
            assert row["period_end"] == str(run.request_conditions.scope.period_end)
            assert row["source_context"]["date_selection"]["policy"] == policy
            assert row["source_context"]["date_selection"]["backup_begin"] is None
            assert client.get(f'/api/v1/product-selection/observations/{row["observation_id"]}', headers={"X-Team-ID": str(context[1][0])}).status_code == 200
    assert platform.rank_calls == [("primary", 1)]


@pytest.mark.parametrize("period", ["1d", "30d"])
@pytest.mark.parametrize("error", [CompassSelectionBusinessError(details={"platform_code": 621000704}), CompassSelectionBusinessError(details={"platform_code": "621000704"}), PlatformSignerFailedError(), PlatformRequestTimeoutError()])
def test_historical_failure_never_probes_another_window(selection_context, period, error):
    receipt = _submit(selection_context, _input(selection_context, period=period))
    platform = WindowPlatform(receipt.execution.request_conditions, {("primary", 1): error})
    _executor(selection_context, platform).execute_available()
    run = _get(selection_context, receipt)
    assert run.status == "failed" and run.result_count is None and run.saved_count == 0
    assert run.request_conditions.date_outcome is None
    assert platform.rank_calls == [("primary", 1)]


@pytest.mark.parametrize("period", ["1d", "30d"])
def test_history_replay_after_midnight_keeps_frozen_dates_and_rejects_backup(selection_context, period):
    context = selection_context
    at = datetime(2026, 12, 31, 15, 59, tzinfo=UTC)
    command = _input(context, period=period)
    first = _submit(context, command, now=at)
    with Session(context[0]) as session:
        replay = SelectionRunService(session, settings=SETTINGS, category_reader=lambda *_: pytest.fail("Replay cannot read categories")).submit(context[4][0], command, now=at + timedelta(minutes=2))
        assert replay.receipt_id == first.receipt_id and replay.execution.request_conditions == first.execution.request_conditions
    second = _submit(context, _input(context, period=period), now=at + timedelta(minutes=2))
    assert not second.reused and second.execution.request_conditions.scope != first.execution.request_conditions.scope
    claim = _claim(context)
    with Session(context[0]) as session:
        with pytest.raises(SelectionRunLeaseLostError):
            SelectionRunService(session).choose_window(claim, "fallback_checking")
