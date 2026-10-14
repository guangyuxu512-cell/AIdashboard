"""0045 durable queue, actual independent claims; all platform I/O synthetic."""

from datetime import UTC, datetime, timedelta
from multiprocessing import get_context
from time import sleep
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, make_url, select, func, text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.modules.access.models import TeamShopAccess
from app.modules.shops.models import Shop
from app.modules.shops.enums import ShopPlatform
from app.modules.product_selection.models import ProductSelectionRun as Run
from app.modules.product_selection.run_service import SelectionRunService
from app.modules.product_selection.strategy_service import SelectionStrategyService
from app.modules.product_selection.strategy_contract import SelectionStrategyUpdate
from tests.integration.test_postgresql_product_selection import selection_context
from tests.integration.test_postgresql_selection_runs import _input
from tests.integration.test_postgresql_selection_windows import _submit
from tests.integration.test_postgresql_selection_strategies import _save, _config

pytestmark = pytest.mark.integration
SETTINGS = Settings(_env_file=None, product_selection_execution_enabled=True, product_selection_concurrency=3)


def submit(context, shop, at, strategy=None, key=None):
    changes = {} if strategy is None else {'strategy_id':strategy.strategy_id,'strategy_version':strategy.version}
    if key is not None: changes['submission_key'] = key
    return _submit(context, _input(context, shop_id=shop, rank_from=1, rank_to=25, **changes), now=at)


def claim(context):
    with Session(context[0]) as session:
        return SelectionRunService(session, settings=SETTINGS).claim_next()


def finish(context, value):
    with Session(context[0]) as session:
        SelectionRunService(session, settings=SETTINGS).finish(value)


def add_shop(context):
    sid = uuid4()
    context[3].append(sid)
    with Session(context[0]) as session:
        session.add(Shop(shop_id=sid, display_name='stage-2a1 queue', platform=ShopPlatform.DOUYIN));session.flush()
        session.add(TeamShopAccess(team_id=context[1][0],shop_id=sid));session.commit()
    return sid


def test_two_running_conflict_creates_stable_pending_without_mutating_old_runs(selection_context):
    context, at = selection_context, datetime.now(UTC)
    saved = _save(context)
    a = submit(context, context[3][0], at, saved); running_a = claim(context)
    b = submit(context, context[3][1], at); running_b = claim(context)
    assert (running_a.run_id,running_b.run_id)==(a.execution_run_id,b.execution_run_id)
    with Session(context[0]) as session:
        saved = SelectionStrategyService(session).save(context[4][0], SelectionStrategyUpdate(**(_config(context, shop_id=context[3][1]).model_dump() | {'expected_version':saved.version})), strategy_id=saved.strategy_id)
    key=uuid4()
    pending = submit(context,context[3][1],at,saved,key)
    assert not pending.reused and pending.execution.status=='pending'
    assert pending.execution.request_conditions.strategy_queue.strategy_id==saved.strategy_id
    assert claim(context) is None
    replay=submit(context,context[3][1],at+timedelta(days=1),saved,key)
    assert replay.execution_run_id==pending.execution_run_id
    assert replay.execution.request_conditions==pending.execution.request_conditions
    with Session(context[0]) as session:
        assert session.get(Run,a.execution_run_id).status=='running'
        assert session.get(Run,b.execution_run_id).status=='running'
        assert session.get(Run,b.execution_run_id).strategy_id is None
    finish(context,running_a)
    # Even after S becomes free, the existing isolated pending is reused.
    again=submit(context,context[3][1],at,saved)
    assert again.reused and again.execution_run_id==pending.execution_run_id
    finish(context,running_b)
    chosen=claim(context)
    assert chosen.run_id==pending.execution_run_id
    assert chosen.request.scope==pending.execution.request_conditions.scope
    assert chosen.request.date_plan==pending.execution.request_conditions.date_plan
    assert claim(context) is None
    finish(context,chosen)


def test_busy_shop_and_strategy_do_not_head_of_line_block_other_shop(selection_context):
    context,at=selection_context,datetime.now(UTC)
    first=submit(context,context[3][0],at);first_claim=claim(context)
    waiting=_submit(context,_input(context,shop_id=context[3][0],rank_from=1,rank_to=24),now=at)
    other=submit(context,context[3][1],at)
    assert claim(context).run_id==other.execution_run_id
    third=submit(context,add_shop(context),at)
    assert claim(context).run_id==third.execution_run_id
    assert claim(context) is None
    with Session(context[0]) as session:
        assert session.get(Run,waiting.execution_run_id).status=='pending'
        assert session.scalar(select(func.count()).select_from(Run).where(Run.status=='running'))==3
    finish(context,first_claim)
    assert claim(context).run_id==waiting.execution_run_id


def _independent_process_claim(gate, results):
    # No credentials in process arguments, result, command line or exceptions.
    try:
        url=make_url(str(get_settings().database_url))
        if (url.database,url.host,url.port)!=('control_center_feat_product_selection','127.0.0.1',35433): raise RuntimeError('target_guard')
        engine=create_engine(url,hide_parameters=True,echo=False)
        with engine.connect() as connection:
            if connection.scalar(text('SELECT current_database()'))!=url.database:raise RuntimeError('live_guard')
        if not gate.wait(15):raise RuntimeError('start_timeout')
        got=None
        for _ in range(10):
            with Session(engine) as session:
                got=SelectionRunService(session,settings=SETTINGS).claim_next()
            if got is not None:break
            sleep(0.05)  # Retry only a busy short DB decision, never platform I/O.
        results.put(('claim',str(got.run_id) if got else None))
        engine.dispose()
    except BaseException as error:
        results.put(('error_type',type(error).__name__))


def test_global_capacity_three_across_independent_processes(selection_context):
    context,at=selection_context,datetime.now(UTC)
    for _ in range(6): submit(context,add_shop(context),at)
    spawn=get_context('spawn');gate=spawn.Event();results=spawn.Queue()
    processes=[spawn.Process(target=_independent_process_claim,args=(gate,results)) for _ in range(6)]
    for process in processes:process.start()
    gate.set()
    try:
        reports=[results.get(timeout=25) for _ in processes]
        assert all(kind=='claim' for kind,_ in reports)
        claimed=[key for _,key in reports if key is not None]
        assert len(claimed)==len(set(claimed))==3
        with Session(context[0]) as session:
            assert session.scalar(select(func.count()).select_from(Run).where(Run.status=='running'))==3
            assert session.scalar(select(func.count()).select_from(Run).where(Run.status=='pending'))==3
    finally:
        for process in processes:
            process.join(5)
            if process.is_alive():process.terminate();process.join(5)
        results.close()
