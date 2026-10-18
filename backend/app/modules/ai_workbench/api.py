from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.modules.access.contracts import ActorContext
from app.modules.access.dependencies import require_module_access
from app.modules.access.module_access import ModuleCode
from app.modules.ai_workbench.enums import (
    GenerationJobStatus,
    GenerationMode,
    GenerationWorkMode,
)
from app.modules.ai_workbench.generation_service import (
    GenerationService,
    generation_counts,
    generation_input_summary,
)
from app.modules.ai_workbench.models import (
    GenerationItem,
    GenerationJob,
    ProductMaterialGroup,
    TemplateGroup,
)
from app.modules.ai_workbench.repository import GenerationCounts, GenerationInputSummary
from app.modules.ai_workbench.schemas import (
    GenerationCountsRead,
    GenerationItemArchiveRequest,
    GenerationItemAssetRead,
    GenerationItemRead,
    GenerationInputSummaryRead,
    GenerationJobRead,
    GenerationJobSummaryRead,
    GenerationRetryRequest,
    GenerationSubmit,
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
from app.modules.ai_workbench.asset_service import AiAssetService
from app.modules.assets.api import asset_content_response
from app.modules.assets.schemas import AssetRead
from app.modules.assets.thumbnails import THUMBNAIL_CONTENT_TYPE
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
        413: {"model": ErrorResponse, "description": "图片超过单文件大小限制"},
        422: {"model": ErrorResponse, "description": "请求字段或业务关系无效"},
        503: {"model": ErrorResponse, "description": "资产存储或缩略图暂不可用"},
    },
)


router = APIRouter(
    prefix="/api/v1/ai-workbench",
    tags=["ai-workbench"],
    responses=AI_WORKBENCH_ERROR_RESPONSES,
)


get_ai_workbench_authorized_actor = require_module_access(ModuleCode.AI_WORKBENCH)


def get_ai_asset_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> AiAssetService:
    return AiAssetService(session)


