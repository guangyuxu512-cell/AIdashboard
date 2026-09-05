from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from io import BytesIO
from uuid import UUID, uuid4

import pytest

from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.ai_workbench.enums import (
    GenerationItemStatus,
    GenerationJobStatus,
    GenerationMode,
    GenerationWorkMode,
    MaterialRole,
    OutputRole,
)
from app.modules.ai_workbench.exceptions import (
    GenerationItemStateConflictError,
    GenerationJobNotFoundError,
    GenerationPlanInvalidError,
    GenerationPlanTooLargeError,
    GenerationRetryConflictError,
    GenerationSubmissionConflictError,
    ProductMaterialGroupNotFoundError,
)
from app.modules.ai_workbench.generation_service import (
    GenerationService,
    derive_generation_job_status,
    generation_counts,
    generation_input_summary,
)
from app.modules.ai_workbench.limits import (
    MAX_GENERATION_ITEM_INPUT_ASSETS,
    MAX_GENERATION_ITEMS,
    MAX_GENERATION_SELECTION_IDS,
)
from app.modules.ai_workbench.models import (
    GenerationItem,
    GenerationJob,
    MaterialGroupAsset,
    MaterialGroupTemplateBinding,
    ProductMaterialGroup,
    PromptTemplate,
    TemplateGroup,
)
from app.modules.ai_workbench.repository import GenerationCounts, GenerationInputSummary
from app.modules.ai_workbench.schemas import (
    BatchGenerationSubmit,
    GenerationItemArchiveRequest,
    GenerationRetryRequest,
    InstantGenerationSubmit,
)
from app.modules.assets.contracts import AssetOwnership
from app.modules.assets.enums import AssetMediaType, AssetSourceType
from app.modules.assets.exceptions import AssetNotFoundError
from app.modules.assets.models import Asset
from tests.support import FakeSession


TEAM_A = uuid4()
TEAM_B = uuid4()
USER_A = uuid4()
USER_A2 = uuid4()
USER_B = uuid4()


def actor(
    *,
    team_id: UUID = TEAM_A,
    user_id: UUID = USER_A,
    scope: DataScope = DataScope.TEAM,
) -> ActorContext:
    return ActorContext(
        user_id=user_id,
        user_display_name=f"Generation {user_id}",
        team_id=team_id,
        membership_id=uuid4(),
        role_code="member",
        data_scope=scope,
    )


def visible(entity: object, current_actor: ActorContext) -> bool:
    if current_actor.data_scope is DataScope.ALL:
        return True
    if entity.team_id != current_actor.team_id:  # type: ignore[attr-defined]
        return False
    if current_actor.data_scope is DataScope.TEAM:
        return True
    return entity.created_by_user_id == current_actor.user_id  # type: ignore[attr-defined]


def stamp(entity: object) -> None:
    now = datetime.now(UTC)
    if hasattr(entity, "created_at"):
        entity.created_at = now  # type: ignore[attr-defined]
    if hasattr(entity, "updated_at"):
        entity.updated_at = now  # type: ignore[attr-defined]


