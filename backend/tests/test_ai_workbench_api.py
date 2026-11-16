import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient, Response

from app.core.database import get_database_session
from app.main import create_app
from app.modules.access.contracts import ActorContext
from app.modules.access.dependencies import (
    get_actor_context,
    get_module_access_service,
)
from app.modules.access.enums import DataScope
from app.modules.access.exceptions import ModuleAccessDeniedError
from app.modules.access.module_access import ModuleCode
from app.modules.ai_workbench.api import (
    get_ai_workbench_authorized_actor,
    get_ai_workbench_service,
    get_generation_service,
)
from app.modules.ai_workbench.enums import GenerationMode, GenerationWorkMode
from app.modules.ai_workbench.exceptions import TemplateGroupInUseError
from app.modules.ai_workbench.models import (
    AiModel,
    GenerationItem,
    GenerationItemAsset,
    GenerationJob,
    MaterialGroupAsset,
    ProductMaterialGroup,
    TemplateGroup,
)
from app.modules.ai_workbench.repository import GenerationCounts, GenerationInputSummary
from app.modules.ai_workbench.schemas import (
    ProductMaterialGroupCreate,
    TemplateGroupCreate,
)
from app.modules.assets.enums import AssetMediaType, AssetSourceType
from app.modules.assets.models import Asset
from tests.support import FakeSession


ACTOR = ActorContext(
    user_id=uuid4(),
    user_display_name="AI API 用户",
    team_id=uuid4(),
    membership_id=uuid4(),
    role_code="member",
    data_scope=DataScope.TEAM,
)


def stamp(entity: object) -> None:
    now = datetime.now(UTC)
    entity.created_at = now  # type: ignore[attr-defined]
    if hasattr(entity, "updated_at"):
        entity.updated_at = now  # type: ignore[attr-defined]


class ApiAiWorkbenchService:
    def __init__(self) -> None:
        self.template_groups: dict[UUID, TemplateGroup] = {}
        self.material_groups: dict[UUID, ProductMaterialGroup] = {}
        self.reject_template_delete = False

    def list_template_groups(self, **kwargs: object) -> tuple[list[TemplateGroup], int]:
        page = int(kwargs["page"])
        page_size = int(kwargs["page_size"])
        values = list(self.template_groups.values())
        start = (page - 1) * page_size
        return values[start : start + page_size], len(values)

    def create_template_group(
        self,
        actor: ActorContext,
        data: TemplateGroupCreate,
    ) -> TemplateGroup:
        group = TemplateGroup(
            template_group_id=uuid4(),
            team_id=actor.team_id,
            created_by_user_id=actor.user_id,
            name=data.name,
            mode=data.mode.value,
            enabled=data.enabled,
        )
        stamp(group)
        self.template_groups[group.template_group_id] = group
        return group

    def get_template_group(
        self,
        actor: ActorContext,
        template_group_id: UUID,
    ) -> TemplateGroup:
        del actor
        return self.template_groups[template_group_id]

    def delete_template_group(
        self,
        actor: ActorContext,
        template_group_id: UUID,
    ) -> None:
        del actor
        if self.reject_template_delete:
            raise TemplateGroupInUseError()
        del self.template_groups[template_group_id]

    def list_product_material_groups(
        self,
        **kwargs: object,
    ) -> tuple[list[ProductMaterialGroup], int]:
        page = int(kwargs["page"])
        page_size = int(kwargs["page_size"])
        values = list(self.material_groups.values())
        start = (page - 1) * page_size
        return values[start : start + page_size], len(values)

    def create_product_material_group(
        self,
        actor: ActorContext,
        data: ProductMaterialGroupCreate,
    ) -> ProductMaterialGroup:
        group = ProductMaterialGroup(
            material_group_id=uuid4(),
            team_id=actor.team_id,
            created_by_user_id=actor.user_id,
            **data.model_dump(),
        )
        stamp(group)
        self.material_groups[group.material_group_id] = group
        return group

    def get_product_material_group(
        self,
        actor: ActorContext,
        material_group_id: UUID,
    ) -> ProductMaterialGroup:
        del actor
        return self.material_groups[material_group_id]


class ApiModuleAccessService:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.checked: list[ModuleCode] = []

    def require_module_access(
        self,
        actor: ActorContext,
        module_code: ModuleCode,
    ) -> None:
        del actor
        self.checked.append(module_code)
        if not self.allowed:
            raise ModuleAccessDeniedError()


