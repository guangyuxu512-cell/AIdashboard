"""Sparse page execution on assigned PostgreSQL; platform input is synthetic."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.modules.product_selection.models import ProductSelectionRun as Run
from app.modules.product_selection.request_mapping import freeze_short_video_request
from app.modules.product_selection.run_service import SelectionRunService
from app.platforms.douyin.product_selection import CompassRankPage, CompassSelectionBusinessError
from app.platforms.exceptions import PlatformSignerFailedError
from tests.integration.test_postgresql_product_selection import selection_context, _product, _api_client
from tests.integration.test_postgresql_selection_runs import _input, _get, _executor, SETTINGS
from tests.integration.test_postgresql_selection_windows import WindowPlatform, _category_tree, _submit

pytestmark = pytest.mark.integration


def product(rank, *, identity=None, first=True):
    return replace(_product(identity or f"900000000000000{rank:04}", rank=rank), newly_on_ranking=first)


def test_150_to_200_skips_middle_pages_official_rank_dedup_and_api(selection_context):
    context = selection_context
    receipt = _submit(context, _input(context, rank_from=150, rank_to=200))
    request = receipt.execution.request_conditions
    pages = {("primary", 1): (product(1, identity="9000000000000000150"),),
             ("primary", 15): (product(149), product(150), product(159)),
             ("primary", 16): (product(150), product(160))}
    pages |= {("primary", number): (product(number * 10),) for number in range(17, 21)}
    platform = WindowPlatform(request, pages)
    _executor(context, platform).execute_available()
    run = _get(context, receipt)
    assert run.status == "succeeded" and run.saved_count == run.result_count == 7
    assert platform.rank_calls == [("primary", p) for p in [1, 15, 16, 17, 18, 19, 20]]
    assert run.request_conditions.version == 8
    with _api_client(context) as client:
        response = client.get("/api/v1/product-selection/candidates", headers={"X-Team-ID": str(context[1][0])}).json()
        assert response["total"] == 7
        assert sorted(row["rank"] for row in response["items"]) == [150, 159, 160, 170, 180, 190, 200]
        assert len({row["product_id"] for row in response["items"]}) == 7


@pytest.mark.parametrize("total,calls,count", [(20, [1], 0), (149, [1, 15], 0), (150, [1, 15], 1), (160, [1, 15, 16], 2)])
def test_platform_total_bounds_jump_and_never_fills_results(selection_context, total, calls, count):
    context = selection_context
    receipt = _submit(context, _input(context, rank_from=150, rank_to=200))
    request = receipt.execution.request_conditions
    pages = {("primary", p): CompassRankPage((product(1 if p == 1 else min(p * 10, total)),), p, 10, total) for p in calls}
    platform = WindowPlatform(request, pages)
    _executor(context, platform).execute_available()
    run = _get(context, receipt)
    assert run.status == "succeeded" and run.saved_count == count
    assert platform.rank_calls == [("primary", p) for p in calls]


@pytest.mark.parametrize("first,last,accepted,pages", [(149, 150, [149, 150], [1, 15]), (150, 150, [150], [1, 15]), (200, 200, [200], [1, 20]), (1, 10, [1, 10], [1])])
def test_boundary_rank_and_first_page_reuse(selection_context, first, last, accepted, pages):
    receipt = _submit(selection_context, _input(selection_context, rank_from=first, rank_to=last))
    data = {("primary", p): tuple(product(r) for r in [1, 10, 149, 150, 200, 201] if (r - 1) // 10 + 1 == p) for p in pages}
    platform = WindowPlatform(receipt.execution.request_conditions, data)
    _executor(selection_context, platform).execute_available()
    run = _get(selection_context, receipt)
    assert run.status == "succeeded" and run.saved_count == len(accepted)
    assert platform.rank_calls == [("primary", p) for p in pages]


@pytest.mark.parametrize("primary", [(), CompassSelectionBusinessError(details={"platform_code": 621000704})])
def test_frozen_backup_uses_same_sparse_pages_before_facts(selection_context, primary):
    receipt = _submit(selection_context, _input(selection_context, rank_from=150, rank_to=150))
    platform = WindowPlatform(receipt.execution.request_conditions, {("primary", 1): primary, ("backup", 1): (product(1),), ("backup", 15): (product(150),)})
    _executor(selection_context, platform).execute_available()
    run = _get(selection_context, receipt)
    assert run.status == "succeeded" and run.saved_count == 1
    assert run.request_conditions.date_outcome.state == "backup"
    assert platform.rank_calls == [("primary", 1), ("backup", 1), ("backup", 15)]
    assert run.request_conditions.actual_scope() == run.request_conditions.date_plan.backup_scope


def test_first_listed_is_return_flag_not_first_local_observation(selection_context):
    receipt = _submit(selection_context, _input(selection_context, rank_from=150, rank_to=150, first_listed_only=True))
    platform = WindowPlatform(receipt.execution.request_conditions, {("primary", 1): (product(1),), ("primary", 15): (product(150, first=False),)})
    _executor(selection_context, platform).execute_available()
    run = _get(selection_context, receipt)
    assert run.status == "succeeded" and run.saved_count == 0
    assert platform.rank_calls == [("primary", 1), ("primary", 15)]


def test_target_page_failure_does_not_change_window(selection_context):
    receipt = _submit(selection_context, _input(selection_context, rank_from=150, rank_to=200))
    platform = WindowPlatform(receipt.execution.request_conditions, {("primary", 1): (product(1),), ("primary", 15): (product(150),), ("primary", 16): PlatformSignerFailedError()})
    _executor(selection_context, platform).execute_available()
    run = _get(selection_context, receipt)
    assert run.status == "partial" and run.saved_count == 1
    assert run.request_conditions.date_outcome.state == "primary"
    assert platform.rank_calls == [("primary", 1), ("primary", 15), ("primary", 16)]


@pytest.mark.parametrize("backup", [(), PlatformSignerFailedError()])
def test_empty_or_failed_backup_never_requests_target_pages(selection_context, backup):
    receipt = _submit(selection_context, _input(selection_context, rank_from=150, rank_to=200))
    platform = WindowPlatform(receipt.execution.request_conditions, {("primary", 1): (), ("backup", 1): backup})
    _executor(selection_context, platform).execute_available()
    run = _get(selection_context, receipt)
    assert run.status == ("succeeded" if backup == () else "failed")
    assert run.saved_count == 0
    assert run.request_conditions.date_outcome.state == ("both_empty" if backup == () else "fallback_failed")
    assert platform.rank_calls == [("primary", 1), ("backup", 1)]


@pytest.mark.parametrize("changes", [{"brand": "known"}, {"price_mode": "custom", "price_above": "20", "price_below": "100"}])
def test_nondefault_brand_or_price_does_not_expand_business_retry(selection_context, changes):
    receipt = _submit(selection_context, _input(selection_context, rank_from=150, rank_to=200, **changes))
    platform = WindowPlatform(receipt.execution.request_conditions, {("primary", 1): CompassSelectionBusinessError(details={"platform_code": 621000704})})
    _executor(selection_context, platform).execute_available()
    run = _get(selection_context, receipt)
    assert run.status == "failed" and run.saved_count == 0 and run.request_conditions.date_outcome is None
    assert platform.rank_calls == [("primary", 1)]


@pytest.mark.parametrize("changes,version", [({}, 3), ({"period": "realtime"}, 4), ({"period": "1d"}, 5), ({"price_mode": "custom", "price_above": "20", "price_below": "100"}, 6)])
def test_active_old_run_is_reused_without_rewriting_its_plan(selection_context, changes, version):
    context, accepted = selection_context, datetime.now(UTC)
    command = _input(context, rank_from=150, rank_to=200, **changes)
    def old_resolver(original, at):
        return freeze_short_video_request(original, at).legacy_paging_request()
    with Session(context[0]) as session:
        old = SelectionRunService(session, settings=SETTINGS, resolver=old_resolver, category_reader=lambda actor, shop: _category_tree(shop)).submit(context[4][0], command, now=accepted)
        row = session.get(Run, old.execution_run_id)
        before = dict(row.request_conditions), row.request_fingerprint
    receipt = _submit(context, _input(context, rank_from=150, rank_to=200, **changes), now=accepted)
    assert receipt.execution_run_id == old.execution_run_id
    assert receipt.execution.request_conditions.version == version
    with Session(context[0]) as session:
        row = session.get(Run, old.execution_run_id)
        assert (row.request_conditions, row.request_fingerprint) == before
    assert receipt.execution.request_conditions.page_numbers == tuple(range(1, 21))


def test_active_legacy_brand_run_is_preserved_but_not_reused_for_corrected_mapping(selection_context):
    context, accepted = selection_context, datetime.now(UTC)
    command = _input(context, rank_from=150, rank_to=200, brand="known")

    def old_resolver(original, at):
        default = freeze_short_video_request(original.model_copy(update={"brand": "all"}), at).legacy_paging_request()
        raw = default.model_dump(mode="json") | {"version": 7}
        raw["original"]["brand"] = "known"
        raw["scope"]["brand_type"] = "0"
        raw["date_plan"]["backup_scope"]["brand_type"] = "0"
        return SelectionResolvedRequest.model_validate(raw)

    with Session(context[0]) as session:
        old = SelectionRunService(
            session, settings=SETTINGS, resolver=old_resolver,
            category_reader=lambda actor, shop: _category_tree(shop),
        ).submit(context[4][0], command, now=accepted)
        row = session.get(Run, old.execution_run_id)
        before = dict(row.request_conditions), row.request_fingerprint

    replay = _submit(context, command, now=accepted)
    assert replay.execution_run_id == old.execution_run_id
    assert replay.execution.request_conditions.version == 7
    assert replay.execution.request_conditions.scope.brand_type == "0"

    receipt = _submit(
        context,
        _input(context, rank_from=150, rank_to=200, brand="known"),
        now=accepted,
    )
    assert receipt.execution_run_id != old.execution_run_id
    assert receipt.execution.request_conditions.version == 9
    assert receipt.execution.request_conditions.scope.brand_type == "1"
    with Session(context[0]) as session:
        row = session.get(Run, old.execution_run_id)
        assert (row.request_conditions, row.request_fingerprint) == before
        legacy = SelectionResolvedRequest.model_validate(row.request_conditions)
        assert legacy.version == 7 and legacy.scope.brand_type == "0"