@router.post("/assets", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
def upload_ai_asset(
    file: Annotated[UploadFile, File()],
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[AiAssetService, Depends(get_ai_asset_service)],
) -> AssetRead:
    return AssetRead.model_validate(
        service.upload(
            actor=actor,
            original_filename=file.filename,
            content_type=file.content_type,
            stream=file.file,
        )
    )


@router.get("/assets/{asset_id}/content", response_class=StreamingResponse)
def read_ai_asset_content(
    asset_id: UUID,
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[AiAssetService, Depends(get_ai_asset_service)],
) -> StreamingResponse:
    asset, content = service.get_content(actor, asset_id)
    return asset_content_response(asset.content_type, asset.size_bytes, content)


@router.get("/assets/{asset_id}/thumbnail", response_class=StreamingResponse)
def read_ai_asset_thumbnail(
    asset_id: UUID,
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[AiAssetService, Depends(get_ai_asset_service)],
) -> StreamingResponse:
    _asset, content, size = service.get_thumbnail(actor, asset_id)
    return asset_content_response(
        THUMBNAIL_CONTENT_TYPE, size, content, cache_control="private, max-age=3600"
    )


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def cleanup_ai_asset(
    asset_id: UUID,
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[AiAssetService, Depends(get_ai_asset_service)],
) -> Response:
    service.cleanup(actor, asset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def get_ai_workbench_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> AiWorkbenchService:
    return AiWorkbenchService(session)


def get_generation_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> GenerationService:
    return GenerationService(session)


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


def _generation_counts_read(counts: GenerationCounts) -> GenerationCountsRead:
    return GenerationCountsRead(
        total_count=counts.total_count,
        pending_count=counts.pending_count,
        running_count=counts.running_count,
        success_count=counts.success_count,
        failed_count=counts.failed_count,
    )


def _generation_job_summary_read(
    job: GenerationJob,
    counts: GenerationCounts,
    input_summary: GenerationInputSummary,
) -> GenerationJobSummaryRead:
    return GenerationJobSummaryRead(
        generation_job_id=job.generation_job_id,
        model_id=job.model_id,
        model_code=job.model.model_code,
        model_display_name=job.model.display_name,
        work_mode=job.work_mode,
        mode=job.mode,
        compress_output_under_1000kb=job.compress_output_under_1000kb,
        status=job.status,
        input_summary=GenerationInputSummaryRead(
            count=input_summary.count,
            primary_name=input_summary.primary_name,
        ),
        created_by_display_name=job.created_by_display_name,
        created_at=job.created_at,
        updated_at=job.updated_at,
        **_generation_counts_read(counts).model_dump(),
    )


def _generation_item_read(item: GenerationItem) -> GenerationItemRead:
    role_order = {"PRODUCT_SOURCE": 0, "STYLE_REFERENCE": 1}
    input_assets = sorted(
        item.input_assets,
        key=lambda link: (
            role_order[link.input_role],
            link.position,
            str(link.asset_id),
        ),
    )
    return GenerationItemRead(
        generation_item_id=item.generation_item_id,
        position=item.position,
        status=item.status,
        final_prompt=item.final_prompt,
        output_role=item.output_role,
        output_format=item.output_format,
        size=item.size,
        source_product_position=item.source_product_position,
        source_template_group_position=item.source_template_group_position,
        source_prompt_template_position=item.source_prompt_template_position,
        output_ordinal=item.output_ordinal,
        source_product_material_group_id=item.source_product_material_group_id,
        source_template_group_id=item.source_template_group_id,
        source_prompt_template_id=item.source_prompt_template_id,
        product_name_snapshot=item.product_name_snapshot,
        template_group_name_snapshot=item.template_group_name_snapshot,
        prompt_template_name_snapshot=item.prompt_template_name_snapshot,
        attempt_count=item.attempt_count,
        last_failure_code=item.last_failure_code,
        last_failure_message=item.last_failure_message,
        last_failed_at=item.last_failed_at,
        started_at=item.started_at,
        finished_at=item.finished_at,
        archived_material_group_id=item.archived_material_group_id,
        archived_material_group_name_snapshot=(
            item.archived_material_group_name_snapshot
        ),
        archived_at=item.archived_at,
        input_assets=[
            GenerationItemAssetRead(
                input_role=link.input_role,
                position=link.position,
                asset=AssetRead.model_validate(link.asset),
            )
            for link in input_assets
        ],
        output_asset=(
            AssetRead.model_validate(item.output_asset)
            if item.output_asset is not None
            else None
        ),
    )


def _generation_job_read(job: GenerationJob) -> GenerationJobRead:
    counts = generation_counts(job.items)
    summary = _generation_job_summary_read(
        job,
        counts,
        generation_input_summary(job),
    )
    return GenerationJobRead(
        **summary.model_dump(),
        submission_key=job.submission_key,
        started_at=job.started_at,
        finished_at=job.finished_at,
        items=[
            _generation_item_read(item)
            for item in sorted(
                job.items,
                key=lambda candidate: (
                    candidate.position,
                    str(candidate.generation_item_id),
                ),
            )
        ],
    )


@router.post(
    "/generation-jobs",
    response_model=GenerationJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_generation(
    data: GenerationSubmit,
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[GenerationService, Depends(get_generation_service)],
) -> GenerationJobRead:
    return _generation_job_read(service.submit(actor, data))


@router.get(
    "/generation-jobs",
    response_model=Page[GenerationJobSummaryRead],
)
def list_generation_jobs(
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[GenerationService, Depends(get_generation_service)],
    pagination: Annotated[PaginationParams, Depends()],
    work_mode: GenerationWorkMode | None = None,
    mode: GenerationMode | None = None,
    generation_status: Annotated[
        GenerationJobStatus | None,
        Query(alias="status"),
    ] = None,
) -> Page[GenerationJobSummaryRead]:
    jobs, total = service.list(
        actor=actor,
        page=pagination.page,
        page_size=pagination.page_size,
        work_mode=work_mode,
        mode=mode,
        status=generation_status,
    )
    return Page(
        items=[
            _generation_job_summary_read(job, counts, input_summary)
            for job, counts, input_summary in jobs
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/generation-jobs/{generation_job_id}",
    response_model=GenerationJobRead,
)
def get_generation_job(
    generation_job_id: UUID,
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[GenerationService, Depends(get_generation_service)],
) -> GenerationJobRead:
    return _generation_job_read(service.get(actor, generation_job_id))


@router.post(
    "/generation-jobs/{generation_job_id}/retry-failed-items",
    response_model=GenerationJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_failed_generation_items(
    generation_job_id: UUID,
    data: GenerationRetryRequest,
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[GenerationService, Depends(get_generation_service)],
) -> GenerationJobRead:
    return _generation_job_read(
        service.retry_failed_items(actor, generation_job_id, data),
    )


@router.post(
    "/generation-jobs/{generation_job_id}/items/{generation_item_id}/archive",
    response_model=GenerationJobRead,
)
def archive_instant_generation_item(
    generation_job_id: UUID,
    generation_item_id: UUID,
    data: GenerationItemArchiveRequest,
    actor: Annotated[ActorContext, Depends(get_ai_workbench_authorized_actor)],
    service: Annotated[GenerationService, Depends(get_generation_service)],
) -> GenerationJobRead:
    return _generation_job_read(
        service.archive_instant_item(
            actor,
            generation_job_id,
            generation_item_id,
            data,
        ),
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