class FakeGenerationRepository:
    def __init__(self, material_groups: dict[UUID, ProductMaterialGroup]) -> None:
        self.jobs: dict[UUID, GenerationJob] = {}
        self.material_groups = material_groups
        self.fail_add = False

    def get_by_submission(
        self,
        *,
        team_id: UUID,
        created_by_user_id: UUID,
        submission_key: str,
    ) -> GenerationJob | None:
        return next(
            (
                job
                for job in self.jobs.values()
                if job.team_id == team_id
                and job.created_by_user_id == created_by_user_id
                and job.submission_key == submission_key
            ),
            None,
        )

    def add_job(self, job: GenerationJob) -> None:
        if self.fail_add:
            raise RuntimeError("generation persistence failed")
        stamp(job)
        for item in job.items:
            item.job = job
            stamp(item)
        self.jobs[job.generation_job_id] = job

    def list_jobs(
        self,
        *,
        actor: ActorContext,
        offset: int,
        limit: int,
        work_mode: GenerationWorkMode | None,
        mode: GenerationMode | None,
        status: GenerationJobStatus | None,
    ) -> list[GenerationJob]:
        values = [job for job in self.jobs.values() if visible(job, actor)]
        if work_mode is not None:
            values = [job for job in values if job.work_mode == work_mode.value]
        if mode is not None:
            values = [job for job in values if job.mode == mode.value]
        if status is not None:
            values = [job for job in values if job.status == status.value]
        return list(reversed(values))[offset : offset + limit]

    def count_jobs(self, **kwargs: object) -> int:
        return len(self.list_jobs(offset=0, limit=10_000, **kwargs))  # type: ignore[arg-type]

    def counts_by_job_ids(
        self,
        job_ids: Sequence[UUID],
    ) -> dict[UUID, GenerationCounts]:
        return {
            job_id: generation_counts(self.jobs[job_id].items) for job_id in job_ids
        }

    def input_summaries_by_job_ids(
        self,
        job_ids: Sequence[UUID],
    ) -> dict[UUID, GenerationInputSummary]:
        return {
            job_id: generation_input_summary(self.jobs[job_id]) for job_id in job_ids
        }

    def get_job_for_actor(
        self,
        *,
        actor: ActorContext,
        generation_job_id: UUID,
    ) -> GenerationJob | None:
        job = self.jobs.get(generation_job_id)
        return job if job is not None and visible(job, actor) else None

    def get_job_for_write(
        self,
        *,
        actor: ActorContext,
        generation_job_id: UUID,
    ) -> GenerationJob | None:
        job = self.get_job_for_actor(actor=actor, generation_job_id=generation_job_id)
        return job if job is not None and job.team_id == actor.team_id else None

    def get_job_by_id(self, generation_job_id: UUID) -> GenerationJob | None:
        return self.jobs.get(generation_job_id)

    def lock_items_for_retry(
        self,
        *,
        generation_job_id: UUID,
        item_ids: Sequence[UUID],
    ) -> list[GenerationItem]:
        requested = set(item_ids)
        return [
            item
            for item in self.jobs[generation_job_id].items
            if item.generation_item_id in requested
        ]

    def get_item_for_execution(
        self,
        generation_item_id: UUID,
    ) -> GenerationItem | None:
        return next(
            (
                item
                for job in self.jobs.values()
                for item in job.items
                if item.generation_item_id == generation_item_id
            ),
            None,
        )

    def get_item_for_job_for_update(
        self,
        *,
        generation_job_id: UUID,
        generation_item_id: UUID,
    ) -> GenerationItem | None:
        return next(
            (
                item
                for item in self.jobs[generation_job_id].items
                if item.generation_item_id == generation_item_id
            ),
            None,
        )

    def material_groups_exist_for_team(
        self,
        *,
        team_id: UUID,
        material_group_ids: Sequence[UUID],
    ) -> set[UUID]:
        return {
            material_group_id
            for material_group_id in material_group_ids
            if (group := self.material_groups.get(material_group_id)) is not None
            and group.team_id == team_id
        }

    def get_material_group_for_output(
        self,
        *,
        team_id: UUID,
        material_group_id: UUID,
    ) -> ProductMaterialGroup | None:
        group = self.material_groups.get(material_group_id)
        return group if group is not None and group.team_id == team_id else None

    def has_active_jobs_for_material_group(self, material_group_id: UUID) -> bool:
        return any(
            item.source_product_material_group_id == material_group_id
            and job.status
            in {GenerationJobStatus.PENDING.value, GenerationJobStatus.RUNNING.value}
            for job in self.jobs.values()
            for item in job.items
        )

    def add_material_group_asset(
        self,
        group: ProductMaterialGroup,
        link: MaterialGroupAsset,
    ) -> None:
        stamp(link)
        group.asset_links.append(link)


class FakeTemplateRepository:
    def __init__(self) -> None:
        self.groups: dict[UUID, TemplateGroup] = {}

    def list_groups_for_generation(
        self,
        *,
        actor: ActorContext,
        team_id: UUID,
        template_group_ids: Sequence[UUID],
    ) -> list[TemplateGroup]:
        return [
            group
            for group_id in template_group_ids
            if (group := self.groups.get(group_id)) is not None
            and group.team_id == team_id
            and visible(group, actor)
        ]

    def get_prompt_source_for_generation(
        self,
        *,
        actor: ActorContext,
        team_id: UUID,
        prompt_template_id: UUID,
    ) -> PromptTemplate | None:
        for group in self.groups.values():
            if group.team_id != team_id or not visible(group, actor):
                continue
            for prompt in group.prompt_templates:
                if prompt.prompt_template_id == prompt_template_id:
                    prompt.template_group = group
                    return prompt
        return None


class FakeMaterialGroupRepository:
    def __init__(self) -> None:
        self.groups: dict[UUID, ProductMaterialGroup] = {}

    def list_groups_for_generation(
        self,
        *,
        actor: ActorContext,
        team_id: UUID,
        material_group_ids: Sequence[UUID] | None,
        limit: int,
    ) -> list[ProductMaterialGroup]:
        values = [
            group
            for group in self.groups.values()
            if group.team_id == team_id and visible(group, actor)
        ]
        if material_group_ids is None:
            return [group for group in values if group.enabled][:limit]
        selected = set(material_group_ids)
        return [
            group for group in values if group.material_group_id in selected
        ][:limit]

    def get_group_for_write(
        self,
        *,
        actor: ActorContext,
        material_group_id: UUID,
    ) -> ProductMaterialGroup | None:
        group = self.groups.get(material_group_id)
        if group is None or group.team_id != actor.team_id or not visible(group, actor):
            return None
        return group


