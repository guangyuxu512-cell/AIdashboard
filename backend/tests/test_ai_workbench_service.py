from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.ai_workbench.enums import (
    GenerationMode,
    GenerationSize,
    MaterialRole,
    OutputFormat,
    OutputRole,
)
from app.modules.ai_workbench.exceptions import (
    ProductMaterialGroupNotFoundError,
    TemplateBindingInvalidError,
    TemplateGroupInUseError,
    TemplateSequenceInvalidError,
)
from app.modules.ai_workbench.models import (
    MaterialGroupAsset,
    MaterialGroupTemplateBinding,
    ProductMaterialGroup,
    PromptTemplate,
    TemplateGroup,
)
from app.modules.ai_workbench.schemas import (
    MaterialGroupAssetAttach,
    ProductMaterialGroupCreate,
    ProductMaterialGroupUpdate,
    PromptTemplateCreate,
    PromptTemplateReorder,
    PromptTemplateUpdate,
    TemplateBindingReplace,
    TemplateGroupCreate,
    TemplateGroupUpdate,
)
from app.modules.ai_workbench.service import AiWorkbenchService
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
    user_id: UUID = USER_A,
    team_id: UUID = TEAM_A,
    scope: DataScope = DataScope.TEAM,
) -> ActorContext:
    return ActorContext(
        user_id=user_id,
        user_display_name="AI Workbench 测试用户",
        team_id=team_id,
        membership_id=uuid4(),
        role_code="member",
        data_scope=scope,
    )


def visible(owner: object, current_actor: ActorContext) -> bool:
    if current_actor.data_scope is DataScope.ALL:
        return True
    if owner.team_id != current_actor.team_id:  # type: ignore[attr-defined]
        return False
    if current_actor.data_scope is DataScope.TEAM:
        return True
    return owner.created_by_user_id == current_actor.user_id  # type: ignore[attr-defined]


def stamp(entity: object) -> None:
    now = datetime.now(UTC)
    if hasattr(entity, "created_at"):
        entity.created_at = now  # type: ignore[attr-defined]
    if hasattr(entity, "updated_at"):
        entity.updated_at = now  # type: ignore[attr-defined]


