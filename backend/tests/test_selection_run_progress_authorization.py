"""Method-only authorization interleavings: no Settings, DB or platform I/O."""

from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.product_selection.exceptions import SelectionRunNotFoundError
from app.modules.product_selection.request_mapping import freeze_short_video_request
from app.modules.product_selection.run_contract import SelectionRunOriginal
from app.modules.product_selection.run_service import SelectionRunService
from app.modules.product_selection.run_repository import SelectionRunRepository


def _context(*, reused=False):
    team, shop, user = uuid4(), uuid4(), uuid4()
    before = ActorContext(user, "synthetic-super", uuid4(), None, "super_account", DataScope.ALL, True)
    after = replace(before, team_id=team, membership_id=uuid4(), role_code="member", data_scope=DataScope.TEAM, is_super_account=False)
    at = datetime(2026, 10, 13, 1, tzinfo=UTC)
    request = freeze_short_video_request(SelectionRunOriginal(
        shop_id=shop, channel="short-video", period="7d", industry_id="7",
        category_ids=("1000009092", "1000009142"), rank_from=1, rank_to=10,
        brand="all", price_mode="all",
    ), at)
    canonical = SimpleNamespace(
        operation_kind="rank", target_observation_id=None, result_detail_version=None,
        run_id=uuid4(), team_id=team, created_by_user_id=user,
        request_shop_id=shop, strategy_id=None, reused_run_id=None,
        request_fingerprint=request.fingerprint(), request_conditions=request.model_dump(mode="json"),
        status="pending", stage="queued", result_count=None, saved_count=0,
        supplemented_count=0, supplement_failed_count=0, error_code=None,
        error_stage=None, platform_business_code=None, started_at=None,
        finished_at=None, created_at=at, updated_at=at,
    )
    row = SimpleNamespace(**(vars(canonical) | {
        "run_id": uuid4(), "reused_run_id": canonical.run_id, "status": "reused",
    })) if reused else canonical
    return before, after, row, canonical


def _service(before, after, visible):
    # Bypass only construction: production get/_read and DTO validation execute.
    # A concrete Session or Settings must never be created by this unit test.
    service = object.__new__(SelectionRunService)
    service.facts = SimpleNamespace(_current_actor=Mock(side_effect=[before, after]))
    service.repository = SimpleNamespace(get_for_actor=Mock(side_effect=visible), validated_request=SelectionRunRepository.validated_request)
    return service


@pytest.mark.parametrize("reused", [False, True])
def test_super_revoked_between_lookup_and_resource_resolve_rechecks_shop_visibility(reused):
    before, after, row, _ = _context(reused=reused)
    service = _service(before, after, lambda actor, _: row if actor.is_super_account else None)
    with pytest.raises(SelectionRunNotFoundError):
        service.get(before, row.run_id)
    calls = service.repository.get_for_actor.call_args_list
    assert len(calls) == 2
    assert calls[0].args[0].is_super_account and calls[0].args[0].team_id is None
    assert calls[1].args == (after, row.run_id)


@pytest.mark.parametrize("reused", [False, True])
def test_fresh_authorized_member_can_read_after_super_is_revoked(reused):
    before, after, row, canonical = _context(reused=reused)

    def visible(actor, run_id):
        assert actor.is_super_account or actor == after
        return row if run_id == row.run_id else canonical

    service = _service(before, after, visible)
    result = service.get(before, row.run_id)
    assert result.run_id == canonical.run_id
    calls = service.repository.get_for_actor.call_args_list
    assert calls[1].args == (after, row.run_id)
    if reused:
        assert calls[2].args == (after, canonical.run_id)


def test_still_super_uses_saved_run_team_for_second_visible_lookup():
    before, member, row, _ = _context()
    after = replace(before, team_id=member.team_id)
    service = _service(before, after, lambda actor, _: row)
    assert service.get(before, row.run_id).run_id == row.run_id
    assert service.repository.get_for_actor.call_args_list[1].args == (after, row.run_id)


def test_initial_normal_member_never_uses_cross_team_super_lookup():
    _, after, row, _ = _context()
    service = _service(after, after, lambda actor, _: None)
    with pytest.raises(SelectionRunNotFoundError):
        service.get(after, row.run_id)
    service.facts._current_actor.assert_called_once_with(after)
    service.repository.get_for_actor.assert_called_once_with(after, row.run_id)
