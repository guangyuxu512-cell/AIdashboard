from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.modules.access.contracts import ActorContext
from app.modules.access.dependencies import require_module_access
from app.modules.access.module_access import ModuleCode
from app.modules.ai_workbench.enums import GenerationMode
from app.modules.ai_workbench.models import ProductMaterialGroup, TemplateGroup
from app.modules.ai_workbench.schemas import (
    MaterialGroupAssetAttach,
    MaterialGroupAssetRead,
    MaterialGroupTemplateBindingRead,
    ProductMaterialGroupCreate,
    ProductMaterialGroupRead,
    ProductMaterialGroupSummaryRead,
    ProductMaterialGroupUpdate,
    PromptTemplateCreate,
    PromptTemplateRead,
    PromptTemplateReorder,
    PromptTemplateUpdate,
    TemplateBindingReplace,
    TemplateGroupCreate,
    TemplateGroupRead,
    TemplateGroupSummaryRead,
    TemplateGroupUpdate,
)
from app.modules.ai_workbench.service import AiWorkbenchService
from app.modules.assets.schemas import AssetRead
from app.shared.pagination import Page, PaginationParams


AI_WORKBENCH_ERROR_RESPONSES = cast(
    dict[int | str, dict[str, Any]],
    COMMON_ERROR_RESPONSES.copy(),
)
AI_WORKBENCH_ERROR_RESPONSES.update(
    {
        401: {"model": ErrorResponse, "description": "需要有效的管理端用户身份"},
        403: {"model": ErrorResponse, "description": "无权使用 AI 工作台或指定团队"},
        404: {"model": ErrorResponse, "description": "管理数据或资产不存在"},
        409: {"model": ErrorResponse, "description": "当前业务状态不允许该操作"},
        422: {"model": ErrorResponse, "description": "请求字段或业务关系无效"},
    },
)


router = APIRouter(
    prefix="/api/v1/ai-workbench",
    tags=["ai-workbench"],
    responses=AI_WORKBENCH_ERROR_RESPONSES,
)


get_ai_workbench_authorized_actor = require_module_access(ModuleCode.AI_WORKBENCH)


def get_ai_workbench_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> AiWorkbenchService:
    return AiWorkbenchService(session)


def _template_group_read(group: TemplateGroup) -> TemplateGroupRead:
    return TemplateGroupRead(
        template_group_id=group.template_group_id,
        name=group.name,
        mode=group.mode,
        enabled=group.enabled,
        created_at=group.created_at,
        updated_at=group.updated_at,
        prompt_templates=[
            PromptTemplateRead.model_validate(prompt)
            for prompt in sorted(
                group.prompt_templates,
                key=lambda item: (item.sort_order, str(item.prompt_template_id)),
            )
        ],
    )


def _product_material_group_read(
    group: ProductMaterialGroup,
) -> ProductMaterialGroupRead:
    assets = sorted(
        group.asset_links,
        key=lambda link: (link.created_at, str(link.asset_id)),
    )
    mode_order = {
        GenerationMode.NORMAL_GENERATION.value: 0,
        GenerationMode.STYLE_REPLICATION.value: 1,
    }
    bindings = sorted(
        group.template_bindings,
        key=lambda binding: (
            mode_order[binding.generation_mode],
            binding.position,
            str(binding.template_group_id),
        ),
    )
    return ProductMaterialGroupRead(
        material_group_id=group.material_group_id,
        name=group.name,
        enabled=group.enabled,
        normal_generation_enabled=group.normal_generation_enabled,
        style_replication_enabled=group.style_replication_enabled,
        created_at=group.created_at,
        updated_at=group.updated_at,
        assets=[
            MaterialGroupAssetRead(
                role=link.role,
                created_at=link.created_at,
                asset=AssetRead.model_validate(link.asset),
            )
            for link in assets
        ],
        template_bindings=[
            MaterialGroupTemplateBindingRead.model_validate(binding)
            for binding in bindings
        ],
    )