class FakeTemplateRepository:
    def __init__(self) -> None:
        self.groups: dict[UUID, TemplateGroup] = {}
        self.bound_group_ids: set[UUID] = set()

    def list_groups(
        self,
        *,
        actor: ActorContext,
        offset: int,
        limit: int,
        search: str | None,
        mode: GenerationMode | None,
        enabled: bool | None,
    ) -> list[TemplateGroup]:
        values = [group for group in self.groups.values() if visible(group, actor)]
        if search:
            values = [group for group in values if search.casefold() in group.name.casefold()]
        if mode is not None:
            values = [group for group in values if group.mode == mode.value]
        if enabled is not None:
            values = [group for group in values if group.enabled is enabled]
        return values[offset : offset + limit]

    def count_groups(self, **kwargs: object) -> int:
        return len(self.list_groups(offset=0, limit=10_000, **kwargs))  # type: ignore[arg-type]

    def get_group_for_actor(
        self,
        *,
        actor: ActorContext,
        template_group_id: UUID,
    ) -> TemplateGroup | None:
        group = self.groups.get(template_group_id)
        if group is not None:
            group.prompt_templates.sort(
                key=lambda prompt: (
                    prompt.sort_order,
                    str(prompt.prompt_template_id),
                ),
            )
        return group if group is not None and visible(group, actor) else None

    def get_group_for_write(
        self,
        *,
        actor: ActorContext,
        template_group_id: UUID,
    ) -> TemplateGroup | None:
        group = self.get_group_for_actor(
            actor=actor,
            template_group_id=template_group_id,
        )
        return group if group is not None and group.team_id == actor.team_id else None

    def list_groups_for_binding(
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

    def list_prompts_for_update(self, template_group_id: UUID) -> list[PromptTemplate]:
        return sorted(
            list(self.groups[template_group_id].prompt_templates),
            key=lambda prompt: (prompt.sort_order, str(prompt.prompt_template_id)),
        )

    def group_has_bindings(self, template_group_id: UUID) -> bool:
        return template_group_id in self.bound_group_ids

    def add_group(self, group: TemplateGroup) -> None:
        stamp(group)
        self.groups[group.template_group_id] = group

    def delete_group(self, group: TemplateGroup) -> None:
        del self.groups[group.template_group_id]

    def add_prompt(self, prompt: PromptTemplate) -> None:
        stamp(prompt)
        self.groups[prompt.template_group_id].prompt_templates.append(prompt)

    def delete_prompt(self, prompt: PromptTemplate) -> None:
        self.groups[prompt.template_group_id].prompt_templates.remove(prompt)


class FakeProductMaterialGroupRepository:
    def __init__(self) -> None:
        self.groups: dict[UUID, ProductMaterialGroup] = {}
        self.fail_binding_add = False

    def list_groups(
        self,
        *,
        actor: ActorContext,
        offset: int,
        limit: int,
        search: str | None,
        enabled: bool | None,
    ) -> list[ProductMaterialGroup]:
        values = [group for group in self.groups.values() if visible(group, actor)]
        if search:
            values = [group for group in values if search.casefold() in group.name.casefold()]
        if enabled is not None:
            values = [group for group in values if group.enabled is enabled]
        return values[offset : offset + limit]

    def count_groups(self, **kwargs: object) -> int:
        return len(self.list_groups(offset=0, limit=10_000, **kwargs))  # type: ignore[arg-type]

    def get_group_for_actor(
        self,
        *,
        actor: ActorContext,
        material_group_id: UUID,
    ) -> ProductMaterialGroup | None:
        group = self.groups.get(material_group_id)
        return group if group is not None and visible(group, actor) else None

    def get_group_for_write(
        self,
        *,
        actor: ActorContext,
        material_group_id: UUID,
    ) -> ProductMaterialGroup | None:
        group = self.get_group_for_actor(actor=actor, material_group_id=material_group_id)
        return group if group is not None and group.team_id == actor.team_id else None

    def add_group(self, group: ProductMaterialGroup) -> None:
        stamp(group)
        self.groups[group.material_group_id] = group

    def delete_group(self, group: ProductMaterialGroup) -> None:
        group.asset_links.clear()
        group.template_bindings.clear()
        del self.groups[group.material_group_id]

    def add_asset_link(self, link: MaterialGroupAsset) -> None:
        stamp(link)
        self.groups[link.material_group_id].asset_links.append(link)

    def delete_asset_link(self, link: MaterialGroupAsset) -> None:
        self.groups[link.material_group_id].asset_links.remove(link)

    def delete_bindings(self, material_group_id: UUID, mode: GenerationMode) -> None:
        group = self.groups[material_group_id]
        group.template_bindings[:] = [
            binding
            for binding in group.template_bindings
            if binding.generation_mode != mode.value
        ]

    def add_bindings(self, bindings: Sequence[MaterialGroupTemplateBinding]) -> None:
        if self.fail_binding_add:
            raise RuntimeError("binding persistence failed")
        for binding in bindings:
            stamp(binding)
            self.groups[binding.material_group_id].template_bindings.append(binding)


class FakeAssetService:
    def __init__(self) -> None:
        self.assets: dict[UUID, Asset] = {}

    def add(self, *, team_id: UUID, created_by_user_id: UUID) -> Asset:
        asset = Asset(
            asset_id=uuid4(),
            team_id=team_id,
            created_by_user_id=created_by_user_id,
            original_filename="product.png",
            storage_key=f"{uuid4()}.png",
            media_type=AssetMediaType.IMAGE.value,
            source_type=AssetSourceType.UPLOAD.value,
            content_type="image/png",
            size_bytes=12,
            sha256="a" * 64,
        )
        stamp(asset)
        self.assets[asset.asset_id] = asset
        return asset

    def list_accessible_by_ids(
        self,
        actor: ActorContext,
        asset_ids: Sequence[UUID],
    ) -> list[Asset]:
        return [
            asset
            for asset_id in asset_ids
            if (asset := self.assets.get(asset_id)) is not None and visible(asset, actor)
        ]


def make_service() -> tuple[
    AiWorkbenchService,
    FakeTemplateRepository,
    FakeProductMaterialGroupRepository,
    FakeAssetService,
    FakeSession,
]:
    templates = FakeTemplateRepository()
    materials = FakeProductMaterialGroupRepository()
    assets = FakeAssetService()
    session = FakeSession()
    service = AiWorkbenchService(
        session,  # type: ignore[arg-type]
        template_repository=templates,  # type: ignore[arg-type]
        material_group_repository=materials,  # type: ignore[arg-type]
        asset_service=assets,  # type: ignore[arg-type]
    )
    return service, templates, materials, assets, session


def create_template_group(
    service: AiWorkbenchService,
    current_actor: ActorContext,
    *,
    name: str = "电商标准套图",
    mode: GenerationMode = GenerationMode.NORMAL_GENERATION,
) -> TemplateGroup:
    return service.create_template_group(
        current_actor,
        TemplateGroupCreate(name=name, mode=mode),
    )


def create_prompt(
    service: AiWorkbenchService,
    current_actor: ActorContext,
    template_group_id: UUID,
    *,
    name: str,
    role: OutputRole,
) -> TemplateGroup:
    return service.create_prompt_template(
        current_actor,
        template_group_id,
        PromptTemplateCreate(
            name=name,
            output_role=role,
            output_format=OutputFormat.SINGLE,
            size=(
                GenerationSize.SQUARE
                if role is OutputRole.MAIN_IMAGE
                else GenerationSize.PORTRAIT
            ),
            count=1,
            variables=["product_name"],
            prompt="{product_name}",
        ),
    )


def create_material_group(
    service: AiWorkbenchService,
    current_actor: ActorContext,
) -> ProductMaterialGroup:
    return service.create_product_material_group(
        current_actor,
        ProductMaterialGroupCreate(name="手机支架"),
    )


def test_template_group_crud_scope_and_disable_preserve_children() -> None:
    service, templates, _, _, _ = make_service()
    owner = actor(scope=DataScope.SELF)
    group = create_template_group(service, owner)
    create_prompt(service, owner, group.template_group_id, name="主图", role=OutputRole.MAIN_IMAGE)

    updated = service.update_template_group(
        owner,
        group.template_group_id,
        TemplateGroupUpdate(name="新名称", enabled=False),
    )

    assert updated.team_id == owner.team_id
    assert updated.created_by_user_id == owner.user_id
    assert updated.name == "新名称"
    assert updated.enabled is False
    assert len(updated.prompt_templates) == 1
    outsider = actor(user_id=USER_A2, scope=DataScope.SELF)
    assert service.list_template_groups(
        actor=outsider,
        page=1,
        page_size=20,
        search=None,
        mode=None,
        enabled=None,
    ) == ([], 0)
    assert group.template_group_id in templates.groups


def test_prompt_sequence_duplicate_update_reorder_and_delete() -> None:
    service, _, _, _, _ = make_service()
    current_actor = actor()
    group = create_template_group(service, current_actor)
    create_prompt(
        service,
        current_actor,
        group.template_group_id,
        name="详情一",
        role=OutputRole.DETAIL_IMAGE,
    )
    create_prompt(
        service,
        current_actor,
        group.template_group_id,
        name="主图一",
        role=OutputRole.MAIN_IMAGE,
    )
    group = create_prompt(
        service,
        current_actor,
        group.template_group_id,
        name="主图二",
        role=OutputRole.MAIN_IMAGE,
    )
    assert [(item.output_role, item.sort_order) for item in group.prompt_templates] == [
        (OutputRole.MAIN_IMAGE.value, 1),
        (OutputRole.MAIN_IMAGE.value, 2),
        (OutputRole.DETAIL_IMAGE.value, 3),
    ]

    source = group.prompt_templates[0]
    group = service.update_prompt_template(
        current_actor,
        group.template_group_id,
        source.prompt_template_id,
        PromptTemplateUpdate(size=GenerationSize.WIDESCREEN, prompt="新版提示词"),
    )
    source = next(
        item
        for item in group.prompt_templates
        if item.prompt_template_id == source.prompt_template_id
    )
    assert source.output_role == OutputRole.MAIN_IMAGE.value
    assert source.size == GenerationSize.WIDESCREEN.value

    group = service.duplicate_prompt_template(
        current_actor,
        group.template_group_id,
        source.prompt_template_id,
    )
    copy = group.prompt_templates[1]
    assert copy.name == "主图一 副本"
    assert copy.output_role == source.output_role
    assert copy.size == source.size
    assert copy.variables == source.variables
    main_ids = [
        item.prompt_template_id
        for item in group.prompt_templates
        if item.output_role == OutputRole.MAIN_IMAGE.value
    ]
    group = service.reorder_prompt_templates(
        current_actor,
        group.template_group_id,
        PromptTemplateReorder(
            output_role=OutputRole.MAIN_IMAGE,
            prompt_template_ids=list(reversed(main_ids)),
        ),
    )
    assert [item.prompt_template_id for item in group.prompt_templates[:3]] == list(
        reversed(main_ids),
    )
    assert [item.sort_order for item in group.prompt_templates] == [1, 2, 3, 4]

    with pytest.raises(TemplateSequenceInvalidError):
        service.reorder_prompt_templates(
            current_actor,
            group.template_group_id,
            PromptTemplateReorder(
                output_role=OutputRole.MAIN_IMAGE,
                prompt_template_ids=main_ids[:1],
            ),
        )
    service.delete_prompt_template(
        current_actor,
        group.template_group_id,
        copy.prompt_template_id,
    )
    remaining = service.get_template_group(current_actor, group.template_group_id)
    assert [item.sort_order for item in remaining.prompt_templates] == [1, 2, 3]


def test_template_group_delete_requires_explicit_detach() -> None:
    service, templates, _, _, session = make_service()
    current_actor = actor()
    group = create_template_group(service, current_actor)
    templates.bound_group_ids.add(group.template_group_id)

    with pytest.raises(TemplateGroupInUseError):
        service.delete_template_group(current_actor, group.template_group_id)
    assert group.template_group_id in templates.groups
    assert session.rollbacks == 1

    templates.bound_group_ids.clear()
    service.delete_template_group(current_actor, group.template_group_id)
    assert group.template_group_id not in templates.groups


def test_product_material_group_crud_disable_and_delete_leave_assets() -> None:
    service, _, materials, assets, _ = make_service()
    current_actor = actor()
    group = create_material_group(service, current_actor)
    asset = assets.add(team_id=TEAM_A, created_by_user_id=USER_A)
    service.attach_asset(
        current_actor,
        group.material_group_id,
        MaterialGroupAssetAttach(asset_id=asset.asset_id, role=MaterialRole.PRODUCT_SOURCE),
    )

    updated = service.update_product_material_group(
        current_actor,
        group.material_group_id,
        ProductMaterialGroupUpdate(
            enabled=False,
            normal_generation_enabled=False,
            style_replication_enabled=False,
        ),
    )
    assert len(updated.asset_links) == 1
    assert updated.enabled is False
    assert updated.normal_generation_enabled is False
    service.delete_product_material_group(current_actor, group.material_group_id)
    assert group.material_group_id not in materials.groups
    assert asset.asset_id in assets.assets


def test_asset_attach_enforces_scope_team_role_and_deduplicates() -> None:
    service, _, _, assets, session = make_service()
    current_actor = actor(scope=DataScope.ALL)
    group = create_material_group(service, current_actor)
    same_team = assets.add(team_id=TEAM_A, created_by_user_id=USER_A2)
    cross_team = assets.add(team_id=TEAM_B, created_by_user_id=USER_B)

    attached = service.attach_asset(
        current_actor,
        group.material_group_id,
        MaterialGroupAssetAttach(
            asset_id=same_team.asset_id,
            role=MaterialRole.PRODUCT_SOURCE,
        ),
    )
    attached = service.attach_asset(
        current_actor,
        group.material_group_id,
        MaterialGroupAssetAttach(
            asset_id=same_team.asset_id,
            role=MaterialRole.STYLE_REFERENCE,
        ),
    )
    assert len(attached.asset_links) == 1
    assert attached.asset_links[0].role == MaterialRole.STYLE_REFERENCE.value

    with pytest.raises(AssetNotFoundError):
        service.attach_asset(
            current_actor,
            group.material_group_id,
            MaterialGroupAssetAttach(
                asset_id=cross_team.asset_id,
                role=MaterialRole.PRODUCT_SOURCE,
            ),
        )
    assert session.rollbacks == 1

    service.detach_asset(current_actor, group.material_group_id, same_team.asset_id)
    current = service.get_product_material_group(
        current_actor,
        group.material_group_id,
    )
    assert current.asset_links == []
    assert same_team.asset_id in assets.assets


def test_team_scope_cannot_attach_unreadable_asset() -> None:
    service, _, _, assets, _ = make_service()
    current_actor = actor(scope=DataScope.TEAM)
    group = create_material_group(service, current_actor)
    hidden = assets.add(team_id=TEAM_B, created_by_user_id=USER_B)

    with pytest.raises(AssetNotFoundError):
        service.attach_asset(
            current_actor,
            group.material_group_id,
            MaterialGroupAssetAttach(
                asset_id=hidden.asset_id,
                role=MaterialRole.PRODUCT_SOURCE,
            ),
        )


def test_template_binding_validates_mode_team_scope_and_normalizes_position() -> None:
    service, templates, _, _, _ = make_service()
    current_actor = actor(scope=DataScope.ALL)
    group = create_material_group(service, current_actor)
    first = create_template_group(service, current_actor, name="主图组一")
    second = create_template_group(service, current_actor, name="主图组二")
    style = create_template_group(
        service,
        current_actor,
        name="复刻组",
        mode=GenerationMode.STYLE_REPLICATION,
    )

    bound = service.replace_template_bindings(
        current_actor,
        group.material_group_id,
        GenerationMode.NORMAL_GENERATION,
        TemplateBindingReplace(
            template_group_ids=[
                second.template_group_id,
                first.template_group_id,
                second.template_group_id,
            ],
        ),
    )
    assert [item.template_group_id for item in bound.template_bindings] == [
        second.template_group_id,
        first.template_group_id,
    ]
    assert [item.position for item in bound.template_bindings] == [0, 1]

    with pytest.raises(TemplateBindingInvalidError):
        service.replace_template_bindings(
            current_actor,
            group.material_group_id,
            GenerationMode.NORMAL_GENERATION,
            TemplateBindingReplace(template_group_ids=[style.template_group_id]),
        )

    cross_team = TemplateGroup(
        template_group_id=uuid4(),
        team_id=TEAM_B,
        created_by_user_id=USER_B,
        name="跨团队模板",
        mode=GenerationMode.NORMAL_GENERATION.value,
        enabled=True,
    )
    stamp(cross_team)
    templates.groups[cross_team.template_group_id] = cross_team
    with pytest.raises(TemplateBindingInvalidError):
        service.replace_template_bindings(
            current_actor,
            group.material_group_id,
            GenerationMode.NORMAL_GENERATION,
            TemplateBindingReplace(template_group_ids=[cross_team.template_group_id]),
        )

    unbound = service.replace_template_bindings(
        current_actor,
        group.material_group_id,
        GenerationMode.NORMAL_GENERATION,
        TemplateBindingReplace(template_group_ids=[]),
    )
    assert unbound.template_bindings == []


def test_all_scope_can_read_but_cannot_write_cross_team_group() -> None:
    service, templates, materials, _, _ = make_service()
    all_actor = actor(scope=DataScope.ALL)
    cross_template = TemplateGroup(
        template_group_id=uuid4(),
        team_id=TEAM_B,
        created_by_user_id=USER_B,
        name="Team B 模板",
        mode=GenerationMode.NORMAL_GENERATION.value,
        enabled=True,
    )
    cross_material = ProductMaterialGroup(
        material_group_id=uuid4(),
        team_id=TEAM_B,
        created_by_user_id=USER_B,
        name="Team B 素材组",
        enabled=True,
        normal_generation_enabled=True,
        style_replication_enabled=False,
    )
    stamp(cross_template)
    stamp(cross_material)
    templates.groups[cross_template.template_group_id] = cross_template
    materials.groups[cross_material.material_group_id] = cross_material

    groups, total = service.list_template_groups(
        actor=all_actor,
        page=1,
        page_size=20,
        search=None,
        mode=None,
        enabled=None,
    )
    assert groups == [cross_template]
    assert total == 1
    with pytest.raises(ProductMaterialGroupNotFoundError):
        service.update_product_material_group(
            all_actor,
            cross_material.material_group_id,
            ProductMaterialGroupUpdate(enabled=False),
        )


def test_binding_persistence_failure_rolls_back_transaction() -> None:
    service, _, materials, _, session = make_service()
    current_actor = actor()
    group = create_material_group(service, current_actor)
    template = create_template_group(service, current_actor)
    materials.fail_binding_add = True

    with pytest.raises(RuntimeError, match="binding persistence failed"):
        service.replace_template_bindings(
            current_actor,
            group.material_group_id,
            GenerationMode.NORMAL_GENERATION,
            TemplateBindingReplace(template_group_ids=[template.template_group_id]),
        )
    assert session.rollbacks == 1
