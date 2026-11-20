"""Persist and trigger operations schedules using the existing scheduler loop."""
from datetime import UTC, datetime, time, timedelta
import re
from urllib.parse import urlsplit
from uuid import UUID, uuid5

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AppError
from app.modules.access.contracts import ActorContext
from app.modules.access.module_access import ModuleCode
from app.modules.access.service import ActorContextService, ModuleAccessService
from app.modules.schedules.operations_models import OperationsSchedule, OperationsScheduleRun
from app.modules.schedules.time_rules import latest_daily_occurrence, latest_hourly_occurrence, next_daily_occurrence, next_hourly_occurrence


class OperationsScheduleConflict(AppError):
    code = 'OPERATIONS_SCHEDULE_CONFLICT'
    message = '定时计划已变化，请刷新后重试'
    status_code = 409


class OperationsScheduleInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    enabled: bool = Field(default=False, strict=True)
    kind: str = Field(pattern=r'^(daily|hourly)$')
    local_time: time | None = None
    interval_hours: int | None = Field(default=None, ge=1, le=24, strict=True)

    @model_validator(mode='after')
    def validate_rule(self):
        if self.kind == 'daily':
            if self.local_time is None or self.local_time.tzinfo is not None or self.interval_hours is not None:
                raise ValueError('每日计划需要本地时间')
            self.local_time = self.local_time.replace(second=0, microsecond=0)
        elif self.local_time is not None or self.interval_hours is None:
            raise ValueError('小时计划需要间隔')
        return self


def schedule_read(row: OperationsSchedule | None) -> dict | None:
    if row is None:
        return None
    return {'schedule_id': str(row.schedule_id), 'strategy_id': str(row.strategy_id), 'name': row.name,
            'enabled': row.enabled, 'kind': row.kind, 'local_time': row.local_time.isoformat(timespec='minutes') if row.local_time else None,
            'interval_hours': row.interval_hours, 'next_run_at': row.next_run_at.isoformat() if row.next_run_at else None}


def get_schedule(session: Session, actor: ActorContext, strategy_id: UUID) -> dict | None:
    team_id = actor.require_team_id()
    row = session.scalar(select(OperationsSchedule).where(OperationsSchedule.team_id == team_id,
                         OperationsSchedule.strategy_id == strategy_id))
    return schedule_read(row)


def list_schedule_runs(session: Session, actor: ActorContext, strategy_id: UUID) -> list[dict]:
    team_id = actor.require_team_id()
    rows = session.scalars(select(OperationsScheduleRun).join(OperationsSchedule,
        OperationsSchedule.schedule_id == OperationsScheduleRun.schedule_id).where(
        OperationsSchedule.team_id == team_id, OperationsSchedule.strategy_id == strategy_id)
        .order_by(OperationsScheduleRun.scheduled_for.desc(), OperationsScheduleRun.run_id.desc()).limit(30)).all()
    return [{'run_id': str(row.run_id), 'scheduled_for': row.scheduled_for.isoformat(),
        'state': row.state, 'attempts': row.attempts, 'error_code': row.error_code,
        'operations_run_id': str(row.operations_run_id) if row.operations_run_id else None} for row in rows]


def put_schedule(session: Session, actor: ActorContext, strategy_id: UUID,
                 data: OperationsScheduleInput, *, now: datetime | None = None) -> dict:
    team_id, at = actor.require_team_id(), now or datetime.now(UTC)
    row = session.scalar(select(OperationsSchedule).where(OperationsSchedule.team_id == team_id,
                         OperationsSchedule.strategy_id == strategy_id).with_for_update())
    if row is None:
        row = OperationsSchedule(team_id=team_id, created_by_user_id=actor.user_id, strategy_id=strategy_id,
                                 name=data.name, enabled=False, kind=data.kind,
                                 local_time=data.local_time, interval_hours=data.interval_hours, created_at=at, updated_at=at)
        session.add(row)
        activating, changed = True, True
    else:
        activating = not row.enabled
        changed = (row.kind, row.local_time, row.interval_hours) != (data.kind, data.local_time, data.interval_hours)
    row.name, row.kind, row.local_time, row.interval_hours = data.name, data.kind, data.local_time, data.interval_hours
    if not data.enabled:
        row.next_run_at = None
        if row.schedule_id:
            pending = session.scalars(select(OperationsScheduleRun).where(
                OperationsScheduleRun.schedule_id == row.schedule_id, OperationsScheduleRun.state == 'pending').with_for_update()).all()
            for run in pending:
                run.state, run.error_code = 'cancelled', 'SCHEDULE_DISABLED'
    elif activating or changed or row.next_run_at is None:
        row.next_run_at = (next_daily_occurrence(data.local_time, 'Asia/Shanghai', after=at) if data.kind == 'daily'
                           else next_hourly_occurrence('Asia/Shanghai', after=at, interval_hours=data.interval_hours))
    row.enabled, row.updated_at = data.enabled, at
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise OperationsScheduleConflict() from None
    return schedule_read(row)


