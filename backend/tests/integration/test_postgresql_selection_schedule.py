"""Low-concurrency Feature PG + injected categories/platform/clock; not natural real due evidence."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo
from threading import Barrier, Thread

import pytest
from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.access.models import TeamModuleAccess, TeamShopAccess
from app.modules.access.module_access import ModuleCode
from app.modules.product_selection.models import ProductSelectionRun as Run
from app.modules.product_selection.run_service import SelectionRunService
from app.modules.product_selection.run_executor import SelectionRunExecutor
from app.modules.product_selection.strategy_service import SelectionStrategyService
from app.modules.product_selection.strategy_contract import SelectionStrategyToggle
from app.modules.schedules.models import Schedule, ScheduleRun
from app.modules.schedules.selection_service import SelectionScheduleService
from app.modules.schedules.service import ScheduleService
from app.platforms.exceptions import PlatformAuthenticationInvalidError
from tests.integration.test_postgresql_product_selection import selection_context, _product, _api_client
from tests.integration.test_postgresql_selection_strategies import _config
from tests.integration.test_postgresql_selection_runs import _input
from tests.integration.test_postgresql_selection_windows import _category_tree, WindowPlatform, _submit

pytestmark=pytest.mark.integration
SETTINGS=Settings(_env_file=None,product_selection_execution_enabled=True,product_selection_schedule_enabled=True,product_selection_concurrency=3)


def save(context,monkeypatch,kind='hourly',brand='all'):
    from app.modules.product_selection import strategy_service
    accepted=datetime.now(UTC).replace(minute=0,second=0,microsecond=0)-timedelta(minutes=30)
    class Clock:
        @classmethod
        def now(cls,tz=None):return accepted
    monkeypatch.setattr(strategy_service,'datetime',Clock)
    choice=_input(context,rank_from=1,rank_to=1,brand=brand).original().model_dump(exclude={'shop_id'})
    config=_config(context,conditions={'version':1,'request':choice},schedule={'scheduled':True,'kind':kind,'interval_hours':3,'daily_time':'09:00'})
    with Session(context[0]) as session:
        saved=SelectionStrategyService(session,settings=SETTINGS).save(context[4][0],config)
    return saved


@pytest.mark.parametrize('brand,code',[('known','1'),('unknown','0')])
def test_scheduled_and_manual_runs_use_same_corrected_brand_mapping(selection_context,monkeypatch,brand,code):
    context=selection_context
    saved=save(context,monkeypatch,brand=brand)
    audit=trigger(context,saved.next_run_at)
    with Session(context[0]) as session:
        scheduled=SelectionRunService(session).get(context[4][0],audit.selection_run_id)
    manual=_submit(context,_input(context,rank_from=1,rank_to=1,brand=brand),now=saved.next_run_at+timedelta(minutes=1))
    assert scheduled.request_conditions.version==manual.execution.request_conditions.version==9
    assert scheduled.request_conditions.scope.brand_type==manual.execution.request_conditions.scope.brand_type==code
    assert scheduled.request_conditions.original.brand==manual.execution.request_conditions.original.brand==brand


def trigger(context,at,reader=None,settings=SETTINGS):
    with Session(context[0]) as session:
        def categories(actor,shop):
            assert not session.in_transaction()
            return _category_tree(shop)
        return SelectionScheduleService(session,settings=settings).trigger_next_due(now=at,category_reader=reader or categories)


def test_due_creates_receipt_audit_next_atomically_replay_and_query_only(selection_context,monkeypatch):
    context=selection_context
    saved=save(context,monkeypatch)
    first=saved.next_run_at
    due=first+timedelta(hours=7,minutes=23)
    audit=trigger(context,due)
    assert audit.trigger_result=='selection_run' and audit.task_id is None
    assert audit.scheduled_for==first+timedelta(hours=6)
    assert trigger(context,due) is None
    with Session(context[0]) as session:
        canonical=session.get(Run,audit.selection_run_id)
        read=SelectionRunService(session).get(context[4][0],canonical.run_id)
        assert read.request_conditions.original==_config(context,conditions=saved.conditions).conditions.original(saved.shop_id)
        assert read.request_conditions.date_plan.accepted_local_date==due.astimezone(ZoneInfo('Asia/Shanghai')).date()
        plan=session.scalar(select(Schedule).where(Schedule.selection_strategy_id==saved.strategy_id))
        assert plan.next_run_at==first+timedelta(hours=9)
        assert session.scalar(select(func.count()).select_from(ScheduleRun))>=1
        before=session.scalar(select(func.count()).select_from(Run).where(Run.team_id==context[1][0]))
        view=SelectionStrategyService(session,settings=SETTINGS).get(context[4][0],saved.strategy_id)
        assert view.latest_run.status=='pending' and view.latest_trigger.receipt_id==canonical.run_id
        assert view.next_run_at==plan.next_run_at
        assert session.scalar(select(func.count()).select_from(Run).where(Run.team_id==context[1][0]))==before


def test_disabled_environment_and_disabled_strategy_do_not_read_categories(selection_context,monkeypatch):
    context=selection_context
    saved=save(context,monkeypatch)
    forbidden=lambda *args:pytest.fail('Disabled environment/strategy must not call platform')
    assert trigger(context,saved.next_run_at,forbidden,Settings(_env_file=None,product_selection_execution_enabled=True,product_selection_schedule_enabled=False)) is None
    with Session(context[0]) as session:
        changed=SelectionStrategyService(session,settings=SETTINGS).toggle(context[4][0],saved.strategy_id,SelectionStrategyToggle(enabled=False,expected_version=saved.version))
        assert not changed.enabled and changed.next_run_at is None
    assert trigger(context,saved.next_run_at+timedelta(days=1),forbidden) is None


def test_preparation_session_failure_has_safe_audit_no_run_and_advances(selection_context,monkeypatch):
    context=selection_context
    saved=save(context,monkeypatch)
    def failed(*args):raise PlatformAuthenticationInvalidError('untrusted platform prose')
    audit=trigger(context,saved.next_run_at,failed)
    assert audit.trigger_result=='blocked' and audit.selection_run_id is None
    with Session(context[0]) as session:
        assert session.scalar(select(func.count()).select_from(Run).where(Run.team_id==context[1][0]))==0
        view=SelectionStrategyService(session,settings=SETTINGS).get(context[4][0],saved.strategy_id)
        assert view.latest_run is None and view.latest_trigger.error_code=='AUTH_INVALID'
        assert 'untrusted' not in view.model_dump_json()
        assert view.next_run_at==saved.next_run_at+timedelta(hours=3)


def test_due_existing_executor_persists_result_and_session_failure_is_not_empty_success(selection_context,monkeypatch):
    context=selection_context
    saved=save(context,monkeypatch)
    audit=trigger(context,saved.next_run_at)
    with Session(context[0]) as session:
        request=SelectionRunService(session).get(context[4][0],audit.selection_run_id).request_conditions
    platform=WindowPlatform(request,{('primary',1):(_product(rank=1),)})
    executor=SelectionRunExecutor(session_factory=lambda:Session(context[0]),platform=platform,settings=SETTINGS)
    assert executor.execute_available()==1
    with Session(context[0]) as session:
        view=SelectionStrategyService(session,settings=SETTINGS).get(context[4][0],saved.strategy_id)
        assert (view.latest_run.status,view.latest_run.saved_count,view.latest_run.supplemented_count)==('succeeded',1,1)
    later=trigger(context,saved.next_run_at+timedelta(hours=3))
    class Expired(WindowPlatform):
        def session_context(self,shop):raise PlatformAuthenticationInvalidError()
    failed=SelectionRunExecutor(session_factory=lambda:Session(context[0]),platform=Expired(request,{}),settings=SETTINGS)
    assert failed.execute_available()==1
    with Session(context[0]) as session:
        view=SelectionStrategyService(session,settings=SETTINGS).get(context[4][0],saved.strategy_id)
        assert view.latest_run.run_id==later.selection_run_id
        assert view.latest_run.status=='failed' and view.latest_run.result_count is None
        assert view.latest_run.error_code=='AUTH_INVALID'


def test_pc_api_filters_selection_in_total_id_and_audit_and_team_access_is_unchanged(selection_context,monkeypatch):
    from app.modules.schedules.api import get_schedule_service
    context=selection_context
    saved=save(context,monkeypatch)
    with Session(context[0]) as session:
        plan=session.scalar(select(Schedule).where(Schedule.selection_strategy_id==saved.strategy_id))
        plan_id=plan.schedule_id
        session.add(TeamModuleAccess(team_id=context[1][0],module_code=ModuleCode.SCHEDULE.value));session.commit()
    def service():
        with Session(context[0]) as session:yield ScheduleService(session)
    with _api_client(context) as client:
        client.app.dependency_overrides[get_schedule_service]=service
        headers={'X-Team-ID':str(context[1][0])}
        page=client.get('/api/v1/schedules',headers=headers)
        assert page.status_code==200 and page.json()['total']==0
        assert client.get(f'/api/v1/schedules/{plan_id}',headers=headers).status_code==404
        assert client.get(f'/api/v1/schedules/{plan_id}/runs',headers=headers).status_code==404
    with _api_client(context,1) as client:
        assert client.get(f'/api/v1/product-selection/strategies/{saved.strategy_id}',headers={'X-Team-ID':str(context[1][1])}).status_code==404


def test_daily_restart_coalesces_one_and_preserves_shanghai_rule(selection_context,monkeypatch):
    context=selection_context
    saved=save(context,monkeypatch,kind='daily')
    due=saved.next_run_at+timedelta(days=3,minutes=17)
    audit=trigger(context,due)
    assert audit.scheduled_for==saved.next_run_at+timedelta(days=3)
    with Session(context[0]) as session:
        view=SelectionStrategyService(session,settings=SETTINGS).get(context[4][0],saved.strategy_id)
        assert view.next_run_at==saved.next_run_at+timedelta(days=4)
        assert view.next_run_at.astimezone(ZoneInfo('Asia/Shanghai')).hour==9
        assert session.scalar(select(func.count()).select_from(ScheduleRun).join(Schedule).where(Schedule.team_id==context[1][0]))==1


@pytest.mark.parametrize('change',['disable','revoke_shop'])
def test_final_recheck_after_category_prepare_does_not_emit_unauthorized_run(selection_context,monkeypatch,change):
    context=selection_context
    saved=save(context,monkeypatch)
    def changed(actor,shop):
        with Session(context[0]) as session:
            if change=='disable':
                SelectionStrategyService(session,settings=SETTINGS).toggle(context[4][0],saved.strategy_id,SelectionStrategyToggle(enabled=False,expected_version=saved.version))
            else:
                session.execute(delete(TeamShopAccess).where(TeamShopAccess.team_id==context[1][0],TeamShopAccess.shop_id==shop));session.commit()
        return _category_tree(shop)
    audit=trigger(context,saved.next_run_at,changed)
    assert audit is None if change=='disable' else audit.trigger_result=='blocked' and audit.selection_run_id is None
    with Session(context[0]) as session:
        assert session.scalar(select(func.count()).select_from(Run).where(Run.team_id==context[1][0]))==0


def test_duplicate_scanners_lock_same_strategy_occurrence_once(selection_context,monkeypatch):
    context=selection_context
    saved=save(context,monkeypatch)
    barrier=Barrier(2);results=[];errors=[]
    def categories(actor,shop):
        barrier.wait(10);return _category_tree(shop)
    def scan():
        try:results.append(trigger(context,saved.next_run_at,categories))
        except BaseException as error:errors.append(type(error).__name__)
    threads=[Thread(target=scan) for _ in range(2)]
    for thread in threads:thread.start()
    for thread in threads:thread.join(15)
    assert not any(thread.is_alive() for thread in threads) and errors==[]
    assert len([result for result in results if result is not None])==1
    with Session(context[0]) as session:
        assert session.scalar(select(func.count()).select_from(Run).where(Run.team_id==context[1][0]))==1
        assert session.scalar(select(func.count()).select_from(ScheduleRun).join(Schedule).where(Schedule.team_id==context[1][0]))==1


@pytest.mark.parametrize('committed',[False,True])
def test_commit_failure_never_splits_receipt_audit_and_next(selection_context,monkeypatch,committed):
    context=selection_context
    saved=save(context,monkeypatch)
    with Session(context[0]) as session:
        real_commit=session.commit
        def lost_ack():
            if committed:real_commit()
            raise RuntimeError('synthetic transaction acknowledgement loss')
        monkeypatch.setattr(session,'commit',lost_ack)
        with pytest.raises(RuntimeError):
            SelectionScheduleService(session,settings=SETTINGS).trigger_next_due(now=saved.next_run_at,category_reader=lambda actor,shop:_category_tree(shop))
    with Session(context[0]) as session:
        assert session.scalar(select(func.count()).select_from(Run).where(Run.team_id==context[1][0]))==int(committed)
        assert session.scalar(select(func.count()).select_from(ScheduleRun).join(Schedule).where(Schedule.team_id==context[1][0]))==int(committed)
        plan=session.scalar(select(Schedule).where(Schedule.selection_strategy_id==saved.strategy_id))
        assert plan.next_run_at==(saved.next_run_at+timedelta(hours=3) if committed else saved.next_run_at)
    result=trigger(context,saved.next_run_at,lambda *_:pytest.fail('Committed occurrence cannot read platform again') if committed else _category_tree(saved.shop_id))
    assert result is None if committed else result.trigger_result=='selection_run'
