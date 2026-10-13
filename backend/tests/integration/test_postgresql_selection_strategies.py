"""Registered Feature PostgreSQL + synthetic I/O, never live platform evidence."""

from dataclasses import replace
from threading import Barrier, Thread
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.modules.access.exceptions import TeamContextRequiredError
from app.modules.access.models import TeamShopAccess
from app.modules.access.repository import AccessManagementRepository
from app.modules.product_selection.exceptions import SelectionRunConflictError, SelectionStrategyNotFoundError, SelectionStrategyVersionConflictError, SelectionShopUnavailableError, SelectionStrategyWriteDisabledError
from app.modules.product_selection.models import ProductSelectionRun as Run, ProductSelectionStrategy as Strategy, ProductSelectionCandidate as Candidate, ProductSelectionObservation as Observation
from app.modules.product_selection.run_contract import SelectionRunCreate, SelectionResolvedRequest
from app.modules.product_selection.run_service import SelectionRunService
from app.modules.product_selection.strategy_contract import SelectionStrategyCreate, SelectionStrategyUpdate, SelectionStrategyToggle
from app.modules.product_selection.strategy_service import SelectionStrategyService
from app.modules.shops.models import Shop
from app.modules.users.models import User
from app.modules.access.service import ActorContextService
from app.platforms.douyin.product_selection import CompassRankPage
from tests.integration.test_postgresql_product_selection import selection_context, _product, _api_client
from tests.integration.test_postgresql_selection_runs import _input, _executor, _get, SETTINGS
from tests.integration.test_postgresql_selection_windows import _category_tree, WindowPlatform

pytestmark = pytest.mark.integration


def _config(context, **changes):
    return SelectionStrategyCreate.model_validate({
        "name": "stage-2a1 真实保存的合成策略", "shop_id": context[3][0], "enabled": True,
        "conditions": {"version": 1, "request": _input(context, rank_from=1, rank_to=25).original().model_dump(exclude={"shop_id"}, mode="json")},
        "schedule": {"scheduled": True, "kind": "daily", "daily_time": "09:00", "timezone": "Asia/Shanghai"},
        **changes,
    })


def _save(context, **changes):
    with Session(context[0]) as session:
        return SelectionStrategyService(session).save(context[4][0], _config(context, **changes))


def _submit(context, strategy, **changes):
    command = _input(context, rank_from=1, rank_to=25, strategy_id=strategy.strategy_id, strategy_version=strategy.version, **changes)
    with Session(context[0]) as session:
        return SelectionRunService(session, settings=SETTINGS, category_reader=lambda actor, shop: _category_tree(shop)).submit(context[4][0], command)


def test_crud_refresh_edit_cas_toggle_do_not_submit_or_fetch(selection_context, monkeypatch):
    context = selection_context
    from app.modules.product_selection import platform_io
    monkeypatch.setattr(platform_io.SelectionStoredSessionIO, "session_context", lambda *_: pytest.fail("Saving must not load Session or request the platform"))
    with _api_client(context) as client:
        headers = {"X-Team-ID": str(context[1][0])}
        created = client.post("/api/v1/product-selection/strategies", json=_config(context).model_dump(mode="json"), headers=headers)
        assert created.status_code == 201
        dto = created.json()
        assert dto["version"] == 1 and dto["latest_run"] is None
        assert not dto["schedule_available"] and dto["next_run_at"] is None
        assert dto["conditions"]["request"]["period"] == "7d"
        assert "begin_date" not in str(dto["conditions"])
        path = f'/api/v1/product-selection/strategies/{dto["strategy_id"]}'
        assert client.get(path, headers=headers).json() == dto
        page = client.get("/api/v1/product-selection/strategies", params={"page_size": 10}, headers=headers).json()
        assert page["total"] == 1 and page["items"][0] == dto
        edited = client.put(path, headers=headers, json=_config(context, name="stage-2a1 已保存编辑").model_dump(mode="json") | {"expected_version": 1})
        assert edited.status_code == 200 and edited.json()["version"] == 2
        conflict = client.put(path, headers=headers, json=_config(context, name="不得覆盖").model_dump(mode="json") | {"expected_version": 1})
        assert conflict.status_code == 409 and conflict.json()["code"] == "PRODUCT_SELECTION_STRATEGY_VERSION_CONFLICT"
        toggled = client.patch(path + "/enabled", headers=headers, json={"enabled": False, "expected_version": 2})
        assert toggled.json()["enabled"] is False and toggled.json()["version"] == 3
        assert client.get(path, headers=headers).json()["name"] == "stage-2a1 已保存编辑"
    with Session(context[0]) as session:
        assert session.scalar(select(func.count()).select_from(Run).where(Run.team_id == context[1][0])) == 0


