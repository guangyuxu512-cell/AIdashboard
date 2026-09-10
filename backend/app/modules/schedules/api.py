from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.core.security import SecretCipher, get_secret_cipher
from app.modules.access.contracts import ActorContext
from app.modules.access.dependencies import require_module_access
from app.modules.access.module_access import ModuleCode
from app.modules.credentials.service import CredentialService
from app.modules.schedules.schemas import (
    ScheduleCreate,
    ScheduleListItemRead,
    ScheduleRead,
    ScheduleRunRead,
    ScheduleUpdate,
)
from app.modules.schedules.service import ScheduleService
from app.modules.schedules.time_rules import get_schedule_timezone
from app.modules.tasks.service import TaskService
from app.shared.pagination import Page, PaginationParams


router = APIRouter(
    prefix="/api/v1/schedules",
    tags=["schedules"],
    responses={
        **COMMON_ERROR_RESPONSES,
        404: {"model": ErrorResponse, "description": "定时计划不存在"},
    },
)


get_schedule_authorized_actor = require_module_access(ModuleCode.SCHEDULE)


def get_schedule_service(
    session: Annotated[Session, Depends(get_database_session)],
    cipher: Annotated[SecretCipher, Depends(get_secret_cipher)],
) -> ScheduleService:
    return ScheduleService(
        session,
        task_service=TaskService(
            session,
            credential_service=CredentialService(session, cipher),
        ),
    )


@router.post("", response_model=ScheduleRead, status_code=status.HTTP_201_CREATED)
def create_schedule(
    data: ScheduleCreate,
    actor: Annotated[ActorContext, Depends(get_schedule_authorized_actor)],
    service: Annotated[ScheduleService, Depends(get_schedule_service)],
) -> ScheduleRead:
    return service.create(data, actor)


@router.get("", response_model=Page[ScheduleListItemRead])
def list_schedules(
    actor: Annotated[ActorContext, Depends(get_schedule_authorized_actor)],
    service: Annotated[ScheduleService, Depends(get_schedule_service)],
    pagination: Annotated[PaginationParams, Depends()],
    enabled: Annotated[bool | None, Query()] = None,
    device_id: Annotated[UUID | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=500)] = None,
    occurrence_date: Annotated[date | None, Query()] = None,
    view_timezone: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[ScheduleListItemRead]:
    if (occurrence_date is None) != (view_timezone is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="occurrence_date and view_timezone must be supplied together",
        )
    if view_timezone is not None:
        try:
            get_schedule_timezone(view_timezone)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
    return service.list_management(
        actor=actor,
        page=pagination.page,
        page_size=pagination.page_size,
        enabled=enabled,
        device_id=device_id,
        search=search,
        occurrence_date=occurrence_date,
        view_timezone=view_timezone,
    )


@router.get("/{schedule_id}", response_model=ScheduleRead)
def get_schedule(
    schedule_id: UUID,
    actor: Annotated[ActorContext, Depends(get_schedule_authorized_actor)],
    service: Annotated[ScheduleService, Depends(get_schedule_service)],
) -> ScheduleRead:
    return service.get(actor, schedule_id)


@router.patch("/{schedule_id}", response_model=ScheduleRead)
def update_schedule(
    schedule_id: UUID,
    data: ScheduleUpdate,
    actor: Annotated[ActorContext, Depends(get_schedule_authorized_actor)],
    service: Annotated[ScheduleService, Depends(get_schedule_service)],
) -> ScheduleRead:
    return service.update(schedule_id, data, actor)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: UUID,
    actor: Annotated[ActorContext, Depends(get_schedule_authorized_actor)],
    service: Annotated[ScheduleService, Depends(get_schedule_service)],
) -> Response:
    service.archive(schedule_id, actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{schedule_id}/runs", response_model=Page[ScheduleRunRead])
def list_schedule_runs(
    schedule_id: UUID,
    actor: Annotated[ActorContext, Depends(get_schedule_authorized_actor)],
    service: Annotated[ScheduleService, Depends(get_schedule_service)],
    pagination: Annotated[PaginationParams, Depends()],
) -> Page[ScheduleRunRead]:
    return service.list_runs(
        schedule_id,
        actor,
        page=pagination.page,
        page_size=pagination.page_size,
    )
