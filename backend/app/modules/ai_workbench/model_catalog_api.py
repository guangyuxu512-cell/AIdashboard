from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.modules.access.contracts import ActorContext
from app.modules.access.dependencies import (
    get_super_account,
    require_module_access,
)
from app.modules.access.module_access import ModuleCode
from app.modules.ai_workbench.model_catalog_schemas import (
    AiModelAdminRead,
    AiModelCatalogRead,
    AiModelCreate,
    AiModelUpdate,
)
from app.modules.ai_workbench.model_catalog_service import AiModelCatalogService


AI_MODEL_ERROR_RESPONSES = {
    **COMMON_ERROR_RESPONSES,
    404: {"model": ErrorResponse, "description": "AI模型不存在"},
    409: {"model": ErrorResponse, "description": "模型标识或默认状态冲突"},
    422: {"model": ErrorResponse, "description": "模型配置无效"},
}


admin_router = APIRouter(
    prefix="/api/v1/ai-models",
    tags=["ai-model-management"],
    responses=AI_MODEL_ERROR_RESPONSES,
)
catalog_router = APIRouter(
    prefix="/api/v1/ai-workbench/models",
    tags=["ai-workbench"],
    responses=AI_MODEL_ERROR_RESPONSES,
)


get_ai_model_catalog_authorized_actor = require_module_access(
    ModuleCode.AI_WORKBENCH,
)


def get_ai_model_catalog_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> AiModelCatalogService:
    return AiModelCatalogService(session)


@admin_router.get("", response_model=list[AiModelAdminRead])
def list_ai_models(
    _actor: Annotated[ActorContext, Depends(get_super_account)],
    service: Annotated[
        AiModelCatalogService,
        Depends(get_ai_model_catalog_service),
    ],
) -> list[AiModelAdminRead]:
    return [AiModelAdminRead.model_validate(model) for model in service.list_models()]


@admin_router.post(
    "",
    response_model=AiModelAdminRead,
    status_code=status.HTTP_201_CREATED,
)
def create_ai_model(
    data: AiModelCreate,
    _actor: Annotated[ActorContext, Depends(get_super_account)],
    service: Annotated[
        AiModelCatalogService,
        Depends(get_ai_model_catalog_service),
    ],
) -> AiModelAdminRead:
    return AiModelAdminRead.model_validate(service.create_model(data))


@admin_router.get("/{model_id}", response_model=AiModelAdminRead)
def get_ai_model(
    model_id: UUID,
    _actor: Annotated[ActorContext, Depends(get_super_account)],
    service: Annotated[
        AiModelCatalogService,
        Depends(get_ai_model_catalog_service),
    ],
) -> AiModelAdminRead:
    return AiModelAdminRead.model_validate(service.get_model(model_id))


@admin_router.patch("/{model_id}", response_model=AiModelAdminRead)
def update_ai_model(
    model_id: UUID,
    data: AiModelUpdate,
    _actor: Annotated[ActorContext, Depends(get_super_account)],
    service: Annotated[
        AiModelCatalogService,
        Depends(get_ai_model_catalog_service),
    ],
) -> AiModelAdminRead:
    return AiModelAdminRead.model_validate(service.update_model(model_id, data))


@admin_router.post("/{model_id}/default", response_model=AiModelAdminRead)
def set_default_ai_model(
    model_id: UUID,
    _actor: Annotated[ActorContext, Depends(get_super_account)],
    service: Annotated[
        AiModelCatalogService,
        Depends(get_ai_model_catalog_service),
    ],
) -> AiModelAdminRead:
    return AiModelAdminRead.model_validate(service.set_default_model(model_id))


@catalog_router.get("", response_model=list[AiModelCatalogRead])
def list_available_ai_models(
    _actor: Annotated[
        ActorContext,
        Depends(get_ai_model_catalog_authorized_actor),
    ],
    service: Annotated[
        AiModelCatalogService,
        Depends(get_ai_model_catalog_service),
    ],
) -> list[AiModelCatalogRead]:
    return [
        AiModelCatalogRead.model_validate(model)
        for model in service.list_available_models()
    ]
