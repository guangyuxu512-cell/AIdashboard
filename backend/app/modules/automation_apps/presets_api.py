from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.modules.access.contracts import ActorContext
from app.modules.access.dependencies import require_module_access
from app.modules.access.module_access import ModuleCode
from app.modules.automation_apps.schemas import (
    AutomationParameterPresetCopy,
    AutomationParameterPresetCreate,
    AutomationParameterPresetRead,
    AutomationParameterPresetUpdate,
)
from app.modules.automation_apps.service import AutomationParameterPresetService
from app.shared.pagination import Page, PaginationParams


router = APIRouter(
    prefix="/api/v1/automation-app-configs/yingdao/{app_id}/parameter-presets",
    tags=["automation-parameter-presets"],
    responses={
        **COMMON_ERROR_RESPONSES,
        404: {"model": ErrorResponse, "description": "参数预设不存在"},
        409: {
            "model": ErrorResponse,
            "description": "参数预设名称冲突或仍被未归档计划引用",
        },
    },
)

management_router = APIRouter(
    prefix="/api/v1/automation-parameter-presets",
    tags=["automation-parameter-presets"],
    responses=COMMON_ERROR_RESPONSES,
)


get_device_authorized_actor = require_module_access(ModuleCode.DEVICE)


def get_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> AutomationParameterPresetService:
    return AutomationParameterPresetService(session)


@management_router.get(
    "",
    response_model=Page[AutomationParameterPresetRead] | list[AutomationParameterPresetRead],
    description="Without page/page_size returns the legacy array; either pagination parameter opts into Page. Invalid or empty values return 422.",
)
def list_all_presets(
    request: Request,
    actor: Annotated[ActorContext, Depends(get_device_authorized_actor)],
    service: Annotated[AutomationParameterPresetService, Depends(get_service)],
    pagination: Annotated[PaginationParams, Depends()],
    device_id: UUID | None = None,
    app_id: str | None = Query(default=None, min_length=1, max_length=200),
    q: str | None = Query(default=None, min_length=1, max_length=100),
) -> Page[AutomationParameterPresetRead] | list[AutomationParameterPresetRead]:
    return service.list_all(
        actor=actor,
        device_id=device_id,
        app_id=app_id,
        name_query=q.strip() if q is not None else None,
        pagination=(
            pagination
            if "page" in request.query_params or "page_size" in request.query_params
            else None
        ),
    )


@router.get("", response_model=list[AutomationParameterPresetRead])
def list_presets(
    app_id: str,
    actor: Annotated[ActorContext, Depends(get_device_authorized_actor)],
    service: Annotated[AutomationParameterPresetService, Depends(get_service)],
) -> list[AutomationParameterPresetRead]:
    return service.list(actor=actor, app_id=app_id)


@router.post(
    "",
    response_model=AutomationParameterPresetRead,
    status_code=status.HTTP_201_CREATED,
)
def create_preset(
    app_id: str,
    data: AutomationParameterPresetCreate,
    actor: Annotated[ActorContext, Depends(get_device_authorized_actor)],
    service: Annotated[AutomationParameterPresetService, Depends(get_service)],
) -> AutomationParameterPresetRead:
    return service.create(actor=actor, app_id=app_id, data=data)


@router.get("/{preset_id}", response_model=AutomationParameterPresetRead)
def get_preset(
    app_id: str,
    preset_id: UUID,
    actor: Annotated[ActorContext, Depends(get_device_authorized_actor)],
    service: Annotated[AutomationParameterPresetService, Depends(get_service)],
) -> AutomationParameterPresetRead:
    return service.get(actor=actor, app_id=app_id, preset_id=preset_id)


@router.patch("/{preset_id}", response_model=AutomationParameterPresetRead)
def update_preset(
    app_id: str,
    preset_id: UUID,
    data: AutomationParameterPresetUpdate,
    actor: Annotated[ActorContext, Depends(get_device_authorized_actor)],
    service: Annotated[AutomationParameterPresetService, Depends(get_service)],
) -> AutomationParameterPresetRead:
    return service.update(
        actor=actor,
        app_id=app_id,
        preset_id=preset_id,
        data=data,
    )


@router.delete("/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_preset(
    app_id: str,
    preset_id: UUID,
    actor: Annotated[ActorContext, Depends(get_device_authorized_actor)],
    service: Annotated[AutomationParameterPresetService, Depends(get_service)],
) -> None:
    service.remove(actor=actor, app_id=app_id, preset_id=preset_id)


@router.post(
    "/{preset_id}/copy",
    response_model=AutomationParameterPresetRead,
    status_code=status.HTTP_201_CREATED,
)
def copy_preset(
    app_id: str,
    preset_id: UUID,
    data: AutomationParameterPresetCopy,
    actor: Annotated[ActorContext, Depends(get_device_authorized_actor)],
    service: Annotated[AutomationParameterPresetService, Depends(get_service)],
) -> AutomationParameterPresetRead:
    return service.copy(
        actor=actor,
        app_id=app_id,
        preset_id=preset_id,
        data=data,
    )
