"""Bounded fallback with real Feature PostgreSQL, synthetic platform only."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Barrier, Thread

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.product_selection.run_contract import SelectionResolvedRequest
from app.modules.product_selection.run_service import SelectionRunService
from app.modules.product_selection.schemas import SelectionCategoriesRead
from app.modules.product_selection.models import ProductSelectionCandidate as Candidate, ProductSelectionObservation as Observation, ProductSelectionRun as Run
from app.modules.product_selection.exceptions import SelectionRunLeaseLostError
from app.platforms.douyin.product_selection import CompassRankPage, CompassSelectionBusinessError, CompassBasicInfo, CompassBadCommentRate, FieldObservation
from app.platforms.exceptions import PlatformAuthenticationInvalidError, PlatformRequestTimeoutError, PlatformResponseInvalidError, PlatformSignerFailedError
from tests.integration.test_postgresql_selection_runs import SETTINGS, FakePlatform, _input, _claim, _get, _executor
from tests.integration.test_postgresql_product_selection import selection_context, _product, _api_client

pytestmark = pytest.mark.integration


def _submit(context, command=None, now=None, reader=None):
    command = command or _input(context, rank_from=1, rank_to=10)
    def categories(actor, shop_id):
        assert not session.in_transaction()
        return SelectionCategoriesRead(shop_id=shop_id, industry_id="7", industry_name="行业", selected_category_id=None,
            nodes=[{"category_id": "1000009092", "name": "父类目", "children": [{"category_id": "1000009142", "name": "子类目", "children": []}]}])
    with Session(context[0]) as session:
        return SelectionRunService(session, settings=SETTINGS, category_reader=reader or categories).submit(context[4][0], command, now=now)


class WindowPlatform(FakePlatform):
    def __init__(self, request, pages):
        super().__init__()
        self.request, self.pages = request, pages
        self.rank_calls = []

    def rank(self, context, request, page_no):
        window = "primary" if request.scope == self.request.scope else "backup"
        self.rank_calls.append((window, page_no))
        value = self.pages[(window, page_no)]
        if isinstance(value, Exception):
            raise value
        return value if isinstance(value, CompassRankPage) else CompassRankPage(tuple(value), page_no, 10, len(value))

    def basic_info(self, context, product_id):
        return CompassBasicInfo(product_id, FieldObservation("available", ("厨具", "收纳")),
            FieldObservation("available", self.request.scope.period_begin),
            FieldObservation("available", CompassBadCommentRate(Decimal("0"), "int", 4)))


@pytest.mark.parametrize("primary,backup,state,count,calls", [
    ((_product(rank=1),), None, "primary", 1, [("primary", 1)]),
    ((), (_product(rank=1),), "backup", 1, [("primary", 1), ("backup", 1)]),
    ((), (), "both_empty", 0, [("primary", 1), ("backup", 1)]),
])
def test_select_window_before_facts_and_refresh_db_only(selection_context, primary, backup, state, count, calls):
    context = selection_context
    receipt = _submit(context)
    platform = WindowPlatform(receipt.execution.request_conditions, {("primary", 1): primary, ("backup", 1): backup})
    _executor(context, platform).execute_available()
    run = _get(context, receipt)
    assert (run.status, run.result_count, run.saved_count) == ("succeeded", count, count)
    assert run.request_conditions.date_outcome.state == state
    assert platform.rank_calls == calls
    with Session(context[0]) as session:
        observations = session.scalars(select(Observation).join(Candidate).where(Candidate.team_id == context[1][0])).all()
        assert len(observations) == count
        if count:
            actual = run.request_conditions.actual_scope()
            row = observations[0]
            assert row.period_begin == actual.period_begin and row.period_end == actual.period_end
            assert row.source_scope_hash == actual.fingerprint()
            assert row.source_context["business"] == actual.model_dump()
            assert row.source_context["date_selection"]["actual_window"] == state
    with _api_client(context) as client:
        headers = {"X-Team-ID": str(context[1][0])}
        assert client.get(f"/api/v1/product-selection/runs/{run.run_id}", headers=headers).json()["request_conditions"]["date_outcome"]["state"] == state
        for _ in range(2):
            data = client.get("/api/v1/product-selection/candidates", headers=headers).json()
            assert data["total"] == count
        if count:
            assert client.get(f"/api/v1/product-selection/observations/{observations[0].observation_id}", headers=headers).status_code == 200
    assert platform.rank_calls == calls


@pytest.mark.parametrize("failure", [PlatformAuthenticationInvalidError(), PlatformSignerFailedError(), PlatformRequestTimeoutError(), PlatformResponseInvalidError(),
    CompassSelectionBusinessError(details={"platform_code": "621000704"})])
@pytest.mark.parametrize("fallback", [False, True])
def test_failures_never_extend_window_search(selection_context, failure, fallback):
    receipt = _submit(selection_context)
    platform = WindowPlatform(receipt.execution.request_conditions, {
        ("primary", 1): () if fallback else failure, ("backup", 1): failure,
    })
    _executor(selection_context, platform).execute_available()
    run = _get(selection_context, receipt)
    assert run.status == "failed" and run.result_count is None and run.saved_count == 0
    assert len(platform.rank_calls) == (2 if fallback else 1)
    assert (run.request_conditions.date_outcome.state if run.request_conditions.date_outcome else None) == ("fallback_failed" if fallback else None)
    if failure.code == "DOUYIN_SELECTION_BUSINESS_REJECTED": assert run.platform_business_code == "621000704"


def test_first_page_has_items_outside_selected_rank_is_not_empty_trigger(selection_context):
    receipt = _submit(selection_context, _input(selection_context, rank_from=11, rank_to=20))
    platform = WindowPlatform(receipt.execution.request_conditions, {("primary", 1): (_product(rank=1),), ("primary", 2): ()})
    _executor(selection_context, platform).execute_available()
    run = _get(selection_context, receipt)
    assert run.status == "succeeded" and run.result_count == 0
    assert run.request_conditions.date_outcome.state == "primary"
    assert platform.rank_calls == [("primary", 1), ("primary", 2)]


def test_inconsistent_empty_page_is_not_a_fallback_trigger(selection_context):
    receipt = _submit(selection_context)
    platform = WindowPlatform(receipt.execution.request_conditions, {("primary", 1): CompassRankPage((), 1, 10, 10)})
    _executor(selection_context, platform).execute_available()
    assert _get(selection_context, receipt).error_code == "PLATFORM_RESPONSE_INVALID"
    assert platform.rank_calls == [("primary", 1)]


def test_fallback_second_page_and_basic_failure_do_not_mix_windows(selection_context):
    receipt = _submit(selection_context, _input(selection_context, rank_from=1, rank_to=20))
    platform = WindowPlatform(receipt.execution.request_conditions, {("primary", 1): (), ("backup", 1): (_product(rank=1),),
        ("backup", 2): CompassSelectionBusinessError(details={"platform_code": 621000704})})
    _executor(selection_context, platform).execute_available()
    run = _get(selection_context, receipt)
    assert run.status == "partial" and run.saved_count == 1
    assert run.request_conditions.date_outcome.state == "backup"
    assert platform.rank_calls == [("primary", 1), ("backup", 1), ("backup", 2)]


def test_replay_cross_day_before_category_io_and_outcome_does_not_break_active_dedup(selection_context):
    command = _input(selection_context, rank_from=1, rank_to=10)
    first = _submit(selection_context, command)
    claim = _claim(selection_context)
    with Session(selection_context[0]) as session:
        service = SelectionRunService(session, settings=SETTINGS)
        service.choose_window(claim, "fallback_checking")
        service.choose_window(claim, "backup")
    def forbidden(*args): raise AssertionError("Replay must not query platform categories")
    replay = _submit(selection_context, command, now=datetime.now(UTC) + timedelta(days=1), reader=forbidden)
    assert replay.receipt_id == first.receipt_id
    assert replay.execution.request_conditions.scope == first.execution.request_conditions.scope
    assert replay.execution.request_conditions.date_outcome.state == "backup"
    reused = _submit(selection_context)
    assert reused.reused and reused.execution_run_id == first.execution_run_id
    with Session(selection_context[0]) as session:
        service = SelectionRunService(session, settings=SETTINGS)
        with pytest.raises(SelectionRunLeaseLostError): service.choose_window(claim, "primary")
        session.get(Run, claim.run_id).lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
        service.recover_expired()
        with pytest.raises(SelectionRunLeaseLostError): service.choose_window(claim, "backup")
    assert _get(selection_context, first).status == "interrupted"


def test_two_sessions_create_one_canonical_v2_execution(selection_context):
    barrier, receipts, failures = Barrier(2), [], []
    def submit():
        try:
            barrier.wait(timeout=10)
            receipts.append(_submit(selection_context))
        except Exception as error: failures.append(type(error).__name__)
    threads = [Thread(target=submit) for _ in range(2)]
    for thread in threads: thread.start()
    for thread in threads: thread.join(timeout=20)
    assert not failures and all(not thread.is_alive() for thread in threads)
    assert len(receipts) == 2 and receipts[0].execution_run_id == receipts[1].execution_run_id
    assert sorted(receipt.reused for receipt in receipts) == [False, True]


def test_backup_basic_failure_preserves_candidates_and_forbids_any_post_write_window_change(selection_context):
    from app.modules.product_selection.service import ProductSelectionFactService
    receipt = _submit(selection_context)
    claim = _claim(selection_context)
    with Session(selection_context[0]) as session:
        service = SelectionRunService(session, settings=SETTINGS)
        service.choose_window(claim, "fallback_checking")
        chosen = service.choose_window(claim, "backup")
        actor = service.authorize(claim, stage="persistence")
    with Session(selection_context[0]) as session:
        facts = ProductSelectionFactService(session)
        page = CompassRankPage((_product(rank=1),), 1, 10, 1)
        with pytest.raises(SelectionRunLeaseLostError):
            facts.persist_rank_page(actor=actor, shop_id=claim.shop_id, scope=claim.request.scope,
                page=page, started_at=claim.started_at, retrieved_at=datetime.now(UTC), claim=claim)
        saved = facts.persist_rank_page(actor=actor, shop_id=claim.shop_id, scope=chosen.actual_scope(),
            page=page, started_at=claim.started_at, retrieved_at=datetime.now(UTC), claim=claim)
        facts.record_basic_info_failure(actor=actor, observation_id=saved[0], rank_started_at=claim.started_at,
            at=datetime.now(UTC), error=PlatformRequestTimeoutError(), claim=claim)
    with Session(selection_context[0]) as session:
        service = SelectionRunService(session, settings=SETTINGS)
        with pytest.raises(SelectionRunLeaseLostError): service.choose_window(claim, "primary")
        service.finish(claim)
    run = _get(selection_context, receipt)
    assert run.status == "partial" and run.saved_count == 1 and run.supplement_failed_count == 1
    assert run.request_conditions.date_outcome.state == "backup"