def test_read_only_management_switch_keeps_saved_config_and_denies_all_writes(selection_context):
    from app.core.config import Settings
    context = selection_context
    saved = _save(context)
    with Session(context[0]) as session:
        reader = SelectionStrategyService(session, settings=Settings(product_selection_strategy_management_enabled=False, product_selection_execution_enabled=False))
        assert reader.get(context[4][0], saved.strategy_id).version == 1
        assert reader.list(context[4][0], offset=0, limit=10)[1] == 1
        with pytest.raises(SelectionStrategyWriteDisabledError): reader.save(context[4][0], _config(context))
        with pytest.raises(SelectionStrategyWriteDisabledError): reader.save(context[4][0], SelectionStrategyUpdate(**(_config(context).model_dump() | {"expected_version": 1})), strategy_id=saved.strategy_id)
        with pytest.raises(SelectionStrategyWriteDisabledError): reader.toggle(context[4][0], saved.strategy_id, SelectionStrategyToggle(enabled=False, expected_version=1))
        assert reader.get(context[4][0], saved.strategy_id).enabled is True


def test_scope_before_pagination_direct_ids_and_revocation(selection_context):
    context = selection_context
    saved = _save(context)
    with Session(context[0]) as session:
        service = SelectionStrategyService(session)
        assert service.list(context[4][1], offset=0, limit=10)[1] == 0
        with pytest.raises(SelectionStrategyNotFoundError): service.get(context[4][1], saved.strategy_id)
        session.execute(delete(TeamShopAccess).where(TeamShopAccess.team_id == context[1][0]))
        session.commit()
        assert service.list(context[4][0], offset=0, limit=10)[1] == 0
        with pytest.raises(SelectionStrategyNotFoundError): service.get(context[4][0], saved.strategy_id)


def test_current_super_account_needs_explicit_team_for_new_strategy(selection_context):
    context = selection_context
    with Session(context[0]) as session:
        session.get(User, context[2][0]).is_super_account = True
        session.commit()
        global_actor = ActorContextService(session).resolve(user_id=context[2][0], requested_team_id=None)
        with pytest.raises(TeamContextRequiredError): SelectionStrategyService(session).save(global_actor, _config(context))


@pytest.mark.parametrize("other_team", [False, True])
def test_existing_super_strategy_operations_use_saved_team_without_switch(selection_context, other_team):
    context = selection_context
    saved = _save(context)
    with Session(context[0]) as session:
        session.get(User, context[2][0]).is_super_account = True
        session.commit()
    headers = {"X-Team-ID": str(context[1][1])} if other_team else {}
    path = f"/api/v1/product-selection/strategies/{saved.strategy_id}"
    with _api_client(context) as client:
        edited = client.put(path, headers=headers, json=_config(context, name="stage-2a1 resource team").model_dump(mode="json") | {"expected_version": 1})
        assert edited.status_code == 200
        assert edited.json()["team_id"] == str(context[1][0])
        assert client.get(path, headers=headers).json()["version"] == 2
        closed = client.patch(path + "/enabled", headers=headers, json={"enabled": False, "expected_version": 2})
        assert closed.status_code == 200 and closed.json()["enabled"] is False
        assert client.get(path, headers=headers).json()["enabled"] is False
        opened = client.patch(path + "/enabled", headers=headers, json={"enabled": True, "expected_version": 3})
        assert opened.status_code == 200 and opened.json()["version"] == 4
    with Session(context[0]) as session:
        actor = ActorContextService(session).resolve(user_id=context[2][0], requested_team_id=context[1][1] if other_team else None)
        observed_teams = []
        service = SelectionRunService(session, settings=SETTINGS, category_reader=lambda current, shop: (observed_teams.append(current.team_id) or _category_tree(shop)))
        command = _input(context, rank_from=21, rank_to=30, strategy_id=saved.strategy_id, strategy_version=4)
        receipt = service.submit(actor, command)
        assert service.submit(actor, command).receipt_id == receipt.receipt_id
        assert observed_teams == [context[1][0]]
        stored = session.get(Strategy, saved.strategy_id)
        assert stored.version == 4 and stored.conditions["request"]["rank_from"] == 1
        assert session.get(Run, receipt.receipt_id).team_id == context[1][0]
        assert SelectionStrategyService(session).get(actor, saved.strategy_id).latest_run.run_id == receipt.execution_run_id
        with pytest.raises(TeamContextRequiredError):
            service.submit(replace(actor, team_id=None), _input(context))


