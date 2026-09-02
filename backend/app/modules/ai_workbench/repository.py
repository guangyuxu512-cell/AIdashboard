from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Load, Session, selectinload
from sqlalchemy.sql import Select

from app.modules.access.contracts import ActorContext
from app.modules.access.policy import DataScopePolicy
from app.modules.ai_workbench.enums import GenerationMode
from app.modules.ai_workbench.models import (
    MaterialGroupAsset,
    MaterialGroupTemplateBinding,
    ProductMaterialGroup,
    PromptTemplate,
    TemplateGroup,
)


class TemplateRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

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
        statement = DataScopePolicy.apply(
            select(TemplateGroup),
            team_id_column=TemplateGroup.team_id,
            created_by_user_id_column=TemplateGroup.created_by_user_id,
            actor=actor,
        )
        statement = self._filter_groups(
            statement,
            search=search,
            mode=mode,
            enabled=enabled,
        )
        return list(
            self.session.scalars(
                statement.order_by(
                    TemplateGroup.created_at.desc(),
                    TemplateGroup.template_group_id.desc(),
                )
                .offset(offset)
                .limit(limit),
            ),
        )

    def count_groups(
        self,
        *,
        actor: ActorContext,
        search: str | None,
        mode: GenerationMode | None,
        enabled: bool | None,
    ) -> int:
        statement = DataScopePolicy.apply(
            select(func.count()).select_from(TemplateGroup),
            team_id_column=TemplateGroup.team_id,
            created_by_user_id_column=TemplateGroup.created_by_user_id,
            actor=actor,
        )
        statement = self._filter_groups(
            statement,
            search=search,
            mode=mode,
            enabled=enabled,
        )
        return int(self.session.scalar(statement) or 0)

    @staticmethod
    def _filter_groups(
        statement: Select[Any],
        *,
        search: str | None,
        mode: GenerationMode | None,
        enabled: bool | None,
    ) -> Select[Any]:
        if search:
            statement = statement.where(
                TemplateGroup.name.ilike(f"%{search}%"),
            )
        if mode is not None:
            statement = statement.where(TemplateGroup.mode == mode.value)
        if enabled is not None:
            statement = statement.where(TemplateGroup.enabled.is_(enabled))
        return statement

    def get_group_for_actor(
        self,
        *,
        actor: ActorContext,
        template_group_id: UUID,
    ) -> TemplateGroup | None:
        statement = DataScopePolicy.apply(
            select(TemplateGroup)
            .where(TemplateGroup.template_group_id == template_group_id)
            .options(selectinload(TemplateGroup.prompt_templates)),
            team_id_column=TemplateGroup.team_id,
            created_by_user_id_column=TemplateGroup.created_by_user_id,
            actor=actor,
        )
        return self.session.scalar(statement.execution_options(populate_existing=True))

    def get_group_for_write(
        self,
        *,
        actor: ActorContext,
        template_group_id: UUID,
    ) -> TemplateGroup | None:
        statement = DataScopePolicy.apply(
            select(TemplateGroup)
            .where(
                TemplateGroup.template_group_id == template_group_id,
                TemplateGroup.team_id == actor.team_id,
            )
            .options(selectinload(TemplateGroup.prompt_templates)),
            team_id_column=TemplateGroup.team_id,
            created_by_user_id_column=TemplateGroup.created_by_user_id,
            actor=actor,
        )
        return self.session.scalar(statement.with_for_update())

    def list_groups_for_binding(
        self,
        *,
        actor: ActorContext,
        team_id: UUID,
        template_group_ids: Sequence[UUID],
    ) -> list[TemplateGroup]:
        if not template_group_ids:
            return []
        statement = DataScopePolicy.apply(
            select(TemplateGroup).where(
                TemplateGroup.template_group_id.in_(template_group_ids),
                TemplateGroup.team_id == team_id,
            ),
            team_id_column=TemplateGroup.team_id,
            created_by_user_id_column=TemplateGroup.created_by_user_id,
            actor=actor,
        )
        return list(self.session.scalars(statement))

    def list_prompts_for_update(self, template_group_id: UUID) -> list[PromptTemplate]:
        return list(
            self.session.scalars(
                select(PromptTemplate)
                .where(PromptTemplate.template_group_id == template_group_id)
                .order_by(
                    PromptTemplate.sort_order.asc(),
                    PromptTemplate.prompt_template_id.asc(),
                )
                .with_for_update(),
            ),
        )

    def group_has_bindings(self, template_group_id: UUID) -> bool:
        statement = (
            select(MaterialGroupTemplateBinding.template_group_id)
            .where(
                MaterialGroupTemplateBinding.template_group_id == template_group_id,
            )
            .limit(1)
        )
        return self.session.scalar(statement) is not None

    def add_group(self, group: TemplateGroup) -> None:
        self.session.add(group)

    def delete_group(self, group: TemplateGroup) -> None:
        self.session.delete(group)

    def add_prompt(self, prompt: PromptTemplate) -> None:
        self.session.add(prompt)

    def delete_prompt(self, prompt: PromptTemplate) -> None:
        self.session.delete(prompt)


class ProductMaterialGroupRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_groups(
        self,
        *,
        actor: ActorContext,
        offset: int,
        limit: int,
        search: str | None,
        enabled: bool | None,
    ) -> list[ProductMaterialGroup]:
        statement = DataScopePolicy.apply(
            select(ProductMaterialGroup),
            team_id_column=ProductMaterialGroup.team_id,
            created_by_user_id_column=ProductMaterialGroup.created_by_user_id,
            actor=actor,
        )
        statement = self._filter_groups(statement, search=search, enabled=enabled)
        return list(
            self.session.scalars(
                statement.order_by(
                    ProductMaterialGroup.created_at.desc(),
                    ProductMaterialGroup.material_group_id.desc(),
                )
                .offset(offset)
                .limit(limit),
            ),
        )

    def count_groups(
        self,
        *,
        actor: ActorContext,
        search: str | None,
        enabled: bool | None,
    ) -> int:
        statement = DataScopePolicy.apply(
            select(func.count()).select_from(ProductMaterialGroup),
            team_id_column=ProductMaterialGroup.team_id,
            created_by_user_id_column=ProductMaterialGroup.created_by_user_id,
            actor=actor,
        )
        statement = self._filter_groups(statement, search=search, enabled=enabled)
        return int(self.session.scalar(statement) or 0)

    @staticmethod
    def _filter_groups(
        statement: Select[Any],
        *,
        search: str | None,
        enabled: bool | None,
    ) -> Select[Any]:
        if search:
            statement = statement.where(
                ProductMaterialGroup.name.ilike(f"%{search}%"),
            )
        if enabled is not None:
            statement = statement.where(ProductMaterialGroup.enabled.is_(enabled))
        return statement

    @staticmethod
    def _detail_options() -> tuple[Load, ...]:
        return (
            selectinload(ProductMaterialGroup.asset_links).joinedload(
                MaterialGroupAsset.asset,
            ),
            selectinload(ProductMaterialGroup.template_bindings),
        )

    def get_group_for_actor(
        self,
        *,
        actor: ActorContext,
        material_group_id: UUID,
    ) -> ProductMaterialGroup | None:
        statement = DataScopePolicy.apply(
            select(ProductMaterialGroup)
            .where(ProductMaterialGroup.material_group_id == material_group_id)
            .options(*self._detail_options()),
            team_id_column=ProductMaterialGroup.team_id,
            created_by_user_id_column=ProductMaterialGroup.created_by_user_id,
            actor=actor,
        )
        return self.session.scalar(statement.execution_options(populate_existing=True))

    def get_group_for_write(
        self,
        *,
        actor: ActorContext,
        material_group_id: UUID,
    ) -> ProductMaterialGroup | None:
        statement = DataScopePolicy.apply(
            select(ProductMaterialGroup)
            .where(
                ProductMaterialGroup.material_group_id == material_group_id,
                ProductMaterialGroup.team_id == actor.team_id,
            )
            .options(*self._detail_options()),
            team_id_column=ProductMaterialGroup.team_id,
            created_by_user_id_column=ProductMaterialGroup.created_by_user_id,
            actor=actor,
        )
        return self.session.scalar(statement.with_for_update())

    def add_group(self, group: ProductMaterialGroup) -> None:
        self.session.add(group)

    def delete_group(self, group: ProductMaterialGroup) -> None:
        self.session.delete(group)

    def add_asset_link(self, link: MaterialGroupAsset) -> None:
        self.session.add(link)

    def delete_asset_link(self, link: MaterialGroupAsset) -> None:
        self.session.delete(link)

    def delete_bindings(self, material_group_id: UUID, mode: GenerationMode) -> None:
        self.session.execute(
            delete(MaterialGroupTemplateBinding).where(
                MaterialGroupTemplateBinding.material_group_id == material_group_id,
                MaterialGroupTemplateBinding.generation_mode == mode.value,
            ),
        )

    def add_bindings(
        self,
        bindings: Sequence[MaterialGroupTemplateBinding],
    ) -> None:
        self.session.add_all(bindings)
