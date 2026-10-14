"""Pure Schedule target synchronization/time rules; no database or due execution."""

from datetime import UTC, datetime, time
from types import SimpleNamespace
from uuid import uuid4

from app.core.config import Settings
from app.modules.schedules.selection_service import SelectionScheduleService


def subject():
    calls=[]
    session=SimpleNamespace(flush=lambda:calls.append('flush'))
    service=SelectionScheduleService(session,settings=Settings(_env_file=None))
    stored=[]
    service.repository=SimpleNamespace(selection_plan=lambda *args,**kwargs:stored[0] if stored else None,add=stored.append)
    row=SimpleNamespace(strategy_id=uuid4(),team_id=uuid4(),created_by_user_id=uuid4(),enabled=True,name='strategy',
        schedule_config={'scheduled':True,'kind':'hourly','interval_hours':5,'daily_time':'09:00','timezone':'Asia/Shanghai'})
    return service,row,stored,calls


def test_next_strict_hour_condition_edits_preserve_anchor_disable_reactivate():
    service,row,stored,calls=subject()
    first=service.sync_strategy(row,now=datetime(2026,12,31,15,47,tzinfo=UTC))
    assert first.next_run_at==datetime(2026,12,31,16,tzinfo=UTC)
    assert first.interval_hours==5 and first.local_time is None
    assert first.target_kind=='server_selection' and first.target_device_id is None and first.skill_id is None
    row.name='changed conditions/name'
    service.sync_strategy(row,now=datetime(2027,1,1,3,15,tzinfo=UTC))
    assert first.next_run_at==datetime(2026,12,31,16,tzinfo=UTC) # Due scanner coalesces; an edit does not reset cadence.
    row.enabled=False
    service.sync_strategy(row,now=datetime(2027,1,1,3,15,tzinfo=UTC))
    assert first.next_run_at is None and not first.enabled
    row.enabled=True
    service.sync_strategy(row,now=datetime(2027,1,1,3,15,tzinfo=UTC))
    assert first.next_run_at==datetime(2027,1,1,4,tzinfo=UTC)
    assert len(stored)==1 and calls==['flush']*4


def test_interval_and_daily_changes_use_same_saved_config_no_fake_midnight():
    service,row,stored,calls=subject()
    first=service.sync_strategy(row,now=datetime(2026,12,31,15,47,tzinfo=UTC))
    row.schedule_config={**row.schedule_config,'interval_hours':3}
    service.sync_strategy(row,now=datetime(2027,1,1,2,10,tzinfo=UTC))
    assert first.next_run_at==datetime(2027,1,1,3,tzinfo=UTC) and first.interval_hours==3
    row.schedule_config={**row.schedule_config,'kind':'daily','daily_time':'09:30'}
    service.sync_strategy(row,now=datetime(2027,1,1,2,10,tzinfo=UTC))
    assert first.interval_hours is None and first.local_time==time(9,30)
    assert first.next_run_at==datetime(2027,1,2,1,30,tzinfo=UTC)
    assert len(stored)==1


def test_unscheduled_new_strategy_does_not_create_plan():
    service,row,stored,calls=subject()
    row.schedule_config={**row.schedule_config,'scheduled':False}
    assert service.sync_strategy(row,now=datetime(2026,10,14,tzinfo=UTC)) is None
    assert stored==[] and calls==[]
