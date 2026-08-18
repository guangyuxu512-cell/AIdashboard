from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.modules.tasks.schemas import (
    TaskComplete,
    TaskFail,
    TaskLeaseRead,
    TaskRead,
    WorkerTaskRead,
    task_to_read,
)
from app.modules.tasks.service import TaskService
from app.modules.workers.auth import get_worker_principal
from app.modules.workers.service import WorkerPrincipal


router = APIRouter(
    prefix="/api/v1/worker/tasks",
    tags=["worker"],
    responses={
        **COMMON_ERROR_RESPONSES,
        401: {"model": ErrorResponse, "description": "Worker 身份验证失败"},
        409: {"model": ErrorResponse, "description": "任务 Lease 或状态已失效"},
    },
)


def get_worker_task_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> TaskService:
    return TaskService(session)


@router.post(
    "/claim",
    response_model=WorkerTaskRead,
    responses={204: {"description": "当前设备没有待执行任务"}},
)
def claim_task(
    principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)],
    service: Annotated[TaskService, Depends(get_worker_task_service)],
) -> WorkerTaskRead | Response:
    task = service.claim(principal)
    if task is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return WorkerTaskRead(
        task_id=task.task_id,
        skill_id=task.skill_id,
        input=task.input_json,
        lease_until=task.lease_until,
    )


@router.post("/{task_id}/renew", response_model=TaskLeaseRead)
def renew_task(
    task_id: UUID,
    principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)],
    service: Annotated[TaskService, Depends(get_worker_task_service)],
) -> TaskLeaseRead:
    task = service.renew(principal, task_id)
    return TaskLeaseRead(
        task_id=task.task_id,
        status=task.status,
        lease_until=task.lease_until,
    )


@router.post("/{task_id}/complete", response_model=TaskRead)
def complete_task(
    task_id: UUID,
    data: TaskComplete,
    principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)],
    service: Annotated[TaskService, Depends(get_worker_task_service)],
) -> TaskRead:
    return task_to_read(service.complete(principal, task_id, data))


@router.post("/{task_id}/fail", response_model=TaskRead)
def fail_task(
    task_id: UUID,
    data: TaskFail,
    principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)],
    service: Annotated[TaskService, Depends(get_worker_task_service)],
) -> TaskRead:
    return task_to_read(service.fail(principal, task_id, data))
