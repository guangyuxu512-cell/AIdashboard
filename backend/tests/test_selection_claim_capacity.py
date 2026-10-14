"""Pure allocator SQL boundaries; actual 0045 concurrency is verified separately in PG."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from app.modules.product_selection.run_repository import SelectionRunRepository


def test_selection_only_allocator_is_transaction_scoped_and_leaves_busy_pending():
    session = MagicMock()
    session.scalar.side_effect = [False]
    at = datetime.now(UTC)
    assert SelectionRunRepository(session).claim_next(now=at, lease_until=at + timedelta(seconds=60), max_running=3) is None
    statement = session.scalar.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "pg_try_advisory_xact_lock" in sql and "product_selection_run_claim" in sql
    assert not session.commit.called and not session.rollback.called and not session.execute.called


def test_capacity_does_not_claim_or_mark_waiting_rows_failed():
    session = MagicMock()
    session.scalar.side_effect = [True, 3]
    at = datetime.now(UTC)
    assert SelectionRunRepository(session).claim_next(now=at, lease_until=at + timedelta(seconds=60), max_running=3) is None
    assert session.scalar.call_count == 2
    assert not session.commit.called


def test_query_skips_busy_shop_and_effective_strategy_uses_row_lock_order():
    statement = SelectionRunRepository.eligible_pending_statement()
    sql = str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "FOR UPDATE SKIP LOCKED" in sql and "ORDER BY product_selection_runs.created_at" in sql
    assert sql.count("NOT (EXISTS") == 2
    assert "request_shop_id = product_selection_runs.request_shop_id" in sql
    assert "running_submission.strategy_id = candidate_submission.strategy_id" in sql
    assert "coalesce(candidate_submission.reused_run_id, candidate_submission.run_id) = product_selection_runs.run_id" in sql
    assert "coalesce(running_submission.reused_run_id, running_submission.run_id) = running_execution.run_id" in sql
    assert "reused_run_id" in sql and "IS NULL" in sql
    assert "'pending'" in sql and "'running'" in sql
    assert "devices" not in sql and "operating_data" not in sql


@pytest.mark.parametrize("capacity", [0, -1, True, 1.5])
def test_invalid_capacity_never_reaches_database(capacity):
    session = MagicMock()
    at = datetime.now(UTC)
    with pytest.raises(ValueError):
        SelectionRunRepository(session).claim_next(now=at, lease_until=at, max_running=capacity)
    assert not session.scalar.called