def test_resource_team_binding_rechecks_super_authority_after_category_io(selection_context):
    context = selection_context
    saved = _save(context)
    with Session(context[0]) as session:
        session.get(User, context[2][0]).is_super_account = True
        session.commit()
        actor = ActorContextService(session).resolve(user_id=context[2][0], requested_team_id=None)
        def revoke_super(current, shop):
            with Session(context[0]) as write:
                write.get(User, current.user_id).is_super_account = False
                write.execute(delete(TeamShopAccess).where(TeamShopAccess.team_id == context[1][0]))
                write.commit()
            return _category_tree(shop)
        with pytest.raises(SelectionStrategyNotFoundError):
            SelectionRunService(session, settings=SETTINGS, category_reader=revoke_super).submit(actor, _input(context, strategy_id=saved.strategy_id, strategy_version=1))
        assert session.scalar(select(func.count()).select_from(Run).where(Run.team_id == context[1][0])) == 0


def test_only_strategy_still_prevents_team_deletion(selection_context):
    from tests.integration.test_postgresql_product_selection import _remove_team_grants_and_membership
    context = selection_context
    _save(context)
    _remove_team_grants_and_membership(context)
    with Session(context[0]) as session:
        assert session.scalar(select(func.count()).select_from(Run).where(Run.team_id == context[1][0])) == 0
        assert session.scalar(select(func.count()).select_from(Candidate).where(Candidate.team_id == context[1][0])) == 0
        assert AccessManagementRepository(session).team_has_references(context[1][0])


def test_recent_run_is_hidden_after_editing_shop_and_revoking_old_shop(selection_context):
    context = selection_context
    saved = _save(context)
    _submit(context, saved)
    with Session(context[0]) as session:
        service = SelectionStrategyService(session)
        update = SelectionStrategyUpdate(**(_config(context, shop_id=context[3][1]).model_dump() | {"expected_version": 1}))
        service.save(context[4][0], update, strategy_id=saved.strategy_id)
        assert service.get(context[4][0], saved.strategy_id).latest_run is not None
        session.execute(delete(TeamShopAccess).where(TeamShopAccess.team_id == context[1][0], TeamShopAccess.shop_id == context[3][0]))
        session.commit()
        assert service.get(context[4][0], saved.strategy_id).latest_run is None


def test_disabled_shop_cannot_write_or_execute_and_strategy_retains_team(selection_context):
    context = selection_context
    saved = _save(context)
    with Session(context[0]) as session:
        assert AccessManagementRepository(session).team_has_references(context[1][0])
        session.get(Shop, context[3][0]).enabled = False
        session.commit()
        service = SelectionStrategyService(session)
        # Historical saved configuration remains readable; no new execution.
        assert service.get(context[4][0], saved.strategy_id).name == saved.name
        with pytest.raises(SelectionShopUnavailableError): service.toggle(context[4][0], saved.strategy_id, SelectionStrategyToggle(enabled=True, expected_version=1))
    with pytest.raises(SelectionShopUnavailableError): _submit(context, saved)