def stage_due(session: Session, *, now: datetime | None = None) -> bool:
    at = now or datetime.now(UTC)
    row = session.scalar(select(OperationsSchedule).where(OperationsSchedule.enabled.is_(True),
        OperationsSchedule.next_run_at.is_not(None), OperationsSchedule.next_run_at <= at)
        .order_by(OperationsSchedule.next_run_at, OperationsSchedule.schedule_id).with_for_update(skip_locked=True).limit(1))
    if row is None:
        session.rollback()
        return False
    if row.kind == 'daily':
        occurrence = latest_daily_occurrence(row.local_time, 'Asia/Shanghai', at_or_before=at)
        following = next_daily_occurrence(row.local_time, 'Asia/Shanghai', after=at)
    else:
        occurrence = latest_hourly_occurrence('Asia/Shanghai', at_or_before=at,
                                               interval_hours=row.interval_hours, anchor=row.next_run_at)
        following = next_hourly_occurrence('Asia/Shanghai', after=at,
                                            interval_hours=row.interval_hours, anchor=row.next_run_at)
    key = uuid5(row.schedule_id, 'operations-selection:' + occurrence.astimezone(UTC).isoformat())
    session.add(OperationsScheduleRun(schedule_id=row.schedule_id, scheduled_for=occurrence,
        submission_key=key, state='pending', attempts=0, next_attempt_at=at, created_at=at))
    row.next_run_at, row.updated_at = following, at
    session.commit()
    return True


def _origin(value: str | None) -> str:
    try:
        parsed = urlsplit(value or '')
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.port not in (None, 443)
                or re.fullmatch(r'(?:/[A-Za-z0-9_-]+)*/?', parsed.path) is None
                or len(value or '') > 2048 or any(ord(char) < 33 or ord(char) == 127 for char in (value or ''))):
            raise ValueError('invalid origin')
    except ValueError:
        raise ValueError('operations origin unavailable') from None
    return (value or '').rstrip('/')


def send_pending(session: Session, settings: Settings, *, now: datetime | None = None, transport=None) -> bool:
    """Retry the same submission key; never create a second logical run."""
    at = now or datetime.now(UTC)
    if not settings.operations_schedule_execution_enabled or not settings.operations_schedule_token:
        return False
    try:
        origin = _origin(settings.operations_schedule_origin)
        token = settings.operations_schedule_token.get_secret_value()
        if not token or len(token) > 4096 or any(char in token for char in '\r\n\0'):
            return False
    except ValueError:
        return False
    run = session.scalar(select(OperationsScheduleRun).where(OperationsScheduleRun.state == 'pending',
        OperationsScheduleRun.next_attempt_at <= at).order_by(OperationsScheduleRun.next_attempt_at,
        OperationsScheduleRun.run_id).with_for_update(skip_locked=True).limit(1))
    if run is None:
        session.rollback()
        return False
    schedule = session.get(OperationsSchedule, run.schedule_id)
    if schedule is None or not schedule.enabled:
        run.state, run.error_code = 'cancelled', 'SCHEDULE_DISABLED'
        session.commit()
        return True
    try:
        actor = ActorContextService(session).resolve(user_id=schedule.created_by_user_id, requested_team_id=schedule.team_id)
        ModuleAccessService(session).require_module_access(actor, ModuleCode.SCHEDULE)
    except AppError:
        run.state, run.error_code = 'failed', 'SCHEDULE_AUTHORIZATION_REVOKED'
        session.commit()
        return True
    error, retryable, operations_run_id = None, False, None
    try:
        with httpx.Client(timeout=8, follow_redirects=False, trust_env=False, transport=transport) as client:
            response = client.post(origin + '/api/v1/internal/scheduled-selection',
                headers={'Authorization': 'Bearer ' + token},
                json={'strategyId': str(schedule.strategy_id), 'submissionKey': str(run.submission_key)})
        if response.status_code in (200, 201, 202):
            body = response.json()
            operations_run_id = UUID(body['runId'])
        elif response.status_code in (408, 429) or response.status_code >= 500:
            error, retryable = 'OPERATIONS_UNAVAILABLE', True
        else:
            error = 'OPERATIONS_REQUEST_REJECTED'
    except (httpx.HTTPError, OSError):
        error, retryable = 'OPERATIONS_UNAVAILABLE', True
    except (ValueError, TypeError, KeyError):
        error, retryable = 'OPERATIONS_RESPONSE_INVALID', True
    run.attempts += 1
    if operations_run_id:
        run.state, run.operations_run_id, run.error_code = 'sent', operations_run_id, None
    elif retryable and run.attempts < 5:
        run.error_code, run.next_attempt_at = error, at + timedelta(seconds=min(300, 10 * 2 ** (run.attempts - 1)))
    else:
        run.state, run.error_code = 'failed', error or 'OPERATIONS_REQUEST_FAILED'
    session.commit()
    return True