class FakeAssetService:
    def __init__(self) -> None:
        self.assets: dict[UUID, Asset] = {}
        self.created_ownership: list[AssetOwnership] = []

    def add(
        self,
        *,
        team_id: UUID,
        created_by_user_id: UUID,
        filename: str = "input.png",
    ) -> Asset:
        asset = Asset(
            asset_id=uuid4(),
            team_id=team_id,
            created_by_user_id=created_by_user_id,
            original_filename=filename,
            storage_key=f"{uuid4()}.png",
            media_type=AssetMediaType.IMAGE.value,
            source_type=AssetSourceType.UPLOAD.value,
            content_type="image/png",
            size_bytes=20,
            sha256="a" * 64,
        )
        stamp(asset)
        self.assets[asset.asset_id] = asset
        return asset

    def list_accessible_by_ids_for_update(
        self,
        actor: ActorContext,
        asset_ids: Sequence[UUID],
    ) -> list[Asset]:
        return [
            asset
            for asset_id in asset_ids
            if (asset := self.assets.get(asset_id)) is not None
            and visible(asset, actor)
        ]

    @contextmanager
    def stage_for_transaction(
        self,
        *,
        original_filename: str | None,
        content_type: str | None,
        stream: BytesIO,
        media_type: AssetMediaType,
        source_type: AssetSourceType,
        ownership: AssetOwnership,
    ) -> Iterator[Asset]:
        del stream
        self.created_ownership.append(ownership)
        asset = Asset(
            asset_id=uuid4(),
            team_id=ownership.team_id,
            created_by_user_id=ownership.created_by_user_id,
            original_filename=original_filename or "generated.png",
            storage_key=f"{uuid4()}.png",
            media_type=media_type.value,
            source_type=source_type.value,
            content_type=content_type or "image/png",
            size_bytes=20,
            sha256="b" * 64,
        )
        stamp(asset)
        self.assets[asset.asset_id] = asset
        try:
            yield asset
        except Exception:
            del self.assets[asset.asset_id]
            raise


def make_service() -> tuple[
    GenerationService,
    FakeGenerationRepository,
    FakeTemplateRepository,
    FakeMaterialGroupRepository,
    FakeAssetService,
    FakeSession,
]:
    templates = FakeTemplateRepository()
    materials = FakeMaterialGroupRepository()
    assets = FakeAssetService()
    generations = FakeGenerationRepository(materials.groups)
    session = FakeSession()
    service = GenerationService(
        session,  # type: ignore[arg-type]
        generation_repository=generations,  # type: ignore[arg-type]
        template_repository=templates,  # type: ignore[arg-type]
        material_group_repository=materials,  # type: ignore[arg-type]
        asset_service=assets,  # type: ignore[arg-type]
    )
    return service, generations, templates, materials, assets, session


def instant_data(
    product_asset_id: UUID,
    *,
    key: str = "instant-key",
    prompt: str = "完整商品主图提示词",
    count: int = 2,
) -> InstantGenerationSubmit:
    return InstantGenerationSubmit(
        work_mode=GenerationWorkMode.INSTANT,
        submission_key=key,
        mode=GenerationMode.NORMAL_GENERATION,
        product_asset_ids=[product_asset_id],
        prompt=prompt,
        output_format="SINGLE",  # type: ignore[arg-type]
        size="1:1",  # type: ignore[arg-type]
        count=count,
    )


def add_template_group(
    repository: FakeTemplateRepository,
    *,
    current_actor: ActorContext,
    mode: GenerationMode,
) -> TemplateGroup:
    group = TemplateGroup(
        template_group_id=uuid4(),
        team_id=current_actor.team_id,
        created_by_user_id=current_actor.user_id,
        name="电商标准套图",
        mode=mode.value,
        enabled=True,
    )
    stamp(group)
    group.prompt_templates = []
    repository.groups[group.template_group_id] = group
    return group


def add_prompt(
    group: TemplateGroup,
    *,
    role: OutputRole,
    count: int,
) -> PromptTemplate:
    prompt = PromptTemplate(
        prompt_template_id=uuid4(),
        template_group_id=group.template_group_id,
        name="主图" if role is OutputRole.MAIN_IMAGE else "详情",
        enabled=True,
        output_role=role.value,
        output_format="SINGLE",
        size="1:1" if role is OutputRole.MAIN_IMAGE else "3:4",
        count=count,
        variables=[],
        prompt="批量模板完整提示词",
        sort_order=len(group.prompt_templates) + 1,
    )
    stamp(prompt)
    group.prompt_templates.append(prompt)
    return prompt


def add_material_group(
    repository: FakeMaterialGroupRepository,
    *,
    current_actor: ActorContext,
    mode: GenerationMode,
) -> ProductMaterialGroup:
    group = ProductMaterialGroup(
        material_group_id=uuid4(),
        team_id=current_actor.team_id,
        created_by_user_id=current_actor.user_id,
        name="手机支架",
        enabled=True,
        normal_generation_enabled=True,
        style_replication_enabled=mode is GenerationMode.STYLE_REPLICATION,
    )
    stamp(group)
    group.asset_links = []
    group.template_bindings = []
    repository.groups[group.material_group_id] = group
    return group