class ApiGenerationService:
    def __init__(self) -> None:
        self.job: GenerationJob | None = None

    def submit(self, actor: ActorContext, data: object) -> GenerationJob:
        product_asset_id = data.product_asset_ids[0]  # type: ignore[attr-defined]
        asset = Asset(
            asset_id=product_asset_id,
            team_id=actor.team_id,
            created_by_user_id=actor.user_id,
            original_filename="source.png",
            storage_key="private/source.png",
            media_type=AssetMediaType.IMAGE.value,
            source_type=AssetSourceType.UPLOAD.value,
            content_type="image/png",
            size_bytes=32,
            sha256="c" * 64,
        )
        stamp(asset)
        job_id = uuid4()
        item_id = uuid4()
        item = GenerationItem(
            generation_item_id=item_id,
            generation_job_id=job_id,
            position=0,
            status="PENDING",
            final_prompt=data.prompt,  # type: ignore[attr-defined]
            output_role="MAIN_IMAGE",
            output_format=data.output_format.value,  # type: ignore[attr-defined]
            size=data.size.value,  # type: ignore[attr-defined]
            output_ordinal=0,
            attempt_count=1,
        )
        item.input_assets = [
            GenerationItemAsset(
                generation_item_id=item_id,
                input_role="PRODUCT_SOURCE",
                position=0,
                asset_id=asset.asset_id,
                asset=asset,
            ),
        ]
        stamp(item)
        model = AiModel(
            model_id=data.model_id,  # type: ignore[attr-defined]
            display_name="GPT Image 2",
            model_code="gpt-image-2",
            provider_code="toapis",
            enabled=True,
            is_default=True,
            capabilities=["NORMAL_GENERATION", "STYLE_REPLICATION"],
            max_input_images=6,
            supported_sizes=["1:1", "3:4", "4:3", "16:9"],
            supported_resolutions=["1k", "2k", "4k"],
        )
        stamp(model)
        job = GenerationJob(
            generation_job_id=job_id,
            team_id=actor.team_id,
            created_by_user_id=actor.user_id,
            model_id=model.model_id,
            model=model,
            created_by_display_name=actor.user_display_name,
            work_mode=GenerationWorkMode.INSTANT.value,
            mode=GenerationMode.NORMAL_GENERATION.value,
            compress_output_under_1000kb=getattr(
                data,
                "compress_output_under_1000kb",
                False,
            ),
            status="PENDING",
            submission_key=data.submission_key,  # type: ignore[attr-defined]
            submission_fingerprint="d" * 64,
            items=[item],
        )
        stamp(job)
        self.job = job
        return job

    def list(
        self,
        **kwargs: object,
    ) -> tuple[
        list[tuple[GenerationJob, GenerationCounts, GenerationInputSummary]],
        int,
    ]:
        del kwargs
        assert self.job is not None
        return [
            (
                self.job,
                GenerationCounts(total_count=1, pending_count=1),
                GenerationInputSummary(count=1, primary_name="source.png"),
            ),
        ], 1

    def get(
        self,
        actor: ActorContext,
        generation_job_id: UUID,
    ) -> GenerationJob:
        del actor
        assert self.job is not None
        assert self.job.generation_job_id == generation_job_id
        return self.job

    def retry_failed_items(
        self,
        actor: ActorContext,
        generation_job_id: UUID,
        data: object,
    ) -> GenerationJob:
        del actor, data
        return self.get(ACTOR, generation_job_id)

    def archive_instant_item(
        self,
        actor: ActorContext,
        generation_job_id: UUID,
        generation_item_id: UUID,
        data: object,
    ) -> GenerationJob:
        job = self.get(actor, generation_job_id)
        item = next(
            item
            for item in job.items
            if item.generation_item_id == generation_item_id
        )
        item.archived_material_group_id = data.material_group_id  # type: ignore[attr-defined]
        item.archived_material_group_name_snapshot = "归档商品"
        item.archived_at = datetime.now(UTC)
        return job


