from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_database_session
from app.modules.workers.auth import get_worker_principal
from app.modules.workers.precheck_contract import PrecheckDeliveryAcknowledgement
from app.modules.workers.selection_delivery import acknowledge_delivery, delivery_context, mark_delivery_pending
from app.modules.workers.service import WorkerPrincipal


router = APIRouter(prefix='/api/v1/worker', tags=['worker-selection-delivery'])


@router.get('/tasks/{task_id}/selection-delivery-context')
def get_selection_delivery_context(task_id: UUID, response: Response,
        principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)],
        session: Annotated[Session, Depends(get_database_session)],
        settings: Annotated[Settings, Depends(get_settings)]) -> dict:
    response.headers['Cache-Control'] = 'no-store'
    return delivery_context(session, settings, principal.device_id, task_id)


@router.post('/tasks/{task_id}/selection-delivered')
def finish_selection_delivery(task_id: UUID, body: PrecheckDeliveryAcknowledgement,
        principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)],
        session: Annotated[Session, Depends(get_database_session)]) -> dict:
    task = acknowledge_delivery(session, principal.device_id, task_id, body)
    return {'task_id': str(task.task_id), 'status': task.status}


@router.post('/tasks/{task_id}/selection-delivery-pending')
def pending_selection_delivery(task_id: UUID, body: PrecheckDeliveryAcknowledgement,
        principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)],
        session: Annotated[Session, Depends(get_database_session)]) -> dict:
    task = mark_delivery_pending(session, principal.device_id, task_id, body)
    return {'task_id': str(task.task_id), 'status': task.status}