def attach(group: ProductMaterialGroup, asset: Asset, role: MaterialRole) -> None:
    link = MaterialGroupAsset(
        material_group_id=group.material_group_id,
        asset_id=asset.asset_id,
        role=role.value,
    )
    stamp(link)
    link.asset = asset
    group.asset_links.append(link)


def test_instant_submit_creates_pending_items_and_is_persistently_idempotent() -> None:
    service, generations, _, _, assets, session = make_service()
    current_actor = actor()
    product = assets.add(team_id=TEAM_A, created_by_user_id=USER_A)
    data = instant_data(product.asset_id)

    job = service.submit(current_actor, data)

    assert job.status == GenerationJobStatus.PENDING.value
    assert len(job.items) == 2
    assert [item.position for item in job.items] == [0, 1]
    assert [item.output_ordinal for item in job.items] == [0, 1]
    assert all(item.final_prompt == data.prompt for item in job.items)
    assert all(item.output_role == OutputRole.MAIN_IMAGE.value for item in job.items)
    assert all(item.output_asset_id is None for item in job.items)
    assert all(item.attempt_count == 1 for item in job.items)
    assert all(
        [link.asset_id for link in item.input_assets] == [product.asset_id]
        for item in job.items
    )
    assert not hasattr(job, "provider_id")
    assert not hasattr(job.items[0], "model_id")

    del assets.assets[product.asset_id]
    repeated = service.submit(current_actor, data)
    assert repeated is job
    assert len(generations.jobs) == 1
    assert session.commits == 1

    with pytest.raises(GenerationSubmissionConflictError):
        service.submit(
            current_actor,
            instant_data(product.asset_id, prompt="另一个提示词"),
        )


def test_submit_rejects_unreadable_or_cross_team_assets_even_for_all_scope() -> None:
    service, generations, _, _, assets, session = make_service()
    all_actor = actor(scope=DataScope.ALL)
    cross_team_asset = assets.add(team_id=TEAM_B, created_by_user_id=USER_B)

    with pytest.raises(AssetNotFoundError):
        service.submit(all_actor, instant_data(cross_team_asset.asset_id))

    assert generations.jobs == {}
    assert session.rollbacks == 1


@pytest.mark.parametrize(
    ("mode", "product_count", "reference_count"),
    [
        (GenerationMode.NORMAL_GENERATION, 17, 0),
        (GenerationMode.STYLE_REPLICATION, 15, 2),
    ],
)
def test_instant_submit_rejects_more_than_sixteen_item_inputs(
    mode: GenerationMode,
    product_count: int,
    reference_count: int,
) -> None:
    service, generations, _, _, assets, _ = make_service()
    current_actor = actor()
    product_ids = [
        assets.add(team_id=TEAM_A, created_by_user_id=USER_A).asset_id
        for _ in range(product_count)
    ]
    reference_ids = [
        assets.add(team_id=TEAM_A, created_by_user_id=USER_A).asset_id
        for _ in range(reference_count)
    ]
    assert len(product_ids) + len(reference_ids) > MAX_GENERATION_ITEM_INPUT_ASSETS

    with pytest.raises(GenerationPlanTooLargeError):
        service.submit(
            current_actor,
            InstantGenerationSubmit(
                work_mode=GenerationWorkMode.INSTANT,
                submission_key=f"too-many-inputs-{mode.value}",
                mode=mode,
                product_asset_ids=product_ids,
                reference_asset_ids=reference_ids,
                prompt="完整提示词",
                output_format="SINGLE",  # type: ignore[arg-type]
                size="1:1",  # type: ignore[arg-type]
                count=1,
            ),
        )

    assert generations.jobs == {}


def test_batch_submit_rejects_more_than_sixteen_inputs_per_item() -> None:
    service, generations, templates, materials, assets, _ = make_service()
    current_actor = actor()
    product = add_material_group(
        materials,
        current_actor=current_actor,
        mode=GenerationMode.STYLE_REPLICATION,
    )
    for _ in range(MAX_GENERATION_ITEM_INPUT_ASSETS):
        attach(
            product,
            assets.add(team_id=TEAM_A, created_by_user_id=USER_A),
            MaterialRole.PRODUCT_SOURCE,
        )
    attach(
        product,
        assets.add(team_id=TEAM_A, created_by_user_id=USER_A),
        MaterialRole.STYLE_REFERENCE,
    )
    template_group = add_template_group(
        templates,
        current_actor=current_actor,
        mode=GenerationMode.STYLE_REPLICATION,
    )
    add_prompt(template_group, role=OutputRole.MAIN_IMAGE, count=1)
    product.template_bindings.append(
        MaterialGroupTemplateBinding(
            material_group_id=product.material_group_id,
            template_group_id=template_group.template_group_id,
            generation_mode=GenerationMode.STYLE_REPLICATION.value,
            position=0,
        ),
    )

    with pytest.raises(GenerationPlanTooLargeError):
        service.submit(
            current_actor,
            BatchGenerationSubmit(
                work_mode=GenerationWorkMode.BATCH,
                submission_key="batch-too-many-item-inputs",
                mode=GenerationMode.STYLE_REPLICATION,
                product_scope="SELECTED",  # type: ignore[arg-type]
                selected_product_ids=[product.material_group_id],
                template_source="PRODUCT_CONFIGURED",  # type: ignore[arg-type]
                output_range="ALL",  # type: ignore[arg-type]
            ),
        )

    assert generations.jobs == {}


