from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.modules.tasks.schemas import (
    ActiveTaskSummaryRead,
    TaskCreate,
    TaskEventListRead,
    TaskRead,
    task_to_read,
)
from app.modules.tasks.service import TaskService


router = APIRouter(
    prefix="/api/v1/tasks",
    tags=["tasks"],
    responses={
        **COMMON_ERROR_RESPONSES,
        404: {"model": ErrorResponse, "description": "任务不存在"},
        409: {"model": ErrorResponse, "description": "任务状态冲突"},
    },
)


def get_task_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> TaskService:
    return TaskService(session)


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    data: TaskCreate,
    service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskRead:
    return task_to_read(service.create(data))


@router.get(
    "/active/{device_id}",
    response_model=ActiveTaskSummaryRead,
    responses={204: {"description": "设备当前没有活动任务"}},
)
def get_active_task(
    device_id: UUID,
    service: Annotated[TaskService, Depends(get_task_service)],
) -> ActiveTaskSummaryRead | Response:
    summary = service.get_active_summary(device_id)
    if summary is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return summary


@router.get("/{task_id}", response_model=TaskRead)
def get_task(
    task_id: UUID,
    service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskRead:
    return task_to_read(service.get(task_id))


@router.get("/{task_id}/events", response_model=TaskEventListRead)
def list_task_events(
    task_id: UUID,
    service: Annotated[TaskService, Depends(get_task_service)],
    after_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> TaskEventListRead:
    return service.list_events(task_id, after_seq=after_seq, limit=limit)
