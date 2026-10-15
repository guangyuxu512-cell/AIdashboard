"""100 synthetic due plans, never real platform load; run only in a coordinated PG window."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Event, Lock, Thread
from time import monotonic, sleep
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.modules.access.models import TeamShopAccess
from app.modules.product_selection.models import ProductSelectionRun as Run
from app.modules.product_selection.run_executor import SelectionRunExecutor
from app.modules.product_selection.run_service import SelectionRunService
from app.modules.product_selection.strategy_service import SelectionStrategyService
from app.modules.schedules.models import Schedule, ScheduleRun
from app.modules.schedules.selection_service import SelectionScheduleService
from app.modules.shops.models import Shop
from app.modules.shops.enums import ShopPlatform
from app.platforms.douyin.product_selection import CompassBasicInfo, CompassBadCommentRate, CompassRankPage, FieldObservation
from tests.integration.test_postgresql_product_selection import selection_context, _product
from tests.integration.test_postgresql_selection_strategies import _config
from tests.integration.test_postgresql_selection_runs import _input
from tests.integration.test_postgresql_selection_windows import _category_tree
from tests.integration.test_postgresql_selection_schedule import SETTINGS

pytestmark=pytest.mark.integration


def test_one_hundred_due_plans_persist_queue_dedup_and_bounded_execution(selection_context,monkeypatch):
    from app.modules.product_selection import strategy_service
    context=selection_context
    accepted=datetime.now(UTC).replace(minute=0,second=0,microsecond=0)-timedelta(minutes=30)
    class Clock:
        @classmethod
        def now(cls,tz=None):return accepted
    monkeypatch.setattr(strategy_service,'datetime',Clock)
    for _ in range(8):
        key=uuid4();context[3].append(key)
        with Session(context[0]) as session:
            session.add(Shop(shop_id=key,display_name='stage-2a1 capacity',platform=ShopPlatform.DOUYIN));session.flush()
            session.add(TeamShopAccess(team_id=context[1][0],shop_id=key));session.commit()
    first=None
    for index in range(100):
        choice=_input(context,shop_id=context[3][index%10],rank_from=index+1,rank_to=index+1).original().model_dump(exclude={'shop_id'})
        with Session(context[0]) as session:
            saved=SelectionStrategyService(session,settings=SETTINGS).save(context[4][0],_config(context,
                name=f'stage-2a1 due {index}',shop_id=context[3][index%10],conditions={'version':1,'request':choice},
                schedule={'scheduled':True,'kind':'hourly','interval_hours':3}))
            first=first or saved.next_run_at
            assert saved.next_run_at==first
    audits=[]
    for _ in range(100):
        with Session(context[0]) as session:
            result=SelectionScheduleService(session,settings=SETTINGS).trigger_next_due(now=first,category_reader=lambda actor,shop:_category_tree(shop))
            assert result is not None and result.trigger_result=='selection_run'
            audits.append(result.run_id)
    assert len(set(audits))==100
    with Session(context[0]) as session:
        assert SelectionScheduleService(session,settings=SETTINGS).trigger_next_due(now=first,category_reader=lambda *_:pytest.fail('No duplicate due read')) is None
        assert session.scalar(select(func.count()).select_from(Run).where(Run.team_id==context[1][0],Run.status=='pending'))==100
        assert session.scalar(select(func.count()).select_from(ScheduleRun).join(Schedule).where(Schedule.team_id==context[1][0]))==100
    lock=Lock();active={};shops={};seen=set();max_active=0;errors=[]
    class Platform:
        def session_context(self,shop):return SimpleNamespace(shop_id=shop)
        def rank(self,context,request,page_no):
            first_rank=(page_no-1)*10+1
            return CompassRankPage(tuple(_product(product_id=str(3800000000000000000+rank),rank=rank) for rank in range(first_rank,first_rank+10)),page_no,10,200)
        def basic_info(self,context,product_id):
            return CompassBasicInfo(product_id,FieldObservation('available',('合成类目',)),FieldObservation('available',accepted.date()),FieldObservation('available',CompassBadCommentRate(Decimal(0),'int',4)))
    executor=SelectionRunExecutor(session_factory=lambda:Session(context[0]),platform=Platform(),settings=SETTINGS)
    original_finish=SelectionRunService.finish
    def measured_finish(self,got,**kwargs):
        # Registration/removal brackets the actual terminal DB commit; a new
        # claimant cannot make Python bookkeeping report a false overlap.
        with lock:
            original_finish(self,got,**kwargs)
            active.pop(got.run_id,None);shops.pop(got.shop_id,None)
    monkeypatch.setattr(SelectionRunService,'finish',measured_finish)
    # Feature PG is reached through the registered SSH forward. This is a
    # correctness stress test, not a 55-second throughput SLA. Use one common
    # bounded deadline and never tear down its fixtures under live consumers.
    stop = Event()
    deadline = monotonic() + 240
    def consume():
        nonlocal max_active
        while not stop.is_set() and monotonic() < deadline:
            with Session(context[0]) as session:
                got=SelectionRunService(session,settings=SETTINGS).claim_next()
            if got is None:
                with Session(context[0]) as session:
                    remaining=session.scalar(select(func.count()).select_from(Run).where(Run.team_id==context[1][0],Run.status.in_(('pending','running'))))
                if not remaining:return
                sleep(0.01);continue
            with lock:
                if got.run_id in seen or got.shop_id in shops or got.request.strategy.strategy_id in active.values():
                    errors.append('duplicate_or_overlap')
                seen.add(got.run_id);active[got.run_id]=got.request.strategy.strategy_id;shops[got.shop_id]=got.run_id
                max_active=max(max_active,len(active))
            sleep(0.01)
            executor.execute_claim(got)
            with lock:
                active.pop(got.run_id,None);shops.pop(got.shop_id,None)
    threads=[Thread(target=consume) for _ in range(3)]
    for thread in threads:thread.start()
    for thread in threads:thread.join(max(0, deadline-monotonic()))
    timed_out = any(thread.is_alive() for thread in threads)
    stop.set()
    for thread in threads:thread.join(15)
    assert not timed_out and not any(thread.is_alive() for thread in threads), f'bounded queue test incomplete: claimed={len(seen)}, active={len(active)}'
    assert errors==[] and max_active==3 and len(seen)==100
    with Session(context[0]) as session:
        assert session.scalar(select(func.count()).select_from(Run).where(Run.team_id==context[1][0],Run.status=='succeeded'))==100
