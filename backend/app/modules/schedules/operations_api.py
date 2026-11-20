from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.modules.access.contracts import ActorContext
from app.modules.schedules.api import get_schedule_authorized_actor
from app.modules.schedules.operations_models import OperationsSchedule, OperationsScheduleRun
from app.modules.schedules.operations_service import OperationsScheduleInput, get_schedule, put_schedule


router = APIRouter(prefix='/api/v1/operations-selection-schedules', tags=['schedules'])


@router.get('/{strategy_id}')
def get_operations_schedule(strategy_id: UUID,
        actor: Annotated[ActorContext, Depends(get_schedule_authorized_actor)],
        session: Annotated[Session, Depends(get_database_session)]):
    return {'schedule': get_schedule(session, actor, strategy_id)}


@router.put('/{strategy_id}')
def put_operations_schedule(strategy_id: UUID, data: OperationsScheduleInput,
        actor: Annotated[ActorContext, Depends(get_schedule_authorized_actor)],
        session: Annotated[Session, Depends(get_database_session)]):
    return {'schedule': put_schedule(session, actor, strategy_id, data)}


@router.get('/{strategy_id}/runs')
def list_operations_schedule_runs(strategy_id: UUID,
        actor: Annotated[ActorContext, Depends(get_schedule_authorized_actor)],
        session: Annotated[Session, Depends(get_database_session)]):
    team_id = actor.require_team_id()
    rows = session.scalars(select(OperationsScheduleRun).join(OperationsSchedule,
        OperationsSchedule.schedule_id == OperationsScheduleRun.schedule_id).where(
        OperationsSchedule.team_id == team_id, OperationsSchedule.strategy_id == strategy_id)
        .order_by(OperationsScheduleRun.scheduled_for.desc(), OperationsScheduleRun.run_id.desc()).limit(30)).all()
    return {'items': [{'run_id': str(row.run_id), 'scheduled_for': row.scheduled_for.isoformat(),
        'state': row.state, 'attempts': row.attempts, 'error_code': row.error_code,
        'operations_run_id': str(row.operations_run_id) if row.operations_run_id else None} for row in rows]}
