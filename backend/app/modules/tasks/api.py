from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.exceptions import RequestValidationError
from pydantic import AwareDatetime, ValidationError
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.core.security import SecretCipher, get_secret_cipher
from app.modules.access.contracts import ActorContext
from app.modules.access.dependencies import require_module_access
from app.modules.access.module_access import ModuleCode
from app.modules.credentials.service import CredentialService
from app.modules.tasks.enums import TaskStatus
from app.modules.tasks.schemas import (
    ActiveTaskSummaryRead,
    TASK_EVENT_DEFAULT_LIMIT,
    TASK_EVENT_MAX_LIMIT,
    TaskCreate,
    TaskCreatedRange,
    TaskEventCursor,
    TaskEventListRead,
    TaskEventPurgeRead,
    TaskListItemRead,
    TaskRead,
    task_to_read,
)
from app.modules.tasks.service import TaskService
from app.shared.pagination import Page, PaginationParams


router = APIRouter(
    prefix="/api/v1/tasks",
    tags=["tasks"],
    responses={
        **COMMON_ERROR_RESPONSES,
        404: {"model": ErrorResponse, "description": "任务不存在"},
        409: {"model": ErrorResponse, "description": "任务状态冲突"},
    },
)


get_task_authorized_actor = require_module_access(ModuleCode.TASK)


def get_task_service(
    session: Annotated[Session, Depends(get_database_session)],
    cipher: Annotated[SecretCipher, Depends(get_secret_cipher)],
) -> TaskService:
    return TaskService(
        session,
        credential_service=CredentialService(session, cipher),
    )


def get_task_created_range(
    created_from: Annotated[AwareDatetime | None, Query()] = None,
    created_to: Annotated[AwareDatetime | None, Query()] = None,
) -> TaskCreatedRange:
    try:
        return TaskCreatedRange(
            created_from=created_from,
            created_to=created_to,
        )
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from error


def get_task_event_cursor(
    after_seq: Annotated[int | None, Query(ge=0)] = None,
    before_seq: Annotated[int | None, Query(gt=0)] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=TASK_EVENT_MAX_LIMIT),
    ] = TASK_EVENT_DEFAULT_LIMIT,
) -> TaskEventCursor:
    try:
        return TaskEventCursor(
            after_seq=after_seq,
            before_seq=before_seq,
            limit=limit,
        )
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from error


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    data: TaskCreate,
    actor: Annotated[ActorContext, Depends(get_task_authorized_actor)],
    service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskRead:
    return task_to_read(service.create(data, actor))


@router.get("", response_model=Page[TaskListItemRead])
def list_tasks(
    actor: Annotated[ActorContext, Depends(get_task_authorized_actor)],
    service: Annotated[TaskService, Depends(get_task_service)],
    pagination: Annotated[PaginationParams, Depends()],
    created_range: Annotated[TaskCreatedRange, Depends(get_task_created_range)],
    task_status: Annotated[TaskStatus | None, Query(alias="status")] = None,
    device_id: Annotated[UUID | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=500)] = None,
) -> Page[TaskListItemRead]:
    return service.list_management_tasks(
        actor=actor,
        page=pagination.page,
        page_size=pagination.page_size,
        status=task_status,
        device_id=device_id,
        search=search,
        created_from=created_range.created_from,
        created_to=created_range.created_to,
    )


@router.post(
    "/runtime-events/purge-expired",
    response_model=TaskEventPurgeRead,
)
def purge_expired_task_events(
    actor: Annotated[ActorContext, Depends(get_task_authorized_actor)],
    service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskEventPurgeRead:
    return service.purge_expired_events_for_actor(actor)


@router.get(
    "/active/{device_id}",
    response_model=ActiveTaskSummaryRead,
    responses={204: {"description": "设备当前没有活动任务"}},
)
def get_active_task(
    device_id: UUID,
    actor: Annotated[ActorContext, Depends(get_task_authorized_actor)],
    service: Annotated[TaskService, Depends(get_task_service)],
) -> ActiveTaskSummaryRead | Response:
    summary = service.get_active_summary(actor, device_id)
    if summary is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return summary


@router.get("/{task_id}", response_model=TaskRead)
def get_task(
    task_id: UUID,
    actor: Annotated[ActorContext, Depends(get_task_authorized_actor)],
    service: Annotated[TaskService, Depends(get_task_service)],
) -> TaskRead:
    return task_to_read(service.get(actor, task_id))


@router.get("/{task_id}/events", response_model=TaskEventListRead)
def list_task_events(
    task_id: UUID,
    actor: Annotated[ActorContext, Depends(get_task_authorized_actor)],
    service: Annotated[TaskService, Depends(get_task_service)],
    cursor: Annotated[TaskEventCursor, Depends(get_task_event_cursor)],
) -> TaskEventListRead:
    return service.list_events(
        actor,
        task_id,
        after_seq=cursor.after_seq,
        before_seq=cursor.before_seq,
        limit=cursor.limit,
    )