@pytest.mark.parametrize(
    ("mode", "product_count", "reference_count"),
    [
        (GenerationMode.NORMAL_GENERATION, 16, 0),
        (GenerationMode.STYLE_REPLICATION, 15, 1),
    ],
)
def test_instant_submit_accepts_sixteen_item_inputs(
    mode: GenerationMode,
    product_count: int,
    reference_count: int,
) -> None:
    service, _, _, _, assets, _ = make_service()
    current_actor = actor()
    product_ids = [
        assets.add(team_id=TEAM_A, created_by_user_id=USER_A).asset_id
        for _ in range(product_count)
    ]
    reference_ids = [
        assets.add(team_id=TEAM_A, created_by_user_id=USER_A).asset_id
        for _ in range(reference_count)
    ]

    job = service.submit(
        current_actor,
        InstantGenerationSubmit(
            work_mode=GenerationWorkMode.INSTANT,
            submission_key=f"sixteen-inputs-{mode.value}",
            mode=mode,
            product_asset_ids=product_ids,
            reference_asset_ids=reference_ids,
            prompt="完整提示词",
            output_format="SINGLE",  # type: ignore[arg-type]
            size="1:1",  # type: ignore[arg-type]
            count=1,
        ),
    )

    assert len(job.items[0].input_assets) == MAX_GENERATION_ITEM_INPUT_ASSETS


def test_instant_template_source_does_not_change_literal_prompt_or_main_role() -> None:
    service, _, templates, _, assets, _ = make_service()
    current_actor = actor()
    product = assets.add(team_id=TEAM_A, created_by_user_id=USER_A)
    template_group = add_template_group(
        templates,
        current_actor=current_actor,
        mode=GenerationMode.NORMAL_GENERATION,
    )
    template = add_prompt(
        template_group,
        role=OutputRole.DETAIL_IMAGE,
        count=1,
    )
    data = instant_data(product.asset_id, prompt="用户最终完整提示词", count=1)
    data.prompt_template_id = template.prompt_template_id

    job = service.submit(current_actor, data)

    item = job.items[0]
    assert item.final_prompt == "用户最终完整提示词"
    assert item.final_prompt != template.prompt
    assert item.output_role == OutputRole.MAIN_IMAGE.value
    assert item.source_prompt_template_id == template.prompt_template_id
    assert item.prompt_template_name_snapshot == template.name


def test_batch_plan_uses_frozen_templates_roles_and_ordered_asset_relations() -> None:
    service, _, templates, materials, assets, _ = make_service()
    current_actor = actor()
    product = add_material_group(
        materials,
        current_actor=current_actor,
        mode=GenerationMode.STYLE_REPLICATION,
    )
    product_source = assets.add(team_id=TEAM_A, created_by_user_id=USER_A)
    reference_one = assets.add(team_id=TEAM_A, created_by_user_id=USER_A)
    reference_two = assets.add(team_id=TEAM_A, created_by_user_id=USER_A)
    attach(product, product_source, MaterialRole.PRODUCT_SOURCE)
    attach(product, reference_one, MaterialRole.STYLE_REFERENCE)
    attach(product, reference_two, MaterialRole.STYLE_REFERENCE)

    template_group = add_template_group(
        templates,
        current_actor=current_actor,
        mode=GenerationMode.STYLE_REPLICATION,
    )
    main = add_prompt(template_group, role=OutputRole.MAIN_IMAGE, count=2)
    add_prompt(template_group, role=OutputRole.DETAIL_IMAGE, count=1)
    product.template_bindings.append(
        MaterialGroupTemplateBinding(
            material_group_id=product.material_group_id,
            template_group_id=template_group.template_group_id,
            generation_mode=GenerationMode.STYLE_REPLICATION.value,
            position=0,
        ),
    )

    job = service.submit(
        current_actor,
        BatchGenerationSubmit(
            work_mode=GenerationWorkMode.BATCH,
            submission_key="batch-key",
            mode=GenerationMode.STYLE_REPLICATION,
            product_scope="SELECTED",  # type: ignore[arg-type]
            selected_product_ids=[product.material_group_id],
            template_source="PRODUCT_CONFIGURED",  # type: ignore[arg-type]
            output_range="MAIN_IMAGE",  # type: ignore[arg-type]
        ),
    )

    assert len(job.items) == 4
    assert all(item.final_prompt == main.prompt for item in job.items)
    assert all(item.output_role == OutputRole.MAIN_IMAGE.value for item in job.items)
    assert all(item.product_name_snapshot == product.name for item in job.items)
    assert all(item.prompt_template_name_snapshot == main.name for item in job.items)
    assert all(item.source_product_position == 0 for item in job.items)
    assert all(item.source_template_group_position == 0 for item in job.items)
    assert all(item.source_prompt_template_position == 0 for item in job.items)
    assert [item.output_ordinal for item in job.items] == [0, 1, 0, 1]
    assert {
        item.input_assets[1].asset_id for item in job.items
    } == {reference_one.asset_id, reference_two.asset_id}
    assert {item.input_assets[1].position for item in job.items} == {0, 1}
    assert all(
        [link.input_role for link in item.input_assets]
        == [MaterialRole.PRODUCT_SOURCE.value, MaterialRole.STYLE_REFERENCE.value]
        for item in job.items
    )


