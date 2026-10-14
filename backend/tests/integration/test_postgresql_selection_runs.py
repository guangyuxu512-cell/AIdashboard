"""Synthetic platform I/O + real registered Feature PostgreSQL, not live proof."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from threading import Barrier, Thread
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic import command as migration_command
from alembic.config import Config
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.access.models import TeamMembership, TeamShopAccess
from app.modules.access.repository import AccessManagementRepository
from app.modules.access.service import ActorContextService
from app.modules.product_selection.exceptions import (
    SelectionRunConflictError, SelectionRunLeaseLostError, SelectionRunNotFoundError,
    SelectionShopUnavailableError, SelectionRequestUnconfirmedError,
)
from app.modules.product_selection.models import ProductSelectionRun as Run, ProductSelectionCandidate as Candidate, ProductSelectionObservation as Observation
from app.modules.product_selection.run_contract import SelectionRunCreate, SelectionResolvedRequest
from app.modules.product_selection.run_executor import SelectionRunExecutor
from app.modules.product_selection.run_service import SelectionRunService
from app.modules.product_selection.request_mapping import prepare_short_video_scope
from app.modules.product_selection.service import ProductSelectionFactService
from app.modules.shops.models import Shop
from app.platforms.douyin.product_selection import CompassRankPage, CompassSelectionBusinessError, CompassBasicInfo, FieldObservation
from app.platforms.exceptions import PlatformAuthenticationInvalidError, PlatformRequestTimeoutError
from tests.integration.test_postgresql_product_selection import (
    selection_context, _scope, _product, _remove_team_grants_and_membership, _api_client,
)


pytestmark = pytest.mark.integration
SETTINGS = Settings(product_selection_execution_enabled=True)


def _resolver(original, now):
    # Synthetic mapping only. Never installed by production dependencies.
    return SelectionResolvedRequest(original=original, scope=_scope(), page_numbers=(2,))


def _input(context, **changes):
    return SelectionRunCreate(**({
        "shop_id": context[3][0], "submission_key": uuid4(), "channel": "short-video",
        "period": "7d", "industry_id": "7", "category_ids": ("1000009092", "1000009142"),
        "brand": "all", "price_mode": "all", "rank_from": 11, "rank_to": 20,
    } | changes))


def _submit(context, value=None, *, actor=None, resolver=_resolver, now=None):
    with Session(context[0]) as session:
        return SelectionRunService(session, settings=SETTINGS, resolver=resolver).submit(actor or context[4][0], value or _input(context), now=now)


def _claim(context):
    with Session(context[0]) as session:
        return SelectionRunService(session, settings=SETTINGS).claim_next()


def _get(context, receipt, *, actor=None):
    with Session(context[0]) as session:
        return SelectionRunService(session).get(actor or context[4][0], receipt.execution_run_id)


class FakePlatform:
    def __init__(self, *, products=(), rank_error=None, basic_error=None, before_rank_return=None):
        self.products, self.rank_error, self.basic_error = products, rank_error, basic_error
        self.before_rank_return = before_rank_return
        self.calls = []

    def session_context(self, shop_id):
        self.calls.append("session")
        return SimpleNamespace(shop_id=shop_id)

    def rank(self, context, request, page_no):
        self.calls.append("rank")
        if self.rank_error:
            raise self.rank_error
        if self.before_rank_return:
            self.before_rank_return()
        return CompassRankPage(tuple(self.products), page_no, 10, len(self.products))

    def basic_info(self, context, product_id):
        self.calls.append("basic_info")
        if self.basic_error:
            raise self.basic_error
        return CompassBasicInfo(product_id, FieldObservation("missing"), FieldObservation("null"), FieldObservation("missing"))


def _executor(context, platform):
    return SelectionRunExecutor(session_factory=lambda: Session(context[0]), platform=platform, settings=SETTINGS)


def test_explicit_window_changes_cannot_rewrite_replayed_or_claimed_run(selection_context):
    context = selection_context
    # Synthetic, independently supplied windows, not a platform cutoff rule.
    window = [date(2026, 10, 3), date(2026, 10, 9)]
    resolutions = []

    def explicit_resolver(original, now):
        resolutions.append(tuple(window))
        return SelectionResolvedRequest(
            original=original,
            scope=prepare_short_video_scope(original, period_begin=window[0], period_end=window[1]),
            page_numbers=(1,),
        )

    command = _input(context, rank_from=1, rank_to=10)
    at = datetime.now(UTC)
    accepted = _submit(context, command, resolver=explicit_resolver, now=at)
    window[:] = [date(2026, 10, 4), date(2026, 10, 10)]
    replay = _submit(context, command, resolver=explicit_resolver, now=at + timedelta(days=1))
    assert replay.receipt_id == accepted.receipt_id
    assert replay.execution_run_id == accepted.execution_run_id
    assert replay.execution.request_conditions.scope.end_date == "2026/10/09 00:00:00"
    assert len(resolutions) == 1

    # Only a fresh explicit submission may freeze a different supplied window.
    newer = _submit(context, _input(context, rank_from=1, rank_to=10), resolver=explicit_resolver, now=at + timedelta(days=1))
    assert not newer.reused and newer.execution_run_id != accepted.execution_run_id
    assert newer.execution.request_conditions.scope.end_date == "2026/10/10 00:00:00"
    assert len(resolutions) == 2
    claim = _claim(context)
    assert claim.run_id == accepted.execution_run_id
    assert claim.request.scope.begin_date == "2026/10/03 00:00:00"
    assert claim.request.scope.end_date == "2026/10/09 00:00:00"
    assert len(resolutions) == 2  # Claim/progress reads do not resolve again.
    assert _get(context, accepted).request_conditions == replay.execution.request_conditions


def test_successful_empty_run_is_queryable_without_inventing_candidates(selection_context):
    context = selection_context
    receipt = _submit(context)
    platform = FakePlatform()
    assert _executor(context, platform).execute_available() == 1
    run = _get(context, receipt)
    assert (run.status, run.result_count, run.saved_count) == ("succeeded", 0, 0)
    assert platform.calls == ["session", "rank"]
    with Session(context[0]) as session:
        assert session.scalar(select(func.count()).select_from(Candidate).where(Candidate.team_id == context[1][0])) == 0
    with _api_client(context) as client:
        response = client.get(f"/api/v1/product-selection/runs/{receipt.receipt_id}", headers={"X-Team-ID": str(context[1][0])})
        assert response.status_code == 200
        assert response.json()["result_count"] == 0
        assert "submission_key" not in response.json()
        assert client.get("/api/v1/product-selection/runs", headers={"X-Team-ID": str(context[1][0])}).json()["total"] == 1
    assert platform.calls == ["session", "rank"]


@pytest.mark.parametrize("code", [621000704, "621000704"])
def test_business_rejection_is_failure_with_scalar_code_not_empty_success(selection_context, code):
    context = selection_context
    receipt = _submit(context)
    platform = FakePlatform(rank_error=CompassSelectionBusinessError(details={"platform_code": code, "untrusted": "not stored"}))
    _executor(context, platform).execute_available()
    run = _get(context, receipt)
    assert run.status == "failed" and run.result_count is None
    assert run.error_stage == "platform_business" and run.platform_business_code == code
    assert "untrusted" not in run.model_dump_json()


def test_basic_failure_keeps_facts_and_repeat_run_updates_not_duplicates(selection_context):
    context = selection_context
    for _ in range(2):
        receipt = _submit(context)
        _executor(context, FakePlatform(products=(_product(),), basic_error=PlatformRequestTimeoutError())).execute_available()
        run = _get(context, receipt)
        assert (run.status, run.saved_count, run.supplement_failed_count) == ("partial", 1, 1)
    with Session(context[0]) as session:
        rows, total = ProductSelectionFactService(session).list_read(actor=context[4][0])
        assert total == 1 and rows[0].last_error_stage == "basic_info_request"
        assert rows[0].last_run_id == receipt.execution_run_id
        assert rows[0].product_id == _product().product_id
        assert rows[0].video_metric_ranges.pay_amt.value_range[0].value == 0
        assert session.scalar(select(func.count()).select_from(Candidate).where(Candidate.team_id == context[1][0])) == 1


def test_partial_basic_fields_are_independent_and_not_counted_twice(selection_context):
    context = selection_context
    receipt = _submit(context)
    claim = _claim(context)
    at = datetime.now(UTC)
    with Session(context[0]) as session:
        facts = ProductSelectionFactService(session)
        obs = facts.persist_rank_page(actor=context[4][0], shop_id=context[3][0], scope=claim.request.scope, page=CompassRankPage((_product(),), 2, 10, 1), started_at=claim.started_at, retrieved_at=at, claim=claim)[0]
        basic = CompassBasicInfo(_product().product_id, FieldObservation("available", ("厨具",)), FieldObservation("missing"), FieldObservation("null"))
        later = at  # identical timestamp precision must still be idempotent
        assert facts.persist_basic_info(actor=context[4][0], observation_id=obs, rank_started_at=claim.started_at, retrieved_at=later, basic=basic, claim=claim)
        assert not facts.persist_basic_info(actor=context[4][0], observation_id=obs, rank_started_at=claim.started_at, retrieved_at=later, basic=basic, claim=claim)
        SelectionRunService(session).finish(claim)
        value = facts.get_read(actor=context[4][0], observation_id=obs)
        assert value.category_path == ["厨具"] and value.first_on_shelf_date is None
    assert _get(context, receipt).supplement_failed_count == 1


def test_two_users_own_receipts_cross_day_replay_never_resolves_again(selection_context):
    context = selection_context
    with Session(context[0]) as session:
        session.scalar(select(TeamMembership).where(TeamMembership.user_id == context[2][1])).enabled = False
        session.flush()
        session.add(TeamMembership(team_id=context[1][0], user_id=context[2][1]))
        session.commit()
        second_actor = ActorContextService(session).resolve(user_id=context[2][1], requested_team_id=context[1][0])
    first, second = _input(context), _input(context)
    a = _submit(context, first)
    b = _submit(context, second, actor=second_actor)
    assert b.reused and b.receipt_id != a.receipt_id and b.execution_run_id == a.execution_run_id
    assert b.submission_key == second.submission_key
    assert "submission_key" not in b.execution.model_dump()
    _executor(context, FakePlatform()).execute_available()
    def forbidden_resolver(*args):
        raise AssertionError("Replay must not recalculate dates")
    replay = _submit(context, second, actor=second_actor, resolver=forbidden_resolver, now=datetime.now(UTC) + timedelta(days=1))
    assert replay.receipt_id == b.receipt_id and replay.execution.status == "succeeded"
    with Session(context[0]) as session:
        rows = list(session.scalars(select(Run).where(Run.team_id == context[1][0])))
        assert len(rows) == 2 and sum(row.reused_run_id is None for row in rows) == 1
        receipt_row = session.get(Run, b.receipt_id)
        assert receipt_row.result_count is None and receipt_row.started_at is None and receipt_row.saved_count == 0
    with pytest.raises(SelectionRunConflictError):
        _submit(context, second.model_copy(update={"rank_to": 19}), actor=second_actor)


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_submit_one_execution_and_replayable_receipts(selection_context, same_key):
    context = selection_context
    inputs = [_input(context), _input(context)]
    if same_key:
        inputs[1] = inputs[0]
    start = Barrier(2)
    results, errors = [], []
    def worker(value):
        try:
            start.wait(timeout=10)
            results.append(_submit(context, value))
        except Exception as error:
            errors.append(type(error).__name__)
    threads = [Thread(target=worker, args=(value,)) for value in inputs]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
        assert not thread.is_alive()
    assert not errors and len(results) == 2
    assert len({row.execution_run_id for row in results}) == 1
    assert len({row.receipt_id for row in results}) == (1 if same_key else 2)


def test_claim_race_global_one_execution_and_receipts_never_claimed(selection_context):
    context = selection_context
    first = _submit(context)
    receipt = _submit(context)  # receipt only
    second = _submit(context, _input(context, shop_id=context[3][1]))
    barrier, claims, errors = Barrier(2), [], []
    def worker():
        try:
            barrier.wait(timeout=10)
            claims.append(_claim(context))
        except Exception as error:
            errors.append(type(error).__name__)
    threads = [Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
        assert not thread.is_alive()
    assert not errors and len([item for item in claims if item]) == 1
    winner = next(item for item in claims if item)
    # SKIP LOCKED can give the two claimants different canonical rows. The
    # unique running index admits one commit, not a guaranteed FIFO winner.
    assert winner.run_id in {first.execution_run_id, second.execution_run_id}
    assert winner.run_id != receipt.receipt_id
    with Session(context[0]) as session:
        assert session.scalar(select(func.count()).select_from(Run).where(Run.status == "running")) == 1
        assert session.get(Run, receipt.receipt_id).status == "reused"
        for run_id in {first.execution_run_id, second.execution_run_id}:
            assert session.get(Run, run_id).status == ("running" if run_id == winner.run_id else "pending")


@pytest.mark.parametrize("earliest_locked", [False, True])
def test_claim_orders_unlocked_canonical_rows_and_skips_receipts(selection_context, earliest_locked):
    context = selection_context
    first = _submit(context)
    receipt = _submit(context)
    second = _submit(context, _input(context, shop_id=context[3][1]))
    with Session(context[0]) as locker:
        if earliest_locked:
            locker.scalar(select(Run).where(Run.run_id == first.execution_run_id).with_for_update())
        claim = _claim(context)
        assert claim is not None
        assert claim.run_id == (second.execution_run_id if earliest_locked else first.execution_run_id)
        assert claim.run_id != receipt.receipt_id
        assert locker.get(Run, receipt.receipt_id).status == "reused"


def test_expired_execution_is_interrupted_and_late_result_cannot_write(selection_context):
    context = selection_context
    receipt = _submit(context)
    claim = _claim(context)
    with Session(context[0]) as session:
        row = session.get(Run, claim.run_id)
        row.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
        with pytest.raises(SelectionRunLeaseLostError):
            ProductSelectionFactService(session).persist_rank_page(actor=context[4][0], shop_id=claim.shop_id, scope=claim.request.scope, page=CompassRankPage((_product(),), 2, 10, 1), started_at=claim.started_at, retrieved_at=datetime.now(UTC), claim=claim)
        assert SelectionRunService(session).recover_expired() == 1
        with pytest.raises(SelectionRunLeaseLostError):
            SelectionRunService(session).finish(claim)
    run = _get(context, receipt)
    assert run.status == "interrupted" and run.result_count is None
    replacement = _submit(context)
    assert replacement.execution_run_id != receipt.execution_run_id
    assert _claim(context).run_id == replacement.execution_run_id


@pytest.mark.parametrize("revoke", ["shop", "membership", "disable"])
def test_revocation_or_disable_after_rank_preserves_safe_terminal_state_without_facts(selection_context, revoke):
    context = selection_context
    receipt = _submit(context)
    def change():
        with Session(context[0]) as session:
            if revoke == "shop":
                session.execute(delete(TeamShopAccess).where(TeamShopAccess.team_id == context[1][0], TeamShopAccess.shop_id == context[3][0]))
            elif revoke == "membership":
                session.execute(delete(TeamMembership).where(TeamMembership.team_id == context[1][0], TeamMembership.user_id == context[2][0]))
            else:
                session.get(Shop, context[3][0]).enabled = False
            session.commit()
    platform = FakePlatform(products=(_product(),), before_rank_return=change)
    _executor(context, platform).execute_available()
    assert platform.calls == ["session", "rank"]
    with Session(context[0]) as session:
        row = session.get(Run, receipt.execution_run_id)
        assert row.status == "failed" and row.saved_count == 0 and row.lease_id is None


def test_disabled_before_execution_sends_no_external_call(selection_context):
    context = selection_context
    receipt = _submit(context)
    with Session(context[0]) as session:
        session.get(Shop, context[3][0]).enabled = False
        session.commit()
    with pytest.raises(SelectionShopUnavailableError):
        _submit(context)
    platform = FakePlatform()
    _executor(context, platform).execute_available()
    assert platform.calls == [] and _get(context, receipt).status == "failed"


def test_cross_team_read_and_revoked_receipt_rejected(selection_context):
    context = selection_context
    receipt = _submit(context)
    with pytest.raises(SelectionRunNotFoundError):
        _get(context, receipt, actor=context[4][1])
    with Session(context[0]) as session:
        session.execute(delete(TeamShopAccess).where(TeamShopAccess.team_id == context[1][0], TeamShopAccess.shop_id == context[3][0]))
        session.commit()
    with pytest.raises(SelectionRunNotFoundError):
        _submit(context, _input(context, submission_key=receipt.submission_key))


def test_only_failed_run_prevents_team_delete_and_schema_downgrade(selection_context):
    context = selection_context
    receipt = _submit(context)
    _executor(context, FakePlatform(rank_error=PlatformAuthenticationInvalidError())).execute_available()
    _remove_team_grants_and_membership(context)
    with Session(context[0]) as session:
        assert AccessManagementRepository(session).team_has_references(context[1][0])
    backend = Path(__file__).resolve().parents[2]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    with pytest.raises(RuntimeError, match="contains run history"):
        migration_command.downgrade(config, "20261010_0042")
    with Session(context[0]) as session:
        assert session.get(Run, receipt.execution_run_id).status == "failed"


def test_unconfirmed_request_does_not_create_empty_job_or_platform_request(selection_context):
    context = selection_context
    with Session(context[0]) as session:
        with pytest.raises(SelectionRequestUnconfirmedError):
            SelectionRunService(session, settings=SETTINGS).submit(context[4][0], _input(context, channel="baiying"))
        assert session.scalar(select(func.count()).select_from(Run).where(Run.team_id == context[1][0])) == 0


def test_post_api_receipt_contract_replay_and_read_do_not_create_platform_work(selection_context):
    context = selection_context
    from app.modules.product_selection.api import get_selection_run_service
    def dependency():
        with Session(context[0]) as session:
            yield SelectionRunService(session, settings=SETTINGS, resolver=_resolver)
    value = _input(context)
    headers = {"X-Team-ID": str(context[1][0])}
    with _api_client(context) as client:
        client.app.dependency_overrides[get_selection_run_service] = dependency
        response = client.post("/api/v1/product-selection/runs", json=value.model_dump(mode="json"), headers=headers)
        assert response.status_code == 202
        receipt = response.json()
        assert receipt["submission_key"] == str(value.submission_key)
        assert receipt["receipt_id"] == receipt["execution_run_id"]
        assert "submission_key" not in receipt["execution"]
        assert receipt["execution"]["status"] == "pending"
        assert client.post("/api/v1/product-selection/runs", json=value.model_dump(mode="json"), headers=headers).json() == receipt
        assert client.get(f"/api/v1/product-selection/runs/{receipt['receipt_id']}", headers=headers).json() == receipt["execution"]
        conflict = value.model_copy(update={"rank_to": 19})
        assert client.post("/api/v1/product-selection/runs", json=conflict.model_dump(mode="json"), headers=headers).status_code == 409
    with Session(context[0]) as session:
        assert session.scalar(select(func.count()).select_from(Run).where(Run.team_id == context[1][0])) == 1


def test_terminal_transition_racing_new_receipt_is_consistent_and_replayable(selection_context):
    context = selection_context
    first = _submit(context)
    claim = _claim(context)
    next_intent = _input(context)
    barrier, results, errors = Barrier(2), [], []
    def finish():
        try:
            barrier.wait(timeout=10)
            with Session(context[0]) as session:
                SelectionRunService(session).finish(claim, error=PlatformRequestTimeoutError())
        except Exception as error:
            errors.append(type(error).__name__)
    def submit():
        try:
            barrier.wait(timeout=10)
            results.append(_submit(context, next_intent))
        except Exception as error:
            errors.append(type(error).__name__)
    threads = [Thread(target=finish), Thread(target=submit)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
        assert not thread.is_alive()
    assert not errors and len(results) == 1
    # Either linearization is legal: B accepted before terminal reuses A, or
    # afterwards becomes a fresh pending execution. B's own key never vanishes.
    replay = _submit(context, next_intent)
    assert replay.receipt_id == results[0].receipt_id
    assert _get(context, first).status == "failed"
    with Session(context[0]) as session:
        assert session.scalar(select(func.count()).select_from(Run).where(Run.team_id == context[1][0], Run.status.in_(("pending", "running")))) <= 1
