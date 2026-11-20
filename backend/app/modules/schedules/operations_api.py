from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.modules.access.contracts import ActorContext
from app.modules.schedules.api import get_schedule_authorized_actor
from app.modules.schedules.operations_service import OperationsScheduleInput, get_schedule, list_schedule_runs, put_schedule


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
    return {'items': list_schedule_runs(session, actor, strategy_id)}