def request(
    service: ApiAiWorkbenchService,
    method: str,
    path: str,
    *,
    actor: ActorContext | None = ACTOR,
    module_access: ApiModuleAccessService | None = None,
    generation_service: ApiGenerationService | None = None,
    **kwargs: object,
) -> Response:
    application = create_app()
    application.dependency_overrides[get_ai_workbench_service] = lambda: service
    if generation_service is not None:
        application.dependency_overrides[get_generation_service] = (
            lambda: generation_service
        )
    application.dependency_overrides[get_database_session] = lambda: FakeSession()
    if module_access is None:
        if actor is not None:
            application.dependency_overrides[get_ai_workbench_authorized_actor] = (
                lambda: actor
            )
    else:
        if actor is not None:
            application.dependency_overrides[get_actor_context] = lambda: actor
        application.dependency_overrides[get_module_access_service] = (
            lambda: module_access
        )

    async def send() -> Response:
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def test_ai_workbench_routes_are_registered_as_resource_apis() -> None:
    application = create_app()
    paths = application.openapi()["paths"]

    assert {
        "/api/v1/ai-workbench/template-groups",
        "/api/v1/ai-workbench/template-groups/{template_group_id}",
        "/api/v1/ai-workbench/template-groups/{template_group_id}/prompt-templates",
        "/api/v1/ai-workbench/template-groups/{template_group_id}/"
        "prompt-templates/{prompt_template_id}",
        "/api/v1/ai-workbench/template-groups/{template_group_id}/"
        "prompt-templates/{prompt_template_id}/duplicate",
        "/api/v1/ai-workbench/template-groups/{template_group_id}/prompt-templates/reorder",
        "/api/v1/ai-workbench/product-material-groups",
        "/api/v1/ai-workbench/product-material-groups/{material_group_id}",
        "/api/v1/ai-workbench/product-material-groups/{material_group_id}/assets",
        "/api/v1/ai-workbench/product-material-groups/{material_group_id}/assets/{asset_id}",
        "/api/v1/ai-workbench/product-material-groups/{material_group_id}/"
        "template-bindings/{mode}",
        "/api/v1/ai-workbench/generation-jobs",
        "/api/v1/ai-workbench/generation-jobs/{generation_job_id}",
        "/api/v1/ai-workbench/generation-jobs/{generation_job_id}/"
        "retry-failed-items",
        "/api/v1/ai-workbench/generation-jobs/{generation_job_id}/items/"
        "{generation_item_id}/archive",
    } <= set(paths)


