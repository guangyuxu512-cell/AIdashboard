from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.modules.product_selection.models import ProductSelectionRun as Run
from app.modules.product_selection.request_mapping import freeze_short_video_request
from app.modules.product_selection.run_contract import SelectionResolvedRequest
from app.modules.product_selection.run_service import SelectionRunService
from tests.integration.test_postgresql_product_selection import selection_context
from tests.integration.test_postgresql_selection_runs import _input, SETTINGS
from tests.integration.test_postgresql_selection_windows import _category_tree
from tests.integration.test_postgresql_selection_strategies import _save

pytestmark = pytest.mark.integration


def test_new_submission_reuses_active_legacy_v2_without_rewriting_canonical(selection_context):
    context = selection_context
    def legacy(original, now):
        raw = freeze_short_video_request(original, now).model_dump(mode="json")
        return SelectionResolvedRequest.model_validate(raw | {"version": 2, "strategy": None})
    with Session(context[0]) as session:
        old = SelectionRunService(session, settings=SETTINGS, resolver=legacy, category_reader=lambda actor, shop: _category_tree(shop)).submit(context[4][0], _input(context, rank_from=1, rank_to=20))
    strategy = _save(context)
    command = _input(context, rank_from=1, rank_to=20, strategy_id=strategy.strategy_id, strategy_version=strategy.version)
    with Session(context[0]) as session:
        service = SelectionRunService(session, settings=SETTINGS, category_reader=lambda actor, shop: _category_tree(shop))
        fresh = service.submit(context[4][0], command)
        assert fresh.reused and fresh.execution_run_id == old.execution_run_id
        assert fresh.strategy.strategy_id == strategy.strategy_id
        canonical = session.get(Run, old.execution_run_id)
        assert canonical.strategy_id is None and canonical.request_conditions["version"] == 2
        assert session.get(Run, fresh.receipt_id).request_conditions["version"] == 3
        assert service.submit(context[4][0], command).receipt_id == fresh.receipt_id
        assert session.scalar(select(func.count()).select_from(Run).where(Run.team_id == context[1][0], Run.status == "pending")) == 1


def test_same_key_replays_v2_before_category_io_but_new_day_does_not_reuse_old_window(selection_context):
    context = selection_context
    accepted = datetime(2026, 10, 31, 12, tzinfo=UTC)
    command = _input(context, rank_from=1, rank_to=20)
    def legacy(original, now):
        return SelectionResolvedRequest.model_validate(freeze_short_video_request(original, now).model_dump(mode="json") | {"version": 2, "strategy": None})
    with Session(context[0]) as session:
        old = SelectionRunService(session, settings=SETTINGS, resolver=legacy, category_reader=lambda actor, shop: _category_tree(shop)).submit(context[4][0], command, now=accepted)
    with Session(context[0]) as session:
        service = SelectionRunService(session, settings=SETTINGS, category_reader=lambda *_: pytest.fail("Replayed keys must not read categories"))
        replay = service.submit(context[4][0], command, now=accepted + timedelta(days=1))
        assert replay.receipt_id == old.receipt_id
        assert replay.execution.request_conditions == old.execution.request_conditions
    with Session(context[0]) as session:
        newer = SelectionRunService(session, settings=SETTINGS, category_reader=lambda actor, shop: _category_tree(shop)).submit(context[4][0], _input(context, rank_from=1, rank_to=20), now=accepted + timedelta(days=1))
        assert not newer.reused and newer.execution_run_id != old.execution_run_id
        assert newer.execution.request_conditions.scope != old.execution.request_conditions.scope
