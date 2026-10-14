"""Actual Feature PostgreSQL, synthetic platform only; not production evidence."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import json
import subprocess
import sys

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog
from app.modules.product_selection.basic_contract import SelectionBasicCreate
from app.modules.product_selection.basic_service import SelectionBasicService
from app.modules.product_selection.candidate_service import SelectionCandidateService
from app.modules.product_selection.result_contract import SelectionBlockCommand
from app.modules.product_selection.result_service import SelectionResultService
from app.modules.product_selection.models import (
    ProductSelectionCandidate as Candidate, ProductSelectionObservation as Observation,
    ProductSelectionRun as Run, ProductSelectionResultItem as Item,
)
from app.modules.product_selection.run_service import SelectionRunService
from app.modules.product_selection.exceptions import SelectionObservationNotFoundError, SelectionRunLeaseLostError, SelectionShopUnavailableError
from app.modules.shops.models import Shop
from app.modules.users.models import User
from app.modules.access.service import ActorContextService
from app.platforms.douyin.product_selection import CompassBasicInfo, CompassBadCommentRate, FieldObservation, CompassSelectionBusinessError
from tests.integration.test_postgresql_product_selection import selection_context, _product, _save, _scope, _api_client
from tests.integration.test_postgresql_selection_runs import _input, _resolver, SETTINGS, FakePlatform, _executor, _get
from tests.integration.test_postgresql_selection_windows import _category_tree
from tests.integration.test_postgresql_selection_strategies import _save as strategy_save

pytestmark = pytest.mark.integration


def rank(context, *, product=None, command=None):
    with Session(context[0]) as session:
        receipt = SelectionRunService(session, settings=SETTINGS, resolver=_resolver).submit(context[4][0], command or _input(context))
    _executor(context, FakePlatform(products=(product or _product(),))).execute_available()
    with Session(context[0]) as session:
        item = session.scalar(select(Item).where(Item.execution_run_id == receipt.execution_run_id))
        return receipt, item.observation_id


def basic_submit(context, observation_id, *, key=None, actor=None):
    with Session(context[0]) as session:
        return SelectionBasicService(session, settings=SETTINGS).submit(actor or context[4][0],
            SelectionBasicCreate(observation_id=observation_id, submission_key=key or uuid4()))


def good_basic(product_id):
    return CompassBasicInfo(product_id, FieldObservation("available", ("行业", "末级")),
        FieldObservation("available", datetime(2026, 10, 1).date()),
        FieldObservation("available", CompassBadCommentRate(Decimal(0), "float", 4)))


def test_today_new_and_later_known_are_both_visible_once_with_frozen_batches(selection_context):
    context = selection_context
    first, observation_id = rank(context)
    second, again = rank(context, product=replace(_product(), rank=17))
    assert again == observation_id
    with Session(context[0]) as session:
        service = SelectionResultService(session)
        for scope, expected in (("today_new", 11), ("today_known", 17), ("today", 17), ("all", 17)):
            reads, total, info = service.list(context[4][0], result_scope=scope)
            assert total == 1 and reads[0].rank == expected and info.unknown_discovery_count == 0
        rows, total, info = service.list(context[4][0], receipt_id=first.receipt_id)
        assert total == 1 and rows[0].rank == 11 and rows[0].discovery_state == "new"
        assert rows[0].source_context.business == first.execution.request_conditions.scope
        assert info.detail_state == "recorded"
        assert session.scalar(select(func.count()).select_from(Candidate)) == 1
        assert session.scalar(select(func.count()).select_from(Item)) == 2


def test_default_and_new_filter_select_latest_only_inside_authorized_shop(selection_context):
    context = selection_context
    rank(context)
    other = _input(context, shop_id=context[3][1])
    rank(context, command=other, product=replace(_product(), rank=19))
    with Session(context[0]) as session:
        rows, total, _ = SelectionResultService(session).list(context[4][0], shop_id=context[3][0])
        assert total == 1 and rows[0].rank == 11
        with pytest.raises(SelectionObservationNotFoundError):
            basic_submit(context, rows[0].observation_id, actor=context[4][1])


def test_legacy_is_unknown_not_fake_empty_and_failed_or_empty_batches_are_recorded(selection_context):
    context = selection_context
    _save(context)
    receipt, _ = rank(context)
    with Session(context[0]) as session:
        reads, _, _ = SelectionResultService(session).list(context[4][0], receipt_id=receipt.receipt_id)
        assert reads[0].discovery_state == "unknown"
        old = session.get(Run, receipt.execution_run_id)
        old.result_detail_version = None  # Synthetic pre-migration fixture, not a production repair.
        session.commit()
        reads, total, info = SelectionResultService(session).list(context[4][0], receipt_id=receipt.receipt_id)
        assert reads == [] and total == 0 and info.detail_state == "not_recorded"
    for platform, expected in ((FakePlatform(), "succeeded"), (FakePlatform(rank_error=CompassSelectionBusinessError(details={"platform_code": "621000704"})), "failed")):
        with Session(context[0]) as session:
            value = SelectionRunService(session, settings=SETTINGS, resolver=_resolver).submit(context[4][0], _input(context))
        _executor(context, platform).execute_available()
        with Session(context[0]) as session:
            reads, total, info = SelectionResultService(session).list(context[4][0], receipt_id=value.receipt_id)
            assert not reads and total == 0 and info.detail_state == "recorded"
            assert info.execution.status == expected


def test_reused_strategy_receipt_batch_and_detail_use_only_canonical_members(selection_context):
    context = selection_context
    strategy = strategy_save(context)
    command = _input(context, strategy_id=strategy.strategy_id, strategy_version=strategy.version)
    with Session(context[0]) as session:
        service = SelectionRunService(session, settings=SETTINGS, category_reader=lambda actor, shop: _category_tree(shop))
        first = service.submit(context[4][0], command)
        second = service.submit(context[4][0], command.model_copy(update={"submission_key": uuid4()}))
    assert second.reused and first.execution_run_id == second.execution_run_id
    _executor(context, FakePlatform(products=(_product(),))).execute_available()
    with Session(context[0]) as session:
        service = SelectionResultService(session)
        batches, total = service.batches(context[4][0], strategy.strategy_id)
        assert total == 2 and {row.execution_run_id for row in batches} == {first.execution_run_id}
        assert all(row.visible_item_count == 1 for row in batches)
        rows, total, _ = service.list(context[4][0], strategy_id=strategy.strategy_id, receipt_id=second.receipt_id)
        assert total == 1 and rows[0].result_run_id == first.execution_run_id
        detail = service.get(context[4][0], rows[0].observation_id, receipt_id=second.receipt_id)
        assert detail.rank == rows[0].rank and detail.video_metric_ranges == rows[0].video_metric_ranges
        assert session.scalar(select(func.count()).select_from(Item)) == 1


def test_shanghai_today_is_membership_time_not_receipt_creation_and_unknown_count_is_all_pages(selection_context):
    context = selection_context
    day = datetime.now(UTC)
    for index in range(3):
        rank(context, product=_product(product_id=str(9000000000000000100 + index)))
    with Session(context[0]) as session:
        reader = SelectionResultService(session)
        assert reader.list(context[4][0], result_scope="today", now=day + timedelta(days=1))[1] == 0
        session.execute(update(Run).values(created_at=day - timedelta(days=1)))
        session.commit()
        assert reader.list(context[4][0], result_scope="today", now=day)[1] == 3
        session.execute(update(Item).values(discovery_state="unknown"))  # fixture-only unknown legacy mix
        session.commit()
        reads, total, info = reader.list(context[4][0], result_scope="today", limit=1, now=day)
        assert len(reads) == 1 and total == 3 and info.unknown_discovery_count == 3


def test_block_is_team_product_wide_idempotent_and_does_not_call_platform(selection_context):
    context = selection_context
    _, source = rank(context)
    _, other = rank(context, command=_input(context, shop_id=context[3][1]))
    with Session(context[0]) as session:
        service = SelectionCandidateService(session)
        for _ in range(2):
            assert service.set_blocked(context[4][0], source, SelectionBlockCommand(blocked=True), request_id="stage-2a1-block").blocked
        assert session.scalar(select(func.count()).select_from(AuditLog)) == 1
        reader = SelectionResultService(session)
        assert reader.list(context[4][0])[1] == 0
        assert reader.list(context[4][0], blocked=True, shop_id=context[3][1])[1] == 1
        with pytest.raises(SelectionObservationNotFoundError):
            service.set_blocked(context[4][1], other, SelectionBlockCommand(blocked=False), request_id="stage-2a1-denied")
        session.execute(update(Shop).where(Shop.shop_id == context[3][0]).values(enabled=False))
        session.commit()
        assert not service.set_blocked(context[4][0], source, SelectionBlockCommand(blocked=False), request_id="stage-2a1-restore").blocked
        assert reader.list(context[4][0])[1] == 1


def test_basic_shared_queue_replay_and_current_field_success_preserves_rank_history(selection_context):
    context = selection_context
    original, observation_id = rank(context)
    key = uuid4()
    first = basic_submit(context, observation_id, key=key)
    assert basic_submit(context, observation_id, key=key).receipt_id == first.receipt_id
    reused = basic_submit(context, observation_id)
    assert reused.reused and reused.execution_run_id == first.execution_run_id
    class BasicPlatform(FakePlatform):
        def basic_info(self, context, product_id):
            self.calls.append("basic_info")
            return good_basic(product_id)
    platform = BasicPlatform()
    _executor(context, platform).execute_available()
    assert platform.calls == ["session", "basic_info"]
    with Session(context[0]) as session:
        read = SelectionBasicService(session).get(context[4][0], first.receipt_id)
        assert read.status == "succeeded" and read.saved_count == 0 and read.supplemented_count == 1
        source = session.get(Observation, observation_id)
        assert source.last_run_id == original.execution_run_id and source.bad_comment_rate_raw == 0
        assert source.basic_info_status["bad_comment_rate"]["last_attempt_state"] == "available"
        assert source.basic_info_status["bad_comment_rate"]["last_success_at"] is not None
        assert _get(context, original).status == "partial" and _get(context, original).supplement_failed_count == 1
        assert SelectionRunService(session).list(context[4][0], shop_id=None, offset=0, limit=10)[1] == 1
        assert session.scalar(select(func.count()).select_from(Item)) == 1


@pytest.mark.parametrize("code", [600002, "600002"])
def test_manual_business_failure_keeps_previous_values_and_actual_code_type(selection_context, code):
    context = selection_context
    _, observation_id = rank(context)
    first = basic_submit(context, observation_id)
    with Session(context[0]) as session:
        claim = SelectionRunService(session, settings=SETTINGS).claim_next()
        SelectionBasicService(session).persist(context[4][0], claim, basic=good_basic(claim.request.product_id))
        SelectionRunService(session).finish(claim)
        before = session.get(Observation, observation_id)
        saved_time, metric_time = before.basic_info_retrieved_at, before.metrics_retrieved_at
    second = basic_submit(context, observation_id)
    _executor(context, FakePlatform(basic_error=CompassSelectionBusinessError(details={"platform_code": code}))).execute_available()
    with Session(context[0]) as session:
        read = SelectionBasicService(session).get(context[4][0], second.receipt_id)
        assert read.status == "failed" and type(read.platform_business_code) is type(code)
        source = session.get(Observation, observation_id)
        assert source.bad_comment_rate_raw == 0 and source.category_path == ["行业", "末级"]
        assert source.basic_info_retrieved_at == saved_time and source.metrics_retrieved_at == metric_time
        assert source.basic_info_status["state"] == "failed"
        assert source.basic_info_status["bad_comment_rate"]["last_success_at"] is not None
        assert source.basic_info_status["bad_comment_rate"]["last_attempt_state"] == "unknown"


def test_partial_basic_only_available_fields_change_and_does_not_fix_video_invalid(selection_context):
    context = selection_context
    _, observation_id = rank(context)
    basic_submit(context, observation_id)
    with Session(context[0]) as session:
        claim = SelectionRunService(session, settings=SETTINGS).claim_next()
        result = good_basic(claim.request.product_id)
        result = replace(result, first_on_shelf_date=FieldObservation("null"), bad_comment_rate=FieldObservation("missing"))
        assert SelectionBasicService(session).persist(context[4][0], claim, basic=result)
        assert not SelectionBasicService(session).persist(context[4][0], claim, basic=result)
        SelectionRunService(session).finish(claim)
        source = session.get(Observation, observation_id)
        assert source.category_path == ["行业", "末级"] and source.first_on_shelf_date is None
        assert source.basic_info_status["state"] == "partial"
        assert source.video_metric_ranges["video_cnt"]["state"] == "invalid"


def test_expired_manual_executor_cannot_write_and_disabled_shop_never_submits(selection_context):
    context = selection_context
    _, observation_id = rank(context)
    receipt = basic_submit(context, observation_id)
    with Session(context[0]) as session:
        claim = SelectionRunService(session, settings=SETTINGS).claim_next()
        session.execute(update(Run).where(Run.run_id == receipt.execution_run_id).values(lease_expires_at=datetime.now(UTC) - timedelta(seconds=1)))
        session.commit()
        SelectionRunService(session).recover_expired()
        with pytest.raises(SelectionRunLeaseLostError):
            SelectionBasicService(session).persist(context[4][0], claim, basic=good_basic(claim.request.product_id))
        session.execute(update(Shop).where(Shop.shop_id == context[3][0]).values(enabled=False))
        session.commit()
    with pytest.raises(SelectionShopUnavailableError):
        basic_submit(context, observation_id)


def test_formal_api_block_filters_async_basic_progress_and_scope_are_real(selection_context):
    from app.core.database import get_database_session
    from app.modules.product_selection.api import get_selection_basic_service
    context = selection_context
    receipt, observation_id = rank(context)
    headers = {"X-Team-ID": str(context[1][0])}
    with _api_client(context) as client:
        def basic_dependency():
            with Session(context[0]) as session:
                yield SelectionBasicService(session, settings=SETTINGS)
        client.app.dependency_overrides[get_selection_basic_service] = basic_dependency
        page = client.get('/api/v1/product-selection/candidates', params={"receipt_id":str(receipt.receipt_id)}, headers=headers)
        assert page.status_code == 200 and page.json()["items"][0]["product_id"].isdigit()
        assert page.json()["context"]["detail_state"] == "recorded"
        path = f'/api/v1/product-selection/observations/{observation_id}'
        assert client.patch(path + '/blocked', json={"blocked":True}, headers=headers).json()["blocked"]
        assert client.get('/api/v1/product-selection/candidates', headers=headers).json()["total"] == 0
        assert client.get('/api/v1/product-selection/candidates', params={"blocked":True}, headers=headers).json()["total"] == 1
        body = {"observation_id":str(observation_id), "submission_key":str(uuid4())}
        submitted = client.post('/api/v1/product-selection/basic-info-runs', json=body, headers=headers)
        assert submitted.status_code == 202
        assert client.post('/api/v1/product-selection/basic-info-runs', json=body, headers=headers).json()["receipt_id"] == submitted.json()["receipt_id"]
        assert client.get(path + '/basic-info-run', headers=headers).json()["status"] == "pending"
        _executor(context, FakePlatform(basic_error=CompassSelectionBusinessError(details={"platform_code":"600002"}))).execute_available()
        assert client.get(path + '/basic-info-run', headers=headers).json()["status"] == "failed"
        detail = client.get(path, headers=headers).json()
        assert detail["basic_info_status"]["platform_business_code"] == "600002"
        assert detail["last_run_id"] == str(receipt.execution_run_id)
    with _api_client(context, actor_index=1) as client:
        assert client.patch(path + '/blocked', json={"blocked":False}, headers={"X-Team-ID":str(context[1][1])}).status_code == 404


def test_manual_and_rank_share_three_slots_and_skip_busy_shop(selection_context):
    from app.core.config import Settings
    from app.modules.product_selection.run_executor import SelectionRunExecutor
    context = selection_context
    _, observation_id = rank(context)
    basic = basic_submit(context, observation_id)
    with Session(context[0]) as session:
        settings = Settings(product_selection_execution_enabled=True, product_selection_concurrency=3)
        service = SelectionRunService(session, settings=settings, resolver=_resolver)
        same = service.submit(context[4][0], _input(context))
        other = service.submit(context[4][0], _input(context, shop_id=context[3][1]))
        first = service.claim_next()
        second = service.claim_next()
        assert first.run_id == basic.execution_run_id and second.run_id == other.execution_run_id
        assert service.claim_next() is None  # same Shop waits even though global capacity remains
        SelectionBasicService(session).persist(context[4][0], first, basic=good_basic(first.request.product_id))
        service.finish(first)
        third = service.claim_next()
        assert third.run_id == same.execution_run_id
        assert session.scalar(select(func.count()).select_from(Run).where(Run.status == 'running')) == 2
        service.finish(second, error=CompassSelectionBusinessError(details={"platform_code":"synthetic"}))
        service.finish(third, error=CompassSelectionBusinessError(details={"platform_code":"synthetic"}))


def test_basic_and_rank_claims_are_limited_across_independent_python_processes(selection_context):
    context = selection_context
    _, observation_id = rank(context)
    basic = basic_submit(context, observation_id)
    with Session(context[0]) as session:
        service = SelectionRunService(session, settings=SETTINGS, resolver=_resolver)
        waiting = service.submit(context[4][0], _input(context))
        other = service.submit(context[4][0], _input(context, shop_id=context[3][1]))
    # No platform adapter or credentials on argv. Each process loads the same
    # protected config, verifies the exact Feature target, and only claims.
    code = '''
import json,os,time
try:
 from app.core.config import get_settings,Settings
 from app.core.database import get_database_engine
 from app.modules.product_selection.run_service import SelectionRunService
 from sqlalchemy.engine import make_url
 from sqlalchemy.orm import Session
 url=make_url(str(get_settings().database_url))
 assert (url.database,url.username,url.host,url.port)==("control_center_feat_product_selection","control_center_dev_user","127.0.0.1",35433)
 engine=get_database_engine();engine.hide_parameters=True
 claim=None
 for _ in range(20):
  with Session(engine) as session:
   claim=SelectionRunService(session,settings=Settings(product_selection_execution_enabled=True,product_selection_concurrency=3)).claim_next()
  if claim is not None:break
  time.sleep(0.05)
 print(json.dumps({"pid":os.getpid(),"run":str(claim.run_id) if claim else None,"shop":str(claim.shop_id) if claim else None}))
except Exception as failure:
 print(json.dumps({"error_type":type(failure).__name__}))
'''
    def probe():
        result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=30)
        assert result.returncode == 0
        return json.loads(result.stdout)
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: probe(), range(2)))
    assert len({row['pid'] for row in results}) == 2
    assert {row['run'] for row in results} == {str(basic.execution_run_id), str(other.execution_run_id)}
    with Session(context[0]) as session:
        assert session.get(Run, waiting.execution_run_id).status == 'pending'
        assert session.scalar(select(func.count()).select_from(Run).where(Run.status=='running')) == 2


def test_disabled_after_basic_enqueue_has_zero_external_calls(selection_context):
    context = selection_context
    _, observation_id = rank(context)
    receipt = basic_submit(context, observation_id)
    with Session(context[0]) as session:
        session.get(Shop, context[3][0]).enabled = False
        session.commit()
    platform = FakePlatform()
    _executor(context, platform).execute_available()
    assert platform.calls == []
    with Session(context[0]) as session:
        read = SelectionBasicService(session).get(context[4][0], receipt.receipt_id)
        assert read.status == 'failed' and read.error_stage == 'authorization'
        assert session.get(Observation, observation_id).last_run_id != receipt.execution_run_id


def test_verified_super_uses_saved_candidate_team_without_switch_and_forged_flag_is_denied(selection_context):
    context = selection_context
    _, observation_id = rank(context)
    with Session(context[0]) as session:
        session.get(User, context[2][1]).is_super_account = True
        session.commit()
        for requested_team in (None, context[1][1]):
            actor = ActorContextService(session).resolve(user_id=context[2][1], requested_team_id=requested_team)
            read = SelectionCandidateService(session).set_blocked(actor, observation_id, SelectionBlockCommand(blocked=True), request_id='stage-2a1-super')
            assert read.blocked
            receipt = SelectionBasicService(session, settings=SETTINGS).submit(actor,
                SelectionBasicCreate(observation_id=observation_id, submission_key=uuid4()))
            assert receipt.execution.team_id == context[1][0]
            assert actor.team_id == requested_team  # never modifies the global context
        session.get(User, context[2][1]).is_super_account = False
        session.commit()
        forged = replace(context[4][1], is_super_account=True)
        with pytest.raises(SelectionObservationNotFoundError):
            SelectionCandidateService(session).set_blocked(forged, observation_id, SelectionBlockCommand(blocked=False), request_id='stage-2a1-forged')