def test_ai_workbench_api_create_list_pagination_and_ownership_input() -> None:
    service = ApiAiWorkbenchService()
    created = request(
        service,
        "POST",
        "/api/v1/ai-workbench/template-groups",
        json={"name": " 电商标准套图 ", "mode": "NORMAL_GENERATION"},
    )

    assert created.status_code == 201
    assert created.json()["name"] == "电商标准套图"
    assert created.json()["mode"] == GenerationMode.NORMAL_GENERATION.value
    listing = request(
        service,
        "GET",
        "/api/v1/ai-workbench/template-groups?page=1&page_size=20",
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["page"] == 1
    assert listing.json()["page_size"] == 20

    rejected = request(
        service,
        "POST",
        "/api/v1/ai-workbench/template-groups",
        json={
            "name": "伪造归属",
            "mode": "NORMAL_GENERATION",
            "team_id": str(uuid4()),
        },
    )
    assert rejected.status_code == 422
    assert rejected.json()["code"] == "VALIDATION_ERROR"


def test_generation_submit_api_is_async_pending_and_uses_safe_asset_projection() -> None:
    service = ApiAiWorkbenchService()
    generation_service = ApiGenerationService()
    asset_id = uuid4()
    model_id = uuid4()

    response = request(
        service,
        "POST",
        "/api/v1/ai-workbench/generation-jobs",
        generation_service=generation_service,
        json={
            "work_mode": "INSTANT",
            "submission_key": "api-submit-1",
            "model_id": str(model_id),
            "mode": "NORMAL_GENERATION",
            "product_asset_ids": [str(asset_id)],
            "prompt": "完整商品主图提示词",
            "output_format": "SINGLE",
            "size": "1:1",
            "count": 1,
            "compress_output_under_1000kb": True,
        },
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "PENDING"
    assert payload["model_id"] == str(model_id)
    assert payload["compress_output_under_1000kb"] is True
    assert payload["model_code"] == "gpt-image-2"
    assert payload["model_display_name"] == "GPT Image 2"
    assert payload["total_count"] == 1
    assert payload["pending_count"] == 1
    assert payload["items"][0]["status"] == "PENDING"
    assert payload["input_summary"] == {
        "count": 1,
        "primary_name": "source.png",
    }
    assert payload["items"][0]["input_assets"][0]["asset"]["asset_id"] == str(
        asset_id,
    )
    assert "storage_key" not in response.text
    assert "provider" not in response.text.casefold()

    listing = request(
        service,
        "GET",
        "/api/v1/ai-workbench/generation-jobs?page=1&page_size=20",
        generation_service=generation_service,
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["model_id"] == str(model_id)
    assert listing.json()["items"][0]["model_display_name"] == "GPT Image 2"
    assert listing.json()["items"][0]["input_summary"] == {
        "count": 1,
        "primary_name": "source.png",
    }
    job_id = payload["generation_job_id"]
    detail = request(
        service,
        "GET",
        f"/api/v1/ai-workbench/generation-jobs/{job_id}",
        generation_service=generation_service,
    )
    assert detail.status_code == 200
    assert detail.json()["generation_job_id"] == job_id
    retry = request(
        service,
        "POST",
        f"/api/v1/ai-workbench/generation-jobs/{job_id}/retry-failed-items",
        generation_service=generation_service,
        json={
            "items": [
                {
                    "item_id": payload["items"][0]["generation_item_id"],
                    "expected_attempt_count": 1,
                },
            ],
        },
    )
    assert retry.status_code == 202
    archive_group_id = uuid4()
    archived = request(
        service,
        "POST",
        f"/api/v1/ai-workbench/generation-jobs/{job_id}/items/"
        f"{payload['items'][0]['generation_item_id']}/archive",
        generation_service=generation_service,
        json={"material_group_id": str(archive_group_id)},
    )
    assert archived.status_code == 200
    assert archived.json()["items"][0]["archived_material_group_id"] == str(
        archive_group_id,
    )


def test_ai_workbench_human_api_requires_authentication_and_module_access() -> None:
    service = ApiAiWorkbenchService()
    unauthenticated = request(
        service,
        "GET",
        "/api/v1/ai-workbench/template-groups",
        actor=None,
    )
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["code"] == "HUMAN_AUTHENTICATION_REQUIRED"

    denied_service = ApiModuleAccessService(allowed=False)
    denied = request(
        service,
        "GET",
        "/api/v1/ai-workbench/template-groups",
        module_access=denied_service,
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "MODULE_ACCESS_DENIED"
    assert denied_service.checked == [ModuleCode.AI_WORKBENCH]

    allowed_service = ApiModuleAccessService(allowed=True)
    allowed = request(
        service,
        "GET",
        "/api/v1/ai-workbench/template-groups",
        module_access=allowed_service,
    )
    assert allowed.status_code == 200
    assert allowed_service.checked == [ModuleCode.AI_WORKBENCH]

    generation_denied_service = ApiModuleAccessService(allowed=False)
    generation_denied = request(
        service,
        "GET",
        "/api/v1/ai-workbench/generation-jobs",
        module_access=generation_denied_service,
    )
    assert generation_denied.status_code == 403
    assert generation_denied.json()["code"] == "MODULE_ACCESS_DENIED"
    assert generation_denied_service.checked == [ModuleCode.AI_WORKBENCH]


def test_product_material_detail_uses_safe_asset_projection() -> None:
    service = ApiAiWorkbenchService()
    group = service.create_product_material_group(
        ACTOR,
        ProductMaterialGroupCreate(name="手机支架"),
    )
    asset = Asset(
        asset_id=uuid4(),
        team_id=ACTOR.team_id,
        created_by_user_id=ACTOR.user_id,
        original_filename="source.png",
        storage_key="private/internal/source.png",
        media_type=AssetMediaType.IMAGE.value,
        source_type=AssetSourceType.UPLOAD.value,
        content_type="image/png",
        size_bytes=128,
        sha256="b" * 64,
    )
    stamp(asset)
    link = MaterialGroupAsset(
        material_group_id=group.material_group_id,
        asset_id=asset.asset_id,
        role="PRODUCT_SOURCE",
    )
    stamp(link)
    link.asset = asset
    group.asset_links.append(link)

    response = request(
        service,
        "GET",
        f"/api/v1/ai-workbench/product-material-groups/{group.material_group_id}",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["assets"][0]["asset"]["original_filename"] == "source.png"
    assert "storage_key" not in response.text
    assert "private/internal" not in response.text


def test_template_group_in_use_uses_stable_error_envelope() -> None:
    service = ApiAiWorkbenchService()
    group = service.create_template_group(
        ACTOR,
        TemplateGroupCreate(
            name="绑定中的模板组",
            mode=GenerationMode.NORMAL_GENERATION,
        ),
    )
    service.reject_template_delete = True

    response = request(
        service,
        "DELETE",
        f"/api/v1/ai-workbench/template-groups/{group.template_group_id}",
    )

    assert response.status_code == 409
    assert response.json()["code"] == "TEMPLATE_GROUP_IN_USE"
    assert response.json()["message"] == "模板组仍被商品素材组引用，无法删除"
    assert response.json()["request_id"]


def test_prompt_api_rejects_negative_prompt() -> None:
    service = ApiAiWorkbenchService()
    group = service.create_template_group(
        ACTOR,
        TemplateGroupCreate(name="提示词组", mode=GenerationMode.NORMAL_GENERATION),
    )

    response = request(
        service,
        "POST",
        f"/api/v1/ai-workbench/template-groups/{group.template_group_id}/prompt-templates",
        json={
            "name": "主图",
            "output_role": "MAIN_IMAGE",
            "output_format": "SINGLE",
            "size": "1:1",
            "count": 1,
            "variables": ["product_name"],
            "prompt": "{product_name}",
            "negative_prompt": "文字",
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
