"""Real assigned PostgreSQL and synthetic platform; no live request proof."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.product_selection.models import ProductSelectionObservation as Observation
from app.modules.product_selection.run_service import SelectionRunService
from app.platforms.douyin.product_selection import CompassSelectionBusinessError
from app.platforms.exceptions import PlatformSignerFailedError
from tests.integration.test_postgresql_product_selection import selection_context, _product, _api_client
from tests.integration.test_postgresql_selection_runs import _input, _get, _executor, SETTINGS
from tests.integration.test_postgresql_selection_windows import _submit, WindowPlatform
from tests.integration.test_postgresql_selection_strategies import _save

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("products", [(), (_product(rank=1),)])
def test_realtime_success_and_empty_never_probe_a_backup(selection_context, products):
    context = selection_context
    strategy = _save(context, conditions={"version": 1, "request": _input(context, period="realtime").original().model_dump(mode="json", exclude={"shop_id"})})
    receipt = _submit(context, _input(context, period="realtime", rank_from=1, rank_to=10, strategy_id=strategy.strategy_id, strategy_version=strategy.version))
    request = receipt.execution.request_conditions
    platform = WindowPlatform(request, {("primary", 1): products})
    _executor(context, platform).execute_available()
    run = _get(context, receipt)
    assert run.status == "succeeded" and run.saved_count == len(products)
    assert run.result_count == len(products) and platform.rank_calls == [("primary", 1)]
    assert run.request_conditions.date_outcome.state == "primary"
    assert not hasattr(run.request_conditions.date_plan, "backup_scope")
    with _api_client(context) as client:
        headers = {"X-Team-ID": str(context[1][0])}
        page = client.get("/api/v1/product-selection/candidates", headers=headers).json()
        assert page["total"] == len(products)
        if products:
            row = page["items"][0]
            assert row["period_begin"] == row["period_end"] == str(request.scope.period_begin)
            assert row["source_context"]["date_selection"]["policy"] == "shanghai_realtime_today"
            assert row["source_context"]["date_selection"]["backup_begin"] is None
            assert client.get(f'/api/v1/product-selection/observations/{row["observation_id"]}', headers=headers).status_code == 200
    assert platform.rank_calls == [("primary", 1)]


@pytest.mark.parametrize("failure", [
    CompassSelectionBusinessError(details={"platform_code": 621000704}),
    CompassSelectionBusinessError(details={"platform_code": "621000704"}),
    PlatformSignerFailedError(),
])
def test_realtime_failures_do_not_inherit_seven_day_business_probe(selection_context, failure):
    context = selection_context
    receipt = _submit(context, _input(context, period="realtime"))
    platform = WindowPlatform(receipt.execution.request_conditions, {("primary", 1): failure})
    _executor(context, platform).execute_available()
    run = _get(context, receipt)
    assert run.status == "failed" and run.result_count is None
    assert run.request_conditions.date_outcome is None and platform.rank_calls == [("primary", 1)]
    with Session(context[0]) as session:
        assert session.scalar(select(func.count()).select_from(Observation).where(Observation.last_run_id == run.run_id)) == 0


def test_realtime_cross_day_replay_keeps_first_day_and_new_key_uses_new_day(selection_context):
    context = selection_context
    at = datetime(2026, 12, 31, 15, 59, tzinfo=UTC)
    command = _input(context, period="realtime")
    first = _submit(context, command, now=at)
    with Session(context[0]) as session:
        service = SelectionRunService(session, settings=SETTINGS, category_reader=lambda *_: pytest.fail("Replay must not read categories"))
        replay = service.submit(context[4][0], command, now=at + timedelta(minutes=2))
        assert replay.receipt_id == first.receipt_id
        assert replay.execution.request_conditions == first.execution.request_conditions
    next_run = _submit(context, _input(context, period="realtime"), now=at + timedelta(minutes=2))
    assert not next_run.reused
    assert next_run.execution.request_conditions.scope.period_begin != first.execution.request_conditions.scope.period_begin
