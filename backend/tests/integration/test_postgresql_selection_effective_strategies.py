"""One legal running row on 0044; complete reused/direct strategy sets."""

from datetime import UTC, datetime
from datetime import timedelta
from threading import Event, Thread, current_thread

import pytest
from sqlalchemy.orm import Session
from sqlalchemy import func, select, delete

from app.modules.product_selection.run_repository import SelectionRunRepository
from app.modules.product_selection.models import ProductSelectionRun as Run
from app.modules.product_selection.run_service import SelectionRunService
from app.modules.product_selection.strategy_service import SelectionStrategyService
from app.modules.product_selection.strategy_contract import SelectionStrategyUpdate
from app.modules.access.models import TeamShopAccess
from tests.integration.test_postgresql_product_selection import selection_context
from tests.integration.test_postgresql_selection_runs import _input, _claim, SETTINGS
from tests.integration.test_postgresql_selection_strategies import _save, _config
from tests.integration.test_postgresql_selection_windows import _submit, _category_tree

pytestmark = pytest.mark.integration


def submit(context, shop, at, strategy=None):
    changes = {} if strategy is None else {"strategy_id": strategy.strategy_id, "strategy_version": strategy.version}
    command = _input(context, shop_id=shop, rank_from=1, rank_to=25, **changes)
    return _submit(context, command, now=at)


@pytest.mark.parametrize("running_direct", [False, True])
@pytest.mark.parametrize("pending_direct", [False, True])
def test_both_canonicals_complete_effective_strategy_sets_block_cross_shop(selection_context, running_direct, pending_direct):
    context, at = selection_context, datetime.now(UTC)
    shop_a, shop_b = context[3]
    strategy = _save(context)
    first = submit(context, shop_a, at, strategy if running_direct else None)
    claim = _claim(context)
    assert claim.run_id == first.execution_run_id
    if not running_direct:
        assert submit(context, shop_a, at, strategy).execution_run_id == first.execution_run_id
    # A genuine edit preserves S identity while moving its request Shop.
    with Session(context[0]) as session:
        strategy = SelectionStrategyService(session).save(context[4][0], SelectionStrategyUpdate(**(_config(context, shop_id=shop_b).model_dump() | {"expected_version": strategy.version})), strategy_id=strategy.strategy_id)
    other = _save(context, shop_id=shop_b) if pending_direct else None
    second = submit(context, shop_b, at, other)
    alias = submit(context, shop_b, at, strategy)
    assert alias.reused and alias.execution_run_id == second.execution_run_id
    with Session(context[0]) as session:
        # Query only: never bypass the old global-running unique constraint.
        assert session.scalar(SelectionRunRepository.eligible_pending_statement()) is None
        session.rollback()
        SelectionRunService(session, settings=SETTINGS).finish(claim)
    with Session(context[0]) as session:
        assert session.scalar(SelectionRunRepository.eligible_pending_statement()).run_id == second.execution_run_id
        assert session.get(Run, second.execution_run_id).status == "pending"
        assert session.get(Run, alias.receipt_id).status == "reused"


def test_nonoverlapping_effective_sets_leave_other_shop_eligible(selection_context):
    context, at = selection_context, datetime.now(UTC)
    first = _save(context)
    running = submit(context, context[3][0], at)
    assert _claim(context).run_id == running.execution_run_id
    submit(context, context[3][0], at, first)
    other = _save(context, shop_id=context[3][1])
    pending = submit(context, context[3][1], at)
    submit(context, context[3][1], at, other)
    with Session(context[0]) as session:
        assert session.scalar(SelectionRunRepository.eligible_pending_statement()).run_id == pending.execution_run_id


@pytest.mark.parametrize("mismatch", ["team_id", "request_shop_id", "request_fingerprint"])
def test_invalid_receipt_scope_is_not_a_valid_effective_strategy(selection_context, mismatch):
    context, at = selection_context, datetime.now(UTC)
    strategy = _save(context)
    running = submit(context, context[3][0], at, strategy)
    assert _claim(context).run_id == running.execution_run_id
    with Session(context[0]) as session:
        strategy = SelectionStrategyService(session).save(context[4][0], SelectionStrategyUpdate(**(_config(context, shop_id=context[3][1]).model_dump() | {"expected_version": strategy.version})), strategy_id=strategy.strategy_id)
    pending = submit(context, context[3][1], at)
    alias = submit(context, context[3][1], at, strategy)
    with Session(context[0]) as session:
        # Synthetic malformed link only; formal service never emits this.
        row = session.get(Run, alias.receipt_id)
        setattr(row, mismatch, context[1][1] if mismatch == "team_id" else context[3][0] if mismatch == "request_shop_id" else "f" * 64)
        session.commit()
        assert session.scalar(SelectionRunRepository.eligible_pending_statement()).run_id == pending.execution_run_id


