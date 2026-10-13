"""Assigned Feature PostgreSQL + synthetic platform. Never live-platform proof."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.modules.product_selection.exceptions import SelectionRunLeaseLostError, SelectionPriceRangeInvalidError
from app.modules.product_selection.run_contract import SelectionPrimaryBusinessError, SelectionRunReceipt
from app.modules.product_selection.run_service import SelectionRunService
from app.platforms.douyin.product_selection import CompassSelectionBusinessError, CompassRankPage
from app.platforms.exceptions import PlatformSignerFailedError, PlatformRequestTimeoutError
from tests.integration.test_postgresql_product_selection import selection_context, _product, _api_client
from tests.integration.test_postgresql_selection_runs import _input, _get, _executor, _claim, SETTINGS
from tests.integration.test_postgresql_selection_windows import _submit, WindowPlatform, _category_tree
from tests.integration.test_postgresql_selection_strategies import _save

pytestmark = pytest.mark.integration


def _priced(context, **changes):
    return _input(context, **({"price_mode": "custom", "price_above": "20.00", "price_below": "100.0", "rank_from": 1, "rank_to": 10} | changes))


@pytest.mark.parametrize("period", ["realtime", "1d", "7d", "30d"])
def test_saved_custom_price_to_executor_database_query_and_repeat(selection_context, period):
    context = selection_context
    at = datetime(2026, 10, 13, 2, tzinfo=UTC)
    command = _priced(context, period=period)
    strategy = _save(context, conditions={"version": 1, "request": command.original().model_dump(mode="json", exclude={"shop_id"})})
    receipt = _submit(context, _priced(context, period=period, strategy_id=strategy.strategy_id, strategy_version=strategy.version), now=at)
    product = replace(_product(rank=1), price_band="¥39-¥115")
    platform = WindowPlatform(receipt.execution.request_conditions, {("primary", 1): (product,)})
    _executor(context, platform).execute_available()
    run = _get(context, receipt)
    assert run.status == "succeeded" and run.request_conditions.version == 6
    assert run.saved_count == 1 and run.supplemented_count == 1 and platform.rank_calls == [("primary", 1)]
    assert run.request_conditions.actual_scope().price_bin == "20-100"
    assert run.request_conditions.strategy.strategy_id == strategy.strategy_id
    with _api_client(context) as client:
        headers = {"X-Team-ID": str(context[1][0])}
        reread = client.get(f"/api/v1/product-selection/strategies/{strategy.strategy_id}", headers=headers).json()
        assert reread["conditions"]["request"]["price_above"] == "20.00"
        assert reread["conditions"]["request"]["price_below"] == "100.0"
        assert reread["latest_run"]["request_conditions"]["scope"]["price_bin"] == "20-100"
        first = client.get("/api/v1/product-selection/candidates", headers=headers).json()
        second = client.get("/api/v1/product-selection/candidates", headers=headers).json()
        assert first == second and first["total"] == 1
        row = first["items"][0]
        assert row["price_band"] == "¥39-¥115"  # no local whole-SKU filtering
        assert row["source_context"]["business"]["price_bin"] == "20-100"
        assert row["period_begin"] == str(run.request_conditions.scope.period_begin)
        assert client.get(f'/api/v1/product-selection/observations/{row["observation_id"]}', headers=headers).json()["price_band"] == "¥39-¥115"
    repeated = _submit(context, _priced(context, period=period), now=at)
    platform2 = WindowPlatform(repeated.execution.request_conditions, {("primary", 1): (product,)})
    _executor(context, platform2).execute_available()
    with _api_client(context) as client:
        page = client.get("/api/v1/product-selection/candidates", headers={"X-Team-ID": str(context[1][0])}).json()
        assert page["total"] == 1 and page["items"][0]["candidate_id"] == row["candidate_id"]
    assert platform.rank_calls == [("primary", 1)]


@pytest.mark.parametrize("backup,state,count", [((_product(rank=1),), "backup", 1), ((), "both_empty", 0), (PlatformRequestTimeoutError(), "fallback_failed", None)])
def test_custom_seven_day_only_legal_empty_may_probe_once(selection_context, backup, state, count):
    receipt = _submit(selection_context, _priced(selection_context))
    platform = WindowPlatform(receipt.execution.request_conditions, {("primary", 1): (), ("backup", 1): backup})
    _executor(selection_context, platform).execute_available()
    run = _get(selection_context, receipt)
    assert run.request_conditions.date_outcome.state == state
    assert run.request_conditions.date_outcome.fallback_reason == "primary_success_empty"
    assert run.result_count == count and platform.rank_calls == [("primary", 1), ("backup", 1)]
    assert run.request_conditions.date_plan.backup_scope.price_bin == "20-100"
    if count:
        with _api_client(selection_context) as client:
            row = client.get("/api/v1/product-selection/candidates", headers={"X-Team-ID": str(selection_context[1][0])}).json()["items"][0]
            assert row["source_context"]["business"]["begin_date"] == run.request_conditions.date_plan.backup_scope.begin_date
            assert row["source_context"]["date_selection"]["actual_window"] == "backup"


@pytest.mark.parametrize("error", [CompassSelectionBusinessError(details={"platform_code": 621000704}), CompassSelectionBusinessError(details={"platform_code": "621000704"}), PlatformSignerFailedError(), PlatformRequestTimeoutError()])
def test_custom_error_never_probes_even_for_seven_day(selection_context, error):
    receipt = _submit(selection_context, _priced(selection_context))
    platform = WindowPlatform(receipt.execution.request_conditions, {("primary", 1): error})
    _executor(selection_context, platform).execute_available()
    run = _get(selection_context, receipt)
    assert run.status == "failed" and run.result_count is None and run.saved_count == 0
    assert platform.rank_calls == [("primary", 1)] and run.request_conditions.date_outcome is None


def test_custom_same_key_replays_frozen_price_after_midnight_and_fences_business_probe(selection_context):
    at = datetime(2026, 12, 31, 15, 59, tzinfo=UTC)
    command = _priced(selection_context)
    first = _submit(selection_context, command, now=at)
    with Session(selection_context[0]) as session:
        replay = SelectionRunService(session, settings=SETTINGS, category_reader=lambda *_: pytest.fail("Replay is DB-only")).submit(selection_context[4][0], command, now=at + timedelta(minutes=2))
    assert replay.receipt_id == first.receipt_id and replay.execution.request_conditions == first.execution.request_conditions
    claim = _claim(selection_context)
    with Session(selection_context[0]) as session:
        with pytest.raises(SelectionRunLeaseLostError):
            SelectionRunService(session).choose_window(claim, "fallback_checking", fallback_reason="primary_business_rejection_probe", primary_error=SelectionPrimaryBusinessError(error_code="DOUYIN_SELECTION_BUSINESS_REJECTED", error_stage="platform_business", platform_business_code=621000704))


def test_single_sided_price_rejected_before_categories_or_run(selection_context):
    with Session(selection_context[0]) as session:
        with pytest.raises(SelectionPriceRangeInvalidError):
            SelectionRunService(session, settings=SETTINGS, category_reader=lambda *_: pytest.fail("Invalid bounds cannot load categories")).submit(selection_context[4][0], _priced(selection_context, price_below=None))


def test_formal_price_post_replay_and_connector_query(selection_context):
    from app.modules.product_selection.api import get_selection_run_service
    from app.modules.product_selection.platform_io import SelectionStoredSessionIO
    context, queries, reads = selection_context, [], []
    command = _priced(context, price_below="40.00")
    def dependency():
        with Session(context[0]) as session:
            def categories(actor, shop_id):
                assert not session.in_transaction()
                reads.append(shop_id)
                return _category_tree(shop_id)
            yield SelectionRunService(session, settings=SETTINGS, category_reader=categories)
    with _api_client(context) as client:
        client.app.dependency_overrides[get_selection_run_service] = dependency
        headers = {"X-Team-ID": str(context[1][0])}
        bad = client.post("/api/v1/product-selection/runs", headers=headers, json=command.model_dump(mode="json") | {"price_below": None})
        assert bad.status_code == 422 and bad.json()["code"] == "PRODUCT_SELECTION_PRICE_RANGE_INVALID"
        assert reads == []
        response = client.post("/api/v1/product-selection/runs", headers=headers, json=command.model_dump(mode="json"))
        assert response.status_code == 202
        assert client.post("/api/v1/product-selection/runs", headers=headers, json=command.model_dump(mode="json")).json() == response.json()
        receipt = SelectionRunReceipt.model_validate(response.json())
    assert reads == [command.shop_id]
    class Connector:
        def rank(self, auth_context, query):
            queries.append(query)
            return CompassRankPage((_product(rank=1),), 1, 10, 1)
    class Platform(WindowPlatform):
        def rank(self, auth_context, request, page_no):
            return SelectionStoredSessionIO(lambda: None, connector=Connector()).rank(auth_context, request, page_no)
    _executor(context, Platform(receipt.execution.request_conditions, {})).execute_available()
    run = _get(context, receipt)
    actual = run.request_conditions.actual_scope()
    assert queries == [{"page_no": "1", "page_size": "10", **actual.model_dump()}]
    assert queries[0]["price_bin"] == "20-40" and queries[0]["brand_type"] == "-1"
    assert all(type(value) is str for value in queries[0].values())
    assert run.status == "succeeded" and run.saved_count == 1
