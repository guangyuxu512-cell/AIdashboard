"""Pure projection priority/sanitization; database access/authorization tested separately."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.product_selection.models import ProductSelectionRun as Run
from app.modules.product_selection.run_contract import SelectionStrategySnapshot
from app.modules.product_selection.request_mapping import freeze_short_video_request
from app.modules.product_selection.strategy_repository import StrategyRunRecord
from app.modules.product_selection.strategy_service import SelectionStrategyService
from app.modules.product_selection.run_repository import SelectionRunRepository
from tests.test_selection_request_mapping import _original


def setup(monkeypatch, *, receipt_hour=9, trigger_hour=10, manual=True, linked=False, wrong_team=False):
    from app.modules.schedules import repository as schedules
    from app.modules.product_selection import run_repository as runs
    at=datetime(2026,10,14,1,tzinfo=UTC)
    sid,team,user=uuid4(),uuid4(),uuid4()
    original=_original()
    frozen=freeze_short_video_request(original,at).model_copy(update={'strategy':SelectionStrategySnapshot(strategy_id=sid,version=1)})
    canonical=Run(run_id=uuid4(),team_id=team,created_by_user_id=user,request_shop_id=original.shop_id,strategy_id=sid,
        submission_key=uuid4(),request_fingerprint=frozen.fingerprint(),request_conditions=frozen.model_dump(mode='json'),
        status='succeeded',stage='completed',result_count=1,saved_count=1,supplemented_count=1,supplement_failed_count=0,
        started_at=at,finished_at=at,created_at=at,updated_at=at)
    submitted=Run(run_id=uuid4(),team_id=uuid4() if wrong_team else team,created_by_user_id=user,request_shop_id=original.shop_id,
        strategy_id=sid,submission_key=uuid4(),request_fingerprint=frozen.fingerprint(),request_conditions=frozen.model_dump(mode='json'),
        reused_run_id=canonical.run_id,status='reused',stage='queued',created_at=at+timedelta(hours=receipt_hour-9),updated_at=at)
    trigger=SimpleNamespace(run_id=uuid4(),scheduled_for=at,created_at=at+timedelta(hours=trigger_hour-9),
        trigger_result='selection_run' if linked else 'blocked',selection_run_id=submitted.run_id if linked else None,
        trigger_error_code='SHOP_SESSION_AUTHENTICATION_INVALID',trigger_error_message='untrusted raw response prose')
    row=SimpleNamespace(strategy_id=sid,team_id=team,created_by_user_id=user,name='saved',request_shop_id=original.shop_id,
        version=1,enabled=True,conditions={'version':1,'request':original.model_dump(exclude={'shop_id'})},
        schedule_config={'scheduled':True,'kind':'hourly','interval_hours':3},created_at=at,updated_at=at)
    service=SelectionStrategyService(SimpleNamespace(),settings=Settings(_env_file=None))
    service.repository=SimpleNamespace(shops=lambda rows:{original.shop_id:'shop'},latest_runs=lambda actor,rows:{sid:StrategyRunRecord(canonical,submitted)} if manual else {})
    monkeypatch.setattr(schedules,'ScheduleRepository',lambda session:SimpleNamespace(selection_plans=lambda ids:{},latest_selection_triggers=lambda ids:{sid:trigger}))
    validate=SelectionRunRepository.validated_request
    monkeypatch.setattr(runs,'SelectionRunRepository',lambda session:SimpleNamespace(validated_request=validate,
        receipts_for_actor=lambda actor,ids:{submitted.run_id:(submitted,canonical)} if linked else {}))
    return service._project(None,[row])[0],trigger,canonical


def test_new_blocked_without_run_hides_older_success_and_never_exposes_raw_message(monkeypatch):
    result,trigger,_=setup(monkeypatch)
    assert result.latest_run is None
    assert result.latest_trigger.trigger_result=='blocked' and result.latest_trigger.receipt_id is None
    assert result.latest_trigger.error_code=='SHOP_SESSION_AUTHENTICATION_INVALID'
    assert result.latest_trigger.error_stage=='execution'
    assert 'untrusted' not in result.model_dump_json()
    assert result.latest_trigger.scheduled_for!=result.latest_trigger.created_at


@pytest.mark.parametrize('receipt_hour,trigger_hour',[(9,8),(11,10)])
def test_newer_receipt_overrides_old_blocked_even_if_canonical_is_older(monkeypatch,receipt_hour,trigger_hour):
    result,_,canonical=setup(monkeypatch,receipt_hour=receipt_hour,trigger_hour=trigger_hour)
    assert result.latest_trigger is None and result.latest_run.run_id==canonical.run_id


def test_linked_receipt_resolves_canonical_without_fake_run(monkeypatch):
    result,trigger,canonical=setup(monkeypatch,manual=False,linked=True)
    assert result.latest_trigger.trigger_result=='selection_run'
    assert result.latest_trigger.receipt_id==trigger.selection_run_id
    assert result.latest_run.run_id==canonical.run_id


def test_wrong_team_receipt_is_safe_blocked_without_identifiers(monkeypatch):
    result,_,_=setup(monkeypatch,manual=False,linked=True,wrong_team=True)
    assert result.latest_run is None and result.latest_trigger.trigger_result=='blocked'
    assert result.latest_trigger.receipt_id is None and result.latest_trigger.execution_run_id is None