def test_association_first_claim_cannot_read_uncommitted_effective_set(selection_context, monkeypatch):
    context, at = selection_context, datetime.now(UTC)
    strategy = _save(context)
    old = submit(context, context[3][0], at, strategy)
    assert _claim(context).run_id == old.execution_run_id
    with Session(context[0]) as session:
        strategy = SelectionStrategyService(session).save(context[4][0], SelectionStrategyUpdate(**(_config(context, shop_id=context[3][1]).model_dump() | {"expected_version": strategy.version})), strategy_id=strategy.strategy_id)
    pending = submit(context, context[3][1], at)
    acquired, release = Event(), Event()
    original = SelectionRunRepository.lock_execution_decision
    def hold(self, *, wait=False):
        value = original(self, wait=wait)
        if wait and current_thread().name == "association-writer":
            acquired.set()
            assert release.wait(10)
        return value
    monkeypatch.setattr(SelectionRunRepository, "lock_execution_decision", hold)
    receipts, errors = [], []
    def associate():
        try: receipts.append(submit(context, context[3][1], at, strategy))
        except BaseException as error: errors.append(type(error).__name__)
    thread = Thread(target=associate, name="association-writer")
    thread.start()
    try:
        assert acquired.wait(10)
        with Session(context[0]) as session:
            repo = SelectionRunRepository(session)
            # Even max=3 cannot decide while associations are being written.
            # This does not create a second running row on immutable 0044.
            assert repo.claim_next(now=at, lease_until=at + timedelta(seconds=60), max_running=3) is None
            assert session.scalar(repo.eligible_pending_statement()).run_id == pending.execution_run_id
            session.rollback()
    finally:
        release.set()
        thread.join(10)
    assert not thread.is_alive() and errors == []
    assert receipts[0].execution_run_id == pending.execution_run_id
    with Session(context[0]) as session:
        assert session.scalar(SelectionRunRepository.eligible_pending_statement()) is None
        assert session.get(Run, pending.execution_run_id).status == "pending"


def test_claim_first_late_association_blocks_other_pending_strategy(selection_context, monkeypatch):
    context, at = selection_context, datetime.now(UTC)
    strategy = _save(context)
    first = submit(context, context[3][1], at)  # Anonymous B is older.
    other = submit(context, context[3][0], at + timedelta(seconds=1), strategy)
    with Session(context[0]) as session:
        strategy = SelectionStrategyService(session).save(context[4][0], SelectionStrategyUpdate(**(_config(context, shop_id=context[3][1]).model_dump() | {"expected_version": strategy.version})), strategy_id=strategy.strategy_id)
    attempted, done = Event(), Event()
    original = SelectionRunRepository.lock_execution_decision
    def observe(self, *, wait=False):
        if wait and current_thread().name == "late-association": attempted.set()
        return original(self, wait=wait)
    monkeypatch.setattr(SelectionRunRepository, "lock_execution_decision", observe)
    receipts, errors = [], []
    def associate():
        try: receipts.append(submit(context, context[3][1], at, strategy))
        except BaseException as error: errors.append(type(error).__name__)
        finally: done.set()
    with Session(context[0]) as session:
        claim = SelectionRunRepository(session).claim_next(now=at, lease_until=at + timedelta(seconds=60))
        assert claim.run_id == first.execution_run_id
        session.flush()  # One real running row remains legal under 0044.
        thread = Thread(target=associate, name="late-association")
        thread.start()
        try:
            assert attempted.wait(10)
            assert not done.wait(0.1)
        finally:
            session.commit()  # Association waits for the actual claim commit.
            thread.join(10)
    assert not thread.is_alive() and errors == []
    assert receipts[0].execution_run_id == first.execution_run_id
    with Session(context[0]) as session:
        assert session.scalar(SelectionRunRepository.eligible_pending_statement()) is None
        assert session.get(Run, other.execution_run_id).status == "pending"
        assert session.scalar(select(func.count()).select_from(Run).where(Run.status == "running")) == 1


def test_authority_is_rechecked_after_waiting_for_decision_lock(selection_context, monkeypatch):
    context, at = selection_context, datetime.now(UTC)
    strategy = _save(context)
    attempted, done = Event(), Event()
    original = SelectionRunRepository.lock_execution_decision
    def observe(self, *, wait=False):
        if wait and current_thread().name == "waiting-submission": attempted.set()
        return original(self, wait=wait)
    monkeypatch.setattr(SelectionRunRepository, "lock_execution_decision", observe)
    errors = []
    def submit_waiting():
        try: submit(context, context[3][0], at, strategy)
        except BaseException as error: errors.append(getattr(error, "code", type(error).__name__))
        finally: done.set()
    with Session(context[0]) as blocker:
        assert SelectionRunRepository(blocker).lock_execution_decision(wait=True)
        thread = Thread(target=submit_waiting, name="waiting-submission")
        thread.start()
        try:
            assert attempted.wait(10)
            with Session(context[0]) as revoker:
                revoker.execute(delete(TeamShopAccess).where(TeamShopAccess.team_id == context[1][0], TeamShopAccess.shop_id == context[3][0]))
                revoker.commit()
        finally:
            blocker.rollback()
            thread.join(10)
    assert not thread.is_alive() and done.is_set()
    assert errors == ["PRODUCT_SELECTION_STRATEGY_NOT_FOUND"]
    with Session(context[0]) as session:
        assert session.scalar(select(func.count()).select_from(Run).where(Run.team_id == context[1][0])) == 0