def test_disabled_shop_can_be_closed_without_bypassing_authority_or_cas(selection_context, monkeypatch):
    from app.modules.product_selection import platform_io
    context = selection_context
    saved = _save(context)
    monkeypatch.setattr(platform_io.SelectionStoredSessionIO, "session_context", lambda *_: pytest.fail("Closing configuration must not read Session or request the platform"))
    with Session(context[0]) as session:
        session.get(Shop, context[3][0]).enabled = False
        session.commit()
    headers = {"X-Team-ID": str(context[1][0])}
    path = f"/api/v1/product-selection/strategies/{saved.strategy_id}/enabled"
    with _api_client(context) as client:
        closed = client.patch(path, headers=headers, json={"enabled": False, "expected_version": 1})
        assert closed.status_code == 200
        assert closed.json()["enabled"] is False and closed.json()["version"] == 2
        stale = client.patch(path, headers=headers, json={"enabled": False, "expected_version": 1})
        assert stale.status_code == 409 and stale.json()["code"] == "PRODUCT_SELECTION_STRATEGY_VERSION_CONFLICT"
        reopened = client.patch(path, headers=headers, json={"enabled": True, "expected_version": 2})
        assert reopened.status_code == 409 and reopened.json()["code"] == "PRODUCT_SELECTION_SHOP_UNAVAILABLE"
        assert client.patch(f"/api/v1/product-selection/strategies/{uuid4()}/enabled", headers=headers, json={"enabled": False, "expected_version": 2}).status_code == 404
    with _api_client(context, actor_index=1) as client:
        assert client.patch(path, headers={"X-Team-ID": str(context[1][1])}, json={"enabled": False, "expected_version": 2}).status_code == 404
    with Session(context[0]) as session:
        session.execute(delete(TeamShopAccess).where(TeamShopAccess.team_id == context[1][0], TeamShopAccess.shop_id == context[3][0]))
        session.commit()
    with _api_client(context) as client:
        assert client.patch(path, headers=headers, json={"enabled": False, "expected_version": 2}).status_code == 404
    with Session(context[0]) as session:
        stored = session.get(Strategy, saved.strategy_id)
        assert stored.enabled is False and stored.version == 2
        assert session.scalar(select(func.count()).select_from(Run).where(Run.team_id == context[1][0])) == 0


def test_edit_can_replace_disabled_shop_with_authorized_enabled_shop(selection_context, monkeypatch):
    from app.modules.product_selection import platform_io
    context = selection_context
    saved = _save(context)
    monkeypatch.setattr(platform_io.SelectionStoredSessionIO, "session_context", lambda *_: pytest.fail("Editing configuration must not read Session or request the platform"))
    with Session(context[0]) as session:
        session.get(Shop, context[3][0]).enabled = False
        session.commit()
    path = f"/api/v1/product-selection/strategies/{saved.strategy_id}"
    headers = {"X-Team-ID": str(context[1][0])}
    with _api_client(context) as client:
        # Create/save still validate the newly submitted target. A disabled
        # target is only permitted for the dedicated close-only operation.
        invalid = client.put(path, headers=headers, json=_config(context).model_dump(mode="json") | {"expected_version": 1})
        assert invalid.status_code == 409 and invalid.json()["code"] == "PRODUCT_SELECTION_SHOP_UNAVAILABLE"
        edited = client.put(path, headers=headers, json=_config(context, shop_id=context[3][1]).model_dump(mode="json") | {"expected_version": 1})
        assert edited.status_code == 200
        assert edited.json()["shop_id"] == str(context[3][1]) and edited.json()["version"] == 2
        assert client.get(path, headers=headers).json()["shop_id"] == str(context[3][1])
    with Session(context[0]) as session:
        assert session.scalar(select(func.count()).select_from(Run).where(Run.team_id == context[1][0])) == 0


def test_concurrent_edit_has_one_winner_and_does_not_reset_version(selection_context):
    context, barrier, results = selection_context, Barrier(2), []
    saved = _save(context)
    def edit(name):
        with Session(context[0]) as session:
            barrier.wait()
            try:
                result = SelectionStrategyService(session).save(context[4][0], SelectionStrategyUpdate(**(_config(context, name=name).model_dump() | {"expected_version": 1})), strategy_id=saved.strategy_id)
                results.append(result.version)
            except SelectionStrategyVersionConflictError:
                results.append("conflict")
    threads = [Thread(target=edit, args=(f"stage-2a1 edit-{n}",)) for n in range(2)]
    for thread in threads: thread.start()
    for thread in threads: thread.join(timeout=20)
    assert sorted(results, key=str) == [2, "conflict"]