def test_batch_submit_requires_at_least_one_executable_item() -> None:
    service, generations, _, materials, _, session = make_service()
    current_actor = actor()
    add_material_group(
        materials,
        current_actor=current_actor,
        mode=GenerationMode.NORMAL_GENERATION,
    )

    with pytest.raises(GenerationPlanInvalidError):
        service.submit(
            current_actor,
            BatchGenerationSubmit(
                work_mode=GenerationWorkMode.BATCH,
                submission_key="empty-plan",
                mode=GenerationMode.NORMAL_GENERATION,
                product_scope="ALL_ENABLED",  # type: ignore[arg-type]
                template_source="PRODUCT_CONFIGURED",  # type: ignore[arg-type]
            ),
        )

    assert generations.jobs == {}
    assert session.rollbacks == 1


def test_batch_plan_limits_all_enabled_products_and_expanded_items() -> None:
    service, generations, templates, materials, assets, _ = make_service()
    current_actor = actor()
    for _ in range(MAX_GENERATION_SELECTION_IDS + 1):
        add_material_group(
            materials,
            current_actor=current_actor,
            mode=GenerationMode.NORMAL_GENERATION,
        )
    with pytest.raises(GenerationPlanTooLargeError):
        service.submit(
            current_actor,
            BatchGenerationSubmit(
                work_mode=GenerationWorkMode.BATCH,
                submission_key="too-many-products",
                mode=GenerationMode.NORMAL_GENERATION,
                product_scope="ALL_ENABLED",  # type: ignore[arg-type]
                template_source="PRODUCT_CONFIGURED",  # type: ignore[arg-type]
            ),
        )
    assert generations.jobs == {}

    materials.groups.clear()
    product = add_material_group(
        materials,
        current_actor=current_actor,
        mode=GenerationMode.NORMAL_GENERATION,
    )
    source = assets.add(team_id=TEAM_A, created_by_user_id=USER_A)
    attach(product, source, MaterialRole.PRODUCT_SOURCE)
    template_group = add_template_group(
        templates,
        current_actor=current_actor,
        mode=GenerationMode.NORMAL_GENERATION,
    )
    for _ in range((MAX_GENERATION_ITEMS // 8) + 1):
        add_prompt(template_group, role=OutputRole.MAIN_IMAGE, count=8)
    product.template_bindings.append(
        MaterialGroupTemplateBinding(
            material_group_id=product.material_group_id,
            template_group_id=template_group.template_group_id,
            generation_mode=GenerationMode.NORMAL_GENERATION.value,
            position=0,
        ),
    )
    with pytest.raises(GenerationPlanTooLargeError):
        service.submit(
            current_actor,
            BatchGenerationSubmit(
                work_mode=GenerationWorkMode.BATCH,
                submission_key="too-many-items",
                mode=GenerationMode.NORMAL_GENERATION,
                product_scope="SELECTED",  # type: ignore[arg-type]
                selected_product_ids=[product.material_group_id],
                template_source="PRODUCT_CONFIGURED",  # type: ignore[arg-type]
            ),
        )
    assert generations.jobs == {}


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        (["PENDING", "PENDING"], GenerationJobStatus.PENDING),
        (["RUNNING", "PENDING"], GenerationJobStatus.RUNNING),
        (["SUCCESS", "PENDING"], GenerationJobStatus.RUNNING),
        (["SUCCESS", "SUCCESS"], GenerationJobStatus.SUCCESS),
        (["FAILED", "FAILED"], GenerationJobStatus.FAILED),
        (["SUCCESS", "FAILED"], GenerationJobStatus.PARTIAL_FAILED),
    ],
)
def test_job_status_is_derived_only_from_item_statuses(
    statuses: list[str],
    expected: GenerationJobStatus,
) -> None:
    items = [GenerationItem(status=status) for status in statuses]
    assert derive_generation_job_status(items) is expected


