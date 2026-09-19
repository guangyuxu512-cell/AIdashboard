from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
from app.modules.ai_workbench.enums import GenerationMode, MaterialRole, OutputRole
from app.modules.ai_workbench.exceptions import (
    MaterialAssetRoleInvalidError,
    ProductMaterialGroupHasActiveGenerationJobsError,
    ProductMaterialGroupNotFoundError,
    PromptTemplateNotFoundError,
    TemplateBindingInvalidError,
    TemplateGroupInUseError,
    TemplateGroupNotFoundError,
    TemplateSequenceInvalidError,
)
from app.modules.ai_workbench.models import (
    MaterialGroupAsset,
    MaterialGroupTemplateBinding,
    ProductMaterialGroup,
    PromptTemplate,
    TemplateGroup,
)
from app.modules.ai_workbench.repository import (
    GenerationRepository,
    ProductMaterialGroupRepository,
    TemplateRepository,
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
from app.modules.assets.exceptions import AssetNotFoundError
from app.modules.assets.service import AssetService
from app.shared.identifiers import generate_id


ROLE_ORDER = {
    OutputRole.MAIN_IMAGE.value: 0,
    OutputRole.DETAIL_IMAGE.value: 1,
}


class AiWorkbenchService:
    def __init__(
        self,
        session: Session,
        *,
        template_repository: TemplateRepository | None = None,
        material_group_repository: ProductMaterialGroupRepository | None = None,
        generation_repository: GenerationRepository | None = None,
        asset_service: AssetService | None = None,
    ) -> None:
        self.session = session
        self.template_repository = template_repository or TemplateRepository(session)
        self.material_group_repository = (
            material_group_repository or ProductMaterialGroupRepository(session)
        )
        self.generation_repository = generation_repository or GenerationRepository(
            session,
        )
        self.asset_service = asset_service or AssetService(session)

    def list_template_groups(
        self,
        *,
        actor: ActorContext,
        page: int,
        page_size: int,
        search: str | None,
        mode: GenerationMode | None,
        enabled: bool | None,
    ) -> tuple[list[TemplateGroup], int]:
        normalized_search = search.strip() if search else None
        return (
            self.template_repository.list_groups(
                actor=actor,
                offset=(page - 1) * page_size,
                limit=page_size,
                search=normalized_search or None,
                mode=mode,
                enabled=enabled,
            ),
            self.template_repository.count_groups(
                actor=actor,
                search=normalized_search or None,
                mode=mode,
                enabled=enabled,
            ),
        )

    def get_template_group(
        self,
        actor: ActorContext,
        template_group_id: UUID,
    ) -> TemplateGroup:
        group = self.template_repository.get_group_for_actor(
            actor=actor,
            template_group_id=template_group_id,
        )
        if group is None:
            raise TemplateGroupNotFoundError()
        return group

    def create_template_group(
        self,
        actor: ActorContext,
        data: TemplateGroupCreate,
    ) -> TemplateGroup:
        group = TemplateGroup(
            template_group_id=generate_id(),
            team_id=actor.require_team_id(),
            created_by_user_id=actor.user_id,
            name=data.name,
            mode=data.mode.value,
            enabled=data.enabled,
        )
        self.template_repository.add_group(group)
        self.session.commit()
        return self.get_template_group(actor, group.template_group_id)

    def update_template_group(
        self,
        actor: ActorContext,
        template_group_id: UUID,
        data: TemplateGroupUpdate,
    ) -> TemplateGroup:
        group = self._template_group_for_write(actor, template_group_id)
        for field_name, value in data.model_dump(exclude_unset=True).items():
            setattr(group, field_name, value)
        self.session.commit()
        return self.get_template_group(actor, template_group_id)

    def delete_template_group(
        self,
        actor: ActorContext,
        template_group_id: UUID,
    ) -> None:
        group = self._template_group_for_write(actor, template_group_id)
        if self.template_repository.group_has_bindings(template_group_id):
            self.session.rollback()
            raise TemplateGroupInUseError()
        self.template_repository.delete_group(group)
        self.session.commit()

    def create_prompt_template(
        self,
        actor: ActorContext,
        template_group_id: UUID,
        data: PromptTemplateCreate,
    ) -> TemplateGroup:
        group = self._template_group_for_write(actor, template_group_id)
        prompts = self.template_repository.list_prompts_for_update(template_group_id)
        prompt = PromptTemplate(
            prompt_template_id=generate_id(),
            template_group_id=template_group_id,
            name=data.name,
            enabled=data.enabled,
            output_role=data.output_role.value,
            output_format=data.output_format.value,
            size=data.size.value,
            count=data.count,
            variables=list(data.variables),
            prompt=data.prompt,
            sort_order=len(prompts) + 1,
        )
        self.template_repository.add_prompt(prompt)
        self._normalize_prompt_sequence([*prompts, prompt])
        group.updated_at = datetime.now(UTC)
        self.session.commit()
        return self.get_template_group(actor, template_group_id)

    def update_prompt_template(
        self,
        actor: ActorContext,
        template_group_id: UUID,
        prompt_template_id: UUID,
        data: PromptTemplateUpdate,
    ) -> TemplateGroup:
        group = self._template_group_for_write(actor, template_group_id)
        prompts = self.template_repository.list_prompts_for_update(template_group_id)
        prompt = self._find_prompt(prompts, prompt_template_id)
        for field_name, value in data.model_dump(exclude_unset=True).items():
            if field_name in {"output_format", "size"}:
                value = value.value
            elif field_name == "variables":
                value = list(value)
            setattr(prompt, field_name, value)
        group.updated_at = datetime.now(UTC)
        self.session.commit()
        return self.get_template_group(actor, template_group_id)

    def delete_prompt_template(
        self,
        actor: ActorContext,
        template_group_id: UUID,
        prompt_template_id: UUID,
    ) -> None:
        group = self._template_group_for_write(actor, template_group_id)
        prompts = self.template_repository.list_prompts_for_update(template_group_id)
        prompt = self._find_prompt(prompts, prompt_template_id)
        self.template_repository.delete_prompt(prompt)
        self._normalize_prompt_sequence(
            [candidate for candidate in prompts if candidate is not prompt],
        )
        group.updated_at = datetime.now(UTC)
        self.session.commit()

    def duplicate_prompt_template(
        self,
        actor: ActorContext,
        template_group_id: UUID,
        prompt_template_id: UUID,
    ) -> TemplateGroup:
        group = self._template_group_for_write(actor, template_group_id)
        prompts = self.template_repository.list_prompts_for_update(template_group_id)
        self._normalize_prompt_sequence(prompts)
        source = self._find_prompt(prompts, prompt_template_id)
        source_index = prompts.index(source)
        suffix = " 副本"
        copy = PromptTemplate(
            prompt_template_id=generate_id(),
            template_group_id=template_group_id,
            name=f"{source.name[: 100 - len(suffix)]}{suffix}",
            enabled=source.enabled,
            output_role=source.output_role,
            output_format=source.output_format,
            size=source.size,
            count=source.count,
            variables=list(source.variables),
            prompt=source.prompt,
            sort_order=source.sort_order + 1,
        )
        prompts.insert(source_index + 1, copy)
        self._assign_prompt_sort_order(prompts)
        self.template_repository.add_prompt(copy)
        group.updated_at = datetime.now(UTC)
        self.session.commit()
        return self.get_template_group(actor, template_group_id)

    def reorder_prompt_templates(
        self,
        actor: ActorContext,
        template_group_id: UUID,
        data: PromptTemplateReorder,
    ) -> TemplateGroup:
        group = self._template_group_for_write(actor, template_group_id)
        prompts = self.template_repository.list_prompts_for_update(template_group_id)
        self._normalize_prompt_sequence(prompts)
        role_prompts = [
            prompt
            for prompt in prompts
            if prompt.output_role == data.output_role.value
        ]
        by_id = {prompt.prompt_template_id: prompt for prompt in role_prompts}
        if set(data.prompt_template_ids) != set(by_id):
            self.session.rollback()
            raise TemplateSequenceInvalidError()
        ordered_role = [by_id[prompt_id] for prompt_id in data.prompt_template_ids]
        if data.output_role is OutputRole.MAIN_IMAGE:
            ordered = ordered_role + [
                prompt
                for prompt in prompts
                if prompt.output_role == OutputRole.DETAIL_IMAGE.value
            ]
        else:
            ordered = [
                prompt
                for prompt in prompts
                if prompt.output_role == OutputRole.MAIN_IMAGE.value
            ] + ordered_role
        self._assign_prompt_sort_order(ordered)
        group.updated_at = datetime.now(UTC)
        self.session.commit()
        return self.get_template_group(actor, template_group_id)

    def list_product_material_groups(
        self,
        *,
        actor: ActorContext,
        page: int,
        page_size: int,
        search: str | None,
        enabled: bool | None,
    ) -> tuple[list[ProductMaterialGroup], int]:
        normalized_search = search.strip() if search else None
        return (
            self.material_group_repository.list_groups(
                actor=actor,
                offset=(page - 1) * page_size,
                limit=page_size,
                search=normalized_search or None,
                enabled=enabled,
            ),
            self.material_group_repository.count_groups(
                actor=actor,
                search=normalized_search or None,
                enabled=enabled,
            ),
        )

    def get_product_material_group(
        self,
        actor: ActorContext,
        material_group_id: UUID,
    ) -> ProductMaterialGroup:
        group = self.material_group_repository.get_group_for_actor(
            actor=actor,
            material_group_id=material_group_id,
        )
        if group is None:
            raise ProductMaterialGroupNotFoundError()
        return group

    def create_product_material_group(
        self,
        actor: ActorContext,
        data: ProductMaterialGroupCreate,
    ) -> ProductMaterialGroup:
        group = ProductMaterialGroup(
            material_group_id=generate_id(),
            team_id=actor.require_team_id(),
            created_by_user_id=actor.user_id,
            **data.model_dump(),
        )
        self.material_group_repository.add_group(group)
        self.session.commit()
        return self.get_product_material_group(actor, group.material_group_id)

    def update_product_material_group(
        self,
        actor: ActorContext,
        material_group_id: UUID,
        data: ProductMaterialGroupUpdate,
    ) -> ProductMaterialGroup:
        group = self._material_group_for_write(actor, material_group_id)
        for field_name, value in data.model_dump(exclude_unset=True).items():
            setattr(group, field_name, value)
        self.session.commit()
        return self.get_product_material_group(actor, material_group_id)

    def delete_product_material_group(
        self,
        actor: ActorContext,
        material_group_id: UUID,
    ) -> None:
        if not self.material_group_repository.exists_in_write_scope(
            actor=actor,
            material_group_id=material_group_id,
        ):
            raise ProductMaterialGroupNotFoundError()
        self.generation_repository.lock_material_group_references(material_group_id)
        group = self._material_group_for_write(actor, material_group_id)
        if self.generation_repository.has_active_jobs_for_material_group(
            material_group_id,
        ):
            self.session.rollback()
            raise ProductMaterialGroupHasActiveGenerationJobsError()
        self.material_group_repository.delete_group(group)
        self.session.commit()

    def attach_asset(
        self,
        actor: ActorContext,
        material_group_id: UUID,
        data: MaterialGroupAssetAttach,
    ) -> ProductMaterialGroup:
        group = self._material_group_for_write(actor, material_group_id)
        assets = self.asset_service.list_accessible_by_ids(actor, [data.asset_id])
        if len(assets) != 1 or assets[0].team_id != group.team_id:
            self.session.rollback()
            raise AssetNotFoundError()
        existing = next(
            (link for link in group.asset_links if link.asset_id == data.asset_id),
            None,
        )
        if existing is not None and existing.role == MaterialRole.AI_OUTPUT.value:
            self.session.rollback()
            raise MaterialAssetRoleInvalidError()
        if existing is None:
            self.material_group_repository.add_asset_link(
                MaterialGroupAsset(
                    material_group_id=material_group_id,
                    asset_id=data.asset_id,
                    role=data.role.value,
                ),
            )
        else:
            existing.role = data.role.value
        group.updated_at = datetime.now(UTC)
        self.session.commit()
        return self.get_product_material_group(actor, material_group_id)

    def detach_asset(
        self,
        actor: ActorContext,
        material_group_id: UUID,
        asset_id: UUID,
    ) -> None:
        group = self._material_group_for_write(actor, material_group_id)
        existing = next(
            (link for link in group.asset_links if link.asset_id == asset_id),
            None,
        )
        if existing is None:
            self.session.rollback()
            return
        self.material_group_repository.delete_asset_link(existing)
        group.updated_at = datetime.now(UTC)
        self.session.commit()

    def replace_template_bindings(
        self,
        actor: ActorContext,
        material_group_id: UUID,
        mode: GenerationMode,
        data: TemplateBindingReplace,
    ) -> ProductMaterialGroup:
        group = self._material_group_for_write(actor, material_group_id)
        template_group_ids = list(dict.fromkeys(data.template_group_ids))
        template_groups = self.template_repository.list_groups_for_binding(
            actor=actor,
            team_id=group.team_id,
            template_group_ids=template_group_ids,
        )
        by_id = {item.template_group_id: item for item in template_groups}
        if set(template_group_ids) != set(by_id) or any(
            by_id[template_group_id].mode != mode.value
            for template_group_id in template_group_ids
        ):
            self.session.rollback()
            raise TemplateBindingInvalidError()
        bindings = [
            MaterialGroupTemplateBinding(
                material_group_id=material_group_id,
                template_group_id=template_group_id,
                generation_mode=mode.value,
                position=position,
            )
            for position, template_group_id in enumerate(template_group_ids)
        ]
        try:
            self.material_group_repository.delete_bindings(material_group_id, mode)
            self.material_group_repository.add_bindings(bindings)
            group.updated_at = datetime.now(UTC)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return self.get_product_material_group(actor, material_group_id)

    def _template_group_for_write(
        self,
        actor: ActorContext,
        template_group_id: UUID,
    ) -> TemplateGroup:
        group = self.template_repository.get_group_for_write(
            actor=actor,
            template_group_id=template_group_id,
        )
        if group is None:
            raise TemplateGroupNotFoundError()
        return group

    def _material_group_for_write(
        self,
        actor: ActorContext,
        material_group_id: UUID,
    ) -> ProductMaterialGroup:
        group = self.material_group_repository.get_group_for_write(
            actor=actor,
            material_group_id=material_group_id,
        )
        if group is None:
            raise ProductMaterialGroupNotFoundError()
        return group

    @staticmethod
    def _find_prompt(
        prompts: list[PromptTemplate],
        prompt_template_id: UUID,
    ) -> PromptTemplate:
        prompt = next(
            (
                candidate
                for candidate in prompts
                if candidate.prompt_template_id == prompt_template_id
            ),
            None,
        )
        if prompt is None:
            raise PromptTemplateNotFoundError()
        return prompt

    @staticmethod
    def _normalize_prompt_sequence(prompts: list[PromptTemplate]) -> None:
        prompts.sort(
            key=lambda prompt: (
                ROLE_ORDER[prompt.output_role],
                prompt.sort_order,
                str(prompt.prompt_template_id),
            ),
        )
        AiWorkbenchService._assign_prompt_sort_order(prompts)

    @staticmethod
    def _assign_prompt_sort_order(prompts: list[PromptTemplate]) -> None:
        for position, prompt in enumerate(prompts, start=1):
            prompt.sort_order = position
