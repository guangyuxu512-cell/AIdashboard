from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.modules.workers.auth import get_worker_principal
from app.modules.workers.schemas import DeviceRuntimeRead, WorkerHeartbeat
from app.modules.workers.service import WorkerPrincipal, WorkerService


router = APIRouter(
    prefix="/api/v1/worker",
    tags=["worker"],
    responses={
        **COMMON_ERROR_RESPONSES,
        401: {"model": ErrorResponse, "description": "Worker 身份验证失败"},
    },
)


def get_worker_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> WorkerService:
    return WorkerService(session)


@router.post("/heartbeat", response_model=DeviceRuntimeRead)
def heartbeat(
    data: WorkerHeartbeat,
    principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)],
    service: Annotated[WorkerService, Depends(get_worker_service)],
) -> DeviceRuntimeRead:
    return service.heartbeat(principal, data)