def test_retrieve_freezes_strategy_draft_without_saving_and_reused_result_is_visible(selection_context):
    context = selection_context
    first, second = _save(context), _save(context, name="stage-2a1 另一策略")
    receipt = _submit(context, first, first_listed_only=True)
    reused = _submit(context, second, first_listed_only=True)
    assert reused.reused and reused.execution_run_id == receipt.execution_run_id
    assert reused.strategy.strategy_id == second.strategy_id
    assert receipt.strategy.strategy_id == first.strategy_id
    with Session(context[0]) as session:
        canonical = session.get(Run, receipt.execution_run_id)
        assert canonical.strategy_id == first.strategy_id
        other = session.get(Run, reused.receipt_id)
        assert other.strategy_id == second.strategy_id and other.saved_count == 0
        assert SelectionResolvedRequest.model_validate(other.request_conditions).strategy.strategy_id == second.strategy_id
        assert SelectionStrategyService(session).get(context[4][0], first.strategy_id).conditions.request.first_listed_only is False
        assert SelectionStrategyService(session).get(context[4][0], second.strategy_id).latest_run.run_id == receipt.execution_run_id
        changed = _config(context, name="stage-2a1 后改名称")
        SelectionStrategyService(session).save(context[4][0], SelectionStrategyUpdate(**(changed.model_dump() | {"expected_version": 1})), strategy_id=first.strategy_id)
        assert session.get(Run, receipt.execution_run_id).request_conditions["strategy"]["version"] == 1


def test_same_submission_cannot_switch_strategy_and_unsaved_run_does_not_create_strategy(selection_context):
    context = selection_context
    first, second = _save(context), _save(context, name="stage-2a1 第二策略")
    key = uuid4()
    _submit(context, first, submission_key=key)
    with pytest.raises(SelectionRunConflictError): _submit(context, second, submission_key=key)
    with Session(context[0]) as session:
        receipt = SelectionRunService(session, settings=SETTINGS, category_reader=lambda actor, shop: _category_tree(shop)).submit(context[4][0], _input(context, rank_from=1, rank_to=25))
        assert receipt.reused
        assert session.get(Run, receipt.receipt_id).strategy_id is None
        assert session.scalar(select(func.count()).select_from(Strategy).where(Strategy.team_id == context[1][0])) == 2


def test_rank_beyond_twenty_and_platform_first_listed_filter_do_not_use_local_first_seen(selection_context):
    context = selection_context
    saved = _save(context)
    receipt = _submit(context, saved, first_listed_only=True)
    new = replace(_product(product_id="9000000000000000025", rank=25), newly_on_ranking=True)
    not_new = replace(_product(product_id="9000000000000000024", rank=24), newly_on_ranking=False)
    platform = WindowPlatform(receipt.execution.request_conditions, {
        ("primary", 1): CompassRankPage((replace(_product(rank=1), newly_on_ranking=False),), 1, 10, 25),
        ("primary", 2): CompassRankPage((replace(_product(rank=11), newly_on_ranking=False),), 2, 10, 25),
        ("primary", 3): CompassRankPage((not_new, new), 3, 10, 25),
    })
    _executor(context, platform).execute_available()
    run = _get(context, receipt)
    assert run.status == "succeeded" and run.saved_count == 1
    assert platform.rank_calls == [("primary", 1), ("primary", 2), ("primary", 3)]
    with Session(context[0]) as session:
        row = session.scalar(select(Observation).where(Observation.last_run_id == run.run_id))
        assert row.rank == 25 and row.newly_on_ranking is True
        assert row.source_context["version"] == 2 and row.source_context["first_listed_only"] is True


def test_unknown_first_listed_flag_is_not_an_empty_success(selection_context):
    context = selection_context
    saved = _save(context)
    receipt = _submit(context, saved, first_listed_only=True)
    platform = WindowPlatform(receipt.execution.request_conditions, {("primary", 1): (_product(rank=1),)})
    _executor(context, platform).execute_available()
    run = _get(context, receipt)
    assert run.status == "failed" and run.result_count is None and run.error_stage == "response_parse"
    assert platform.rank_calls == [("primary", 1)]