def test_item_completion_uses_job_ownership_and_retry_is_compare_and_set() -> None:
    service, _, _, materials, assets, _ = make_service()
    current_actor = actor()
    product = assets.add(team_id=TEAM_A, created_by_user_id=USER_A)
    job = service.submit(current_actor, instant_data(product.asset_id, count=2))
    first, second = job.items

    job = service.mark_item_running(first.generation_item_id)
    assert job.status == GenerationJobStatus.RUNNING.value
    job = service.complete_item(
        first.generation_item_id,
        original_filename="generated.png",
        content_type="image/png",
        stream=BytesIO(b"\x89PNG\r\n\x1a\nresult"),
    )
    first = job.items[0]
    assert first.status == GenerationItemStatus.SUCCESS.value
    assert first.output_asset is not None
    assert first.output_asset.source_type == AssetSourceType.AI_GENERATED.value
    assert assets.created_ownership[-1] == AssetOwnership(
        team_id=job.team_id,
        created_by_user_id=job.created_by_user_id,
    )
    output_asset_id = first.output_asset.asset_id
    creation_count = len(assets.created_ownership)
    repeated_completion = service.complete_item(
        first.generation_item_id,
        original_filename="ignored.png",
        content_type="image/png",
        stream=BytesIO(b"ignored"),
    )
    assert repeated_completion.items[0].output_asset_id == output_asset_id
    assert len(assets.created_ownership) == creation_count

    archive_group = add_material_group(
        materials,
        current_actor=current_actor,
        mode=GenerationMode.NORMAL_GENERATION,
    )
    archived = service.archive_instant_item(
        current_actor,
        job.generation_job_id,
        first.generation_item_id,
        GenerationItemArchiveRequest(
            material_group_id=archive_group.material_group_id,
        ),
    )
    assert archived.items[0].archived_material_group_id == archive_group.material_group_id
    assert archived.items[0].archived_material_group_name_snapshot == archive_group.name
    assert archived.items[0].archived_at is not None
    assert len(archive_group.asset_links) == 1
    assert archive_group.asset_links[0].asset_id == output_asset_id
    assert archive_group.asset_links[0].role == MaterialRole.AI_OUTPUT.value
    service.archive_instant_item(
        current_actor,
        job.generation_job_id,
        first.generation_item_id,
        GenerationItemArchiveRequest(
            material_group_id=archive_group.material_group_id,
        ),
    )
    assert len(archive_group.asset_links) == 1
    other_group = add_material_group(
        materials,
        current_actor=current_actor,
        mode=GenerationMode.NORMAL_GENERATION,
    )
    with pytest.raises(GenerationItemStateConflictError):
        service.archive_instant_item(
            current_actor,
            job.generation_job_id,
            first.generation_item_id,
            GenerationItemArchiveRequest(
                material_group_id=other_group.material_group_id,
            ),
        )
    assert other_group.asset_links == []

    job = service.fail_item(
        second.generation_item_id,
        failure_code="PROVIDER_REJECTED",
        failure_message="生成失败",
    )
    assert job.status == GenerationJobStatus.PARTIAL_FAILED.value
    retry = GenerationRetryRequest.model_validate(
        {
            "items": [
                {
                    "item_id": str(second.generation_item_id),
                    "expected_attempt_count": 1,
                },
            ],
        },
    )
    job = service.retry_failed_items(current_actor, job.generation_job_id, retry)
    second = job.items[1]
    assert second.status == GenerationItemStatus.PENDING.value
    assert second.attempt_count == 2
    assert second.last_failure_code == "PROVIDER_REJECTED"
    assert second.last_failure_message == "生成失败"
    assert job.status == GenerationJobStatus.RUNNING.value

    repeated = service.retry_failed_items(current_actor, job.generation_job_id, retry)
    assert repeated.items[1].attempt_count == 2
    with pytest.raises(GenerationRetryConflictError):
        service.retry_failed_items(
            current_actor,
            job.generation_job_id,
            GenerationRetryRequest.model_validate(
                {
                    "items": [
                        {
                            "item_id": str(second.generation_item_id),
                            "expected_attempt_count": 2,
                        },
                    ],
                },
            ),
        )