@router.get("/template-groups", response_model=Page[TemplateGroupSummaryRead])
def list_template_groups(
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[AiWorkbenchService, Depends(get_ai_workbench_service)],
    pagination: Annotated[PaginationParams, Depends()],
    search: Annotated[str | None, Query(max_length=100)] = None,
    mode: GenerationMode | None = None,
    enabled: bool | None = None,
) -> Page[TemplateGroupSummaryRead]:
    groups, total = service.list_template_groups(
        actor=actor,
        page=pagination.page,
        page_size=pagination.page_size,
        search=search,
        mode=mode,
        enabled=enabled,
    )
    return Page(
        items=[TemplateGroupSummaryRead.model_validate(group) for group in groups],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post(
    "/template-groups",
    response_model=TemplateGroupRead,
    status_code=status.HTTP_201_CREATED,
)
def create_template_group(
    data: TemplateGroupCreate,
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[AiWorkbenchService, Depends(get_ai_workbench_service)],
) -> TemplateGroupRead:
    return _template_group_read(service.create_template_group(actor, data))


@router.get("/template-groups/{template_group_id}", response_model=TemplateGroupRead)
def get_template_group(
    template_group_id: UUID,
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[AiWorkbenchService, Depends(get_ai_workbench_service)],
) -> TemplateGroupRead:
    return _template_group_read(service.get_template_group(actor, template_group_id))


@router.patch("/template-groups/{template_group_id}", response_model=TemplateGroupRead)
def update_template_group(
    template_group_id: UUID,
    data: TemplateGroupUpdate,
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[AiWorkbenchService, Depends(get_ai_workbench_service)],
) -> TemplateGroupRead:
    return _template_group_read(
        service.update_template_group(actor, template_group_id, data),
    )


@router.delete(
    "/template-groups/{template_group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_template_group(
    template_group_id: UUID,
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[AiWorkbenchService, Depends(get_ai_workbench_service)],
) -> Response:
    service.delete_template_group(actor, template_group_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/template-groups/{template_group_id}/prompt-templates",
    response_model=TemplateGroupRead,
    status_code=status.HTTP_201_CREATED,
)
def create_prompt_template(
    template_group_id: UUID,
    data: PromptTemplateCreate,
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[AiWorkbenchService, Depends(get_ai_workbench_service)],
) -> TemplateGroupRead:
    return _template_group_read(
        service.create_prompt_template(actor, template_group_id, data),
    )


@router.patch(
    "/template-groups/{template_group_id}/prompt-templates/{prompt_template_id}",
    response_model=TemplateGroupRead,
)
def update_prompt_template(
    template_group_id: UUID,
    prompt_template_id: UUID,
    data: PromptTemplateUpdate,
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[AiWorkbenchService, Depends(get_ai_workbench_service)],
) -> TemplateGroupRead:
    return _template_group_read(
        service.update_prompt_template(
            actor,
            template_group_id,
            prompt_template_id,
            data,
        ),
    )


@router.delete(
    "/template-groups/{template_group_id}/prompt-templates/{prompt_template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_prompt_template(
    template_group_id: UUID,
    prompt_template_id: UUID,
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[AiWorkbenchService, Depends(get_ai_workbench_service)],
) -> Response:
    service.delete_prompt_template(actor, template_group_id, prompt_template_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/template-groups/{template_group_id}/prompt-templates/{prompt_template_id}/duplicate",
    response_model=TemplateGroupRead,
    status_code=status.HTTP_201_CREATED,
)
def duplicate_prompt_template(
    template_group_id: UUID,
    prompt_template_id: UUID,
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[AiWorkbenchService, Depends(get_ai_workbench_service)],
) -> TemplateGroupRead:
    return _template_group_read(
        service.duplicate_prompt_template(
            actor,
            template_group_id,
            prompt_template_id,
        ),
    )


@router.put(
    "/template-groups/{template_group_id}/prompt-templates/reorder",
    response_model=TemplateGroupRead,
)
def reorder_prompt_templates(
    template_group_id: UUID,
    data: PromptTemplateReorder,
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[AiWorkbenchService, Depends(get_ai_workbench_service)],
) -> TemplateGroupRead:
    return _template_group_read(
        service.reorder_prompt_templates(actor, template_group_id, data),
    )


@router.get(
    "/product-material-groups",
    response_model=Page[ProductMaterialGroupSummaryRead],
)
def list_product_material_groups(
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[AiWorkbenchService, Depends(get_ai_workbench_service)],
    pagination: Annotated[PaginationParams, Depends()],
    search: Annotated[str | None, Query(max_length=100)] = None,
    enabled: bool | None = None,
) -> Page[ProductMaterialGroupSummaryRead]:
    groups, total = service.list_product_material_groups(
        actor=actor,
        page=pagination.page,
        page_size=pagination.page_size,
        search=search,
        enabled=enabled,
    )
    return Page(
        items=[ProductMaterialGroupSummaryRead.model_validate(group) for group in groups],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post(
    "/product-material-groups",
    response_model=ProductMaterialGroupRead,
    status_code=status.HTTP_201_CREATED,
)
def create_product_material_group(
    data: ProductMaterialGroupCreate,
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[AiWorkbenchService, Depends(get_ai_workbench_service)],
) -> ProductMaterialGroupRead:
    return _product_material_group_read(
        service.create_product_material_group(actor, data),
    )


@router.get(
    "/product-material-groups/{material_group_id}",
    response_model=ProductMaterialGroupRead,
)
def get_product_material_group(
    material_group_id: UUID,
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[AiWorkbenchService, Depends(get_ai_workbench_service)],
) -> ProductMaterialGroupRead:
    return _product_material_group_read(
        service.get_product_material_group(actor, material_group_id),
    )


@router.patch(
    "/product-material-groups/{material_group_id}",
    response_model=ProductMaterialGroupRead,
)
def update_product_material_group(
    material_group_id: UUID,
    data: ProductMaterialGroupUpdate,
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[AiWorkbenchService, Depends(get_ai_workbench_service)],
) -> ProductMaterialGroupRead:
    return _product_material_group_read(
        service.update_product_material_group(actor, material_group_id, data),
    )


@router.delete(
    "/product-material-groups/{material_group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_product_material_group(
    material_group_id: UUID,
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[AiWorkbenchService, Depends(get_ai_workbench_service)],
) -> Response:
    service.delete_product_material_group(actor, material_group_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/product-material-groups/{material_group_id}/assets",
    response_model=ProductMaterialGroupRead,
)
def attach_asset(
    material_group_id: UUID,
    data: MaterialGroupAssetAttach,
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[AiWorkbenchService, Depends(get_ai_workbench_service)],
) -> ProductMaterialGroupRead:
    return _product_material_group_read(
        service.attach_asset(actor, material_group_id, data),
    )


@router.delete(
    "/product-material-groups/{material_group_id}/assets/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def detach_asset(
    material_group_id: UUID,
    asset_id: UUID,
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[AiWorkbenchService, Depends(get_ai_workbench_service)],
) -> Response:
    service.detach_asset(actor, material_group_id, asset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/product-material-groups/{material_group_id}/template-bindings/{mode}",
    response_model=ProductMaterialGroupRead,
)
def replace_template_bindings(
    material_group_id: UUID,
    mode: GenerationMode,
    data: TemplateBindingReplace,
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[AiWorkbenchService, Depends(get_ai_workbench_service)],
) -> ProductMaterialGroupRead:
    return _product_material_group_read(
        service.replace_template_bindings(actor, material_group_id, mode, data),
    )