def test_batch_retry_rejects_deleted_source_group_without_mutation() -> None:
    service, _, templates, materials, assets, _ = make_service()
    current_actor = actor()
    product = add_material_group(
        materials,
        current_actor=current_actor,
        mode=GenerationMode.NORMAL_GENERATION,
    )
    source = assets.add(team_id=TEAM_A, created_by_user_id=USER_A)
    attach(product, source, MaterialRole.PRODUCT_SOURCE)
    template_group = add_template_group(
        templates,
        current_actor=current_actor,
        mode=GenerationMode.NORMAL_GENERATION,
    )
    add_prompt(template_group, role=OutputRole.MAIN_IMAGE, count=1)
    product.template_bindings.append(
        MaterialGroupTemplateBinding(
            material_group_id=product.material_group_id,
            template_group_id=template_group.template_group_id,
            generation_mode=GenerationMode.NORMAL_GENERATION.value,
            position=0,
        ),
    )
    job = service.submit(
        current_actor,
        BatchGenerationSubmit(
            work_mode=GenerationWorkMode.BATCH,
            submission_key="deleted-source",
            mode=GenerationMode.NORMAL_GENERATION,
            product_scope="SELECTED",  # type: ignore[arg-type]
            selected_product_ids=[product.material_group_id],
            template_source="PRODUCT_CONFIGURED",  # type: ignore[arg-type]
        ),
    )
    item = job.items[0]
    service.fail_item(
        item.generation_item_id,
        failure_code="FAILED",
        failure_message="待重试",
    )
    del materials.groups[product.material_group_id]

    with pytest.raises(ProductMaterialGroupNotFoundError):
        service.retry_failed_items(
            current_actor,
            job.generation_job_id,
            GenerationRetryRequest.model_validate(
                {
                    "items": [
                        {
                            "item_id": str(item.generation_item_id),
                            "expected_attempt_count": 1,
                        },
                    ],
                },
            ),
        )
    assert item.status == GenerationItemStatus.FAILED.value
    assert item.attempt_count == 1


def test_stale_retry_does_not_rewrite_terminal_job_history() -> None:
    service, _, _, _, assets, session = make_service()
    current_actor = actor()
    source = assets.add(team_id=TEAM_A, created_by_user_id=USER_A)
    job = service.submit(
        current_actor,
        instant_data(source.asset_id, key="stale-retry", count=1),
    )
    item = job.items[0]
    service.fail_item(
        item.generation_item_id,
        failure_code="FIRST_FAILURE",
        failure_message="第一次失败",
    )
    first_request = GenerationRetryRequest.model_validate(
        {
            "items": [
                {
                    "item_id": str(item.generation_item_id),
                    "expected_attempt_count": 1,
                },
            ],
        },
    )
    service.retry_failed_items(current_actor, job.generation_job_id, first_request)
    job = service.fail_item(
        item.generation_item_id,
        failure_code="SECOND_FAILURE",
        failure_message="第二次失败",
    )
    finished_at = job.finished_at
    commits = session.commits

    repeated = service.retry_failed_items(
        current_actor,
        job.generation_job_id,
        first_request,
    )

    assert repeated.finished_at == finished_at
    assert repeated.items[0].attempt_count == 2
    assert repeated.items[0].status == GenerationItemStatus.FAILED.value
    assert session.commits == commits


def test_generation_records_apply_self_team_all_scope_and_write_stays_in_team() -> None:
    service, _, _, _, assets, _ = make_service()
    asset_a = assets.add(team_id=TEAM_A, created_by_user_id=USER_A)
    asset_a2 = assets.add(team_id=TEAM_A, created_by_user_id=USER_A2)
    asset_b = assets.add(team_id=TEAM_B, created_by_user_id=USER_B)
    job_a = service.submit(actor(scope=DataScope.SELF), instant_data(asset_a.asset_id))
    service.submit(
        actor(user_id=USER_A2, scope=DataScope.SELF),
        instant_data(asset_a2.asset_id, key="a2"),
    )
    job_b = service.submit(
        actor(team_id=TEAM_B, user_id=USER_B, scope=DataScope.TEAM),
        instant_data(asset_b.asset_id, key="b"),
    )

    self_jobs, self_total = service.list(
        actor=actor(scope=DataScope.SELF),
        page=1,
        page_size=20,
        work_mode=None,
        mode=None,
        status=None,
    )
    assert self_total == 1
    assert self_jobs[0][0] is job_a
    team_jobs, team_total = service.list(
        actor=actor(scope=DataScope.TEAM),
        page=1,
        page_size=20,
        work_mode=None,
        mode=None,
        status=None,
    )
    assert team_total == 2
    assert len(team_jobs) == 2
    all_jobs, all_total = service.list(
        actor=actor(scope=DataScope.ALL),
        page=1,
        page_size=20,
        work_mode=None,
        mode=None,
        status=None,
    )
    assert all_total == 3
    assert len(all_jobs) == 3
    with pytest.raises(GenerationJobNotFoundError):
        service.retry_failed_items(
            actor(scope=DataScope.ALL),
            job_b.generation_job_id,
            GenerationRetryRequest.model_validate(
                {
                    "items": [
                        {
                            "item_id": str(job_b.items[0].generation_item_id),
                            "expected_attempt_count": 1,
                        },
                    ],
                },
            ),
        )


def test_submit_persistence_failure_rolls_back() -> None:
    service, generations, _, _, assets, session = make_service()
    source = assets.add(team_id=TEAM_A, created_by_user_id=USER_A)
    generations.fail_add = True

    with pytest.raises(RuntimeError, match="generation persistence failed"):
        service.submit(actor(), instant_data(source.asset_id))

    assert generations.jobs == {}
    assert session.rollbacks == 1
