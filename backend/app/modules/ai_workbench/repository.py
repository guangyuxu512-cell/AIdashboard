from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import case, delete, func, select
from sqlalchemy.orm import Load, Session, noload, selectinload
from sqlalchemy.sql import Select

from app.modules.access.contracts import ActorContext
from app.modules.access.policy import DataScopePolicy
from app.modules.ai_workbench.enums import (
    GenerationInputRole,
    GenerationItemStatus,
    GenerationJobStatus,
    GenerationMode,
    GenerationWorkMode,
)
from app.modules.assets.models import Asset
from app.modules.ai_workbench.models import (
    GenerationItem,
    GenerationItemAsset,
    GenerationJob,
    GenerationProviderExecution,
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

    def list_groups_for_generation(
        self,
        *,
        actor: ActorContext,
        team_id: UUID,
        template_group_ids: Sequence[UUID],
    ) -> list[TemplateGroup]:
        if not template_group_ids:
            return []
        statement = DataScopePolicy.apply(
            select(TemplateGroup)
            .where(
                TemplateGroup.template_group_id.in_(template_group_ids),
                TemplateGroup.team_id == team_id,
            )
            .options(selectinload(TemplateGroup.prompt_templates)),
            team_id_column=TemplateGroup.team_id,
            created_by_user_id_column=TemplateGroup.created_by_user_id,
            actor=actor,
        )
        return list(self.session.scalars(statement.with_for_update()))

    def get_prompt_source_for_generation(
        self,
        *,
        actor: ActorContext,
        team_id: UUID,
        prompt_template_id: UUID,
    ) -> PromptTemplate | None:
        statement = DataScopePolicy.apply(
            select(PromptTemplate)
            .join(TemplateGroup)
            .where(
                PromptTemplate.prompt_template_id == prompt_template_id,
                TemplateGroup.team_id == team_id,
            )
            .options(selectinload(PromptTemplate.template_group)),
            team_id_column=TemplateGroup.team_id,
            created_by_user_id_column=TemplateGroup.created_by_user_id,
            actor=actor,
        )
        return self.session.scalar(statement.with_for_update())

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

    def exists_in_write_scope(
        self,
        *,
        actor: ActorContext,
        material_group_id: UUID,
    ) -> bool:
        statement = DataScopePolicy.apply(
            select(ProductMaterialGroup.material_group_id).where(
                ProductMaterialGroup.material_group_id == material_group_id,
                ProductMaterialGroup.team_id == actor.team_id,
            ),
            team_id_column=ProductMaterialGroup.team_id,
            created_by_user_id_column=ProductMaterialGroup.created_by_user_id,
            actor=actor,
        )
        return self.session.scalar(statement) is not None

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

    def list_groups_for_generation(
        self,
        *,
        actor: ActorContext,
        team_id: UUID,
        material_group_ids: Sequence[UUID] | None,
        limit: int,
    ) -> list[ProductMaterialGroup]:
        statement = DataScopePolicy.apply(
            select(ProductMaterialGroup)
            .where(ProductMaterialGroup.team_id == team_id)
            .options(*self._detail_options()),
            team_id_column=ProductMaterialGroup.team_id,
            created_by_user_id_column=ProductMaterialGroup.created_by_user_id,
            actor=actor,
        )
        if material_group_ids is None:
            statement = statement.where(ProductMaterialGroup.enabled.is_(True))
        elif material_group_ids:
            statement = statement.where(
                ProductMaterialGroup.material_group_id.in_(material_group_ids),
            )
        else:
            return []
        statement = statement.order_by(
            ProductMaterialGroup.created_at.asc(),
            ProductMaterialGroup.material_group_id.asc(),
        ).limit(limit)
        return list(self.session.scalars(statement.with_for_update()))

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


@dataclass(frozen=True, slots=True)
class GenerationCounts:
    total_count: int = 0
    pending_count: int = 0
    running_count: int = 0
    success_count: int = 0
    failed_count: int = 0


@dataclass(frozen=True, slots=True)
class GenerationInputSummary:
    count: int = 0
    primary_name: str | None = None


class GenerationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _detail_options() -> tuple[Load, ...]:
        return (
            selectinload(GenerationJob.items)
            .selectinload(GenerationItem.input_assets)
            .joinedload(GenerationItemAsset.asset),
            selectinload(GenerationJob.items).joinedload(
                GenerationItem.output_asset,
            ),
        )

    def get_by_submission(
        self,
        *,
        team_id: UUID,
        created_by_user_id: UUID,
        submission_key: str,
    ) -> GenerationJob | None:
        return self.session.scalar(
            select(GenerationJob)
            .where(
                GenerationJob.team_id == team_id,
                GenerationJob.created_by_user_id == created_by_user_id,
                GenerationJob.submission_key == submission_key,
            )
            .options(*self._detail_options())
            .execution_options(populate_existing=True),
        )

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
        statement = DataScopePolicy.apply(
            select(GenerationJob),
            team_id_column=GenerationJob.team_id,
            created_by_user_id_column=GenerationJob.created_by_user_id,
            actor=actor,
        )
        statement = self._filter_jobs(
            statement,
            work_mode=work_mode,
            mode=mode,
            status=status,
        )
        statement = statement.options(noload(GenerationJob.items))
        return list(
            self.session.scalars(
                statement.order_by(
                    GenerationJob.created_at.desc(),
                    GenerationJob.generation_job_id.desc(),
                )
                .offset(offset)
                .limit(limit),
            ),
        )

    def count_jobs(
        self,
        *,
        actor: ActorContext,
        work_mode: GenerationWorkMode | None,
        mode: GenerationMode | None,
        status: GenerationJobStatus | None,
    ) -> int:
        statement = DataScopePolicy.apply(
            select(func.count()).select_from(GenerationJob),
            team_id_column=GenerationJob.team_id,
            created_by_user_id_column=GenerationJob.created_by_user_id,
            actor=actor,
        )
        statement = self._filter_jobs(
            statement,
            work_mode=work_mode,
            mode=mode,
            status=status,
        )
        return int(self.session.scalar(statement) or 0)

    @staticmethod
    def _filter_jobs(
        statement: Select[Any],
        *,
        work_mode: GenerationWorkMode | None,
        mode: GenerationMode | None,
        status: GenerationJobStatus | None,
    ) -> Select[Any]:
        if work_mode is not None:
            statement = statement.where(GenerationJob.work_mode == work_mode.value)
        if mode is not None:
            statement = statement.where(GenerationJob.mode == mode.value)
        if status is not None:
            statement = statement.where(GenerationJob.status == status.value)
        return statement

    def counts_by_job_ids(
        self,
        job_ids: Sequence[UUID],
    ) -> dict[UUID, GenerationCounts]:
        if not job_ids:
            return {}
        rows = self.session.execute(
            select(
                GenerationItem.generation_job_id,
                func.count().label("total_count"),
                func.count().filter(
                    GenerationItem.status == GenerationItemStatus.PENDING.value,
                ),
                func.count().filter(
                    GenerationItem.status == GenerationItemStatus.RUNNING.value,
                ),
                func.count().filter(
                    GenerationItem.status == GenerationItemStatus.SUCCESS.value,
                ),
                func.count().filter(
                    GenerationItem.status == GenerationItemStatus.FAILED.value,
                ),
            )
            .where(GenerationItem.generation_job_id.in_(job_ids))
            .group_by(GenerationItem.generation_job_id),
        )
        return {
            row[0]: GenerationCounts(
                total_count=int(row[1]),
                pending_count=int(row[2]),
                running_count=int(row[3]),
                success_count=int(row[4]),
                failed_count=int(row[5]),
            )
            for row in rows
        }

    def input_summaries_by_job_ids(
        self,
        job_ids: Sequence[UUID],
    ) -> dict[UUID, GenerationInputSummary]:
        if not job_ids:
            return {}
        summaries = {job_id: GenerationInputSummary() for job_id in job_ids}
        instant_count_rows = self.session.execute(
            select(
                GenerationItem.generation_job_id,
                func.count(func.distinct(GenerationItemAsset.asset_id)),
            )
            .join(
                GenerationItemAsset,
                GenerationItemAsset.generation_item_id
                == GenerationItem.generation_item_id,
            )
            .join(
                GenerationJob,
                GenerationJob.generation_job_id == GenerationItem.generation_job_id,
            )
            .where(
                GenerationItem.generation_job_id.in_(job_ids),
                GenerationJob.work_mode == GenerationWorkMode.INSTANT.value,
                GenerationItemAsset.input_role
                == GenerationInputRole.PRODUCT_SOURCE.value,
            )
            .group_by(GenerationItem.generation_job_id),
        )
        for job_id, count in instant_count_rows:
            summaries[job_id] = GenerationInputSummary(count=int(count))

        ranked_instant_names = (
            select(
                GenerationItem.generation_job_id.label("generation_job_id"),
                Asset.original_filename.label("primary_name"),
                func.row_number()
                .over(
                    partition_by=GenerationItem.generation_job_id,
                    order_by=(
                        GenerationItem.position,
                        GenerationItemAsset.position,
                        GenerationItemAsset.asset_id,
                    ),
                )
                .label("input_rank"),
            )
            .join(
                GenerationItemAsset,
                GenerationItemAsset.generation_item_id
                == GenerationItem.generation_item_id,
            )
            .join(Asset, Asset.asset_id == GenerationItemAsset.asset_id)
            .join(
                GenerationJob,
                GenerationJob.generation_job_id == GenerationItem.generation_job_id,
            )
            .where(
                GenerationItem.generation_job_id.in_(job_ids),
                GenerationJob.work_mode == GenerationWorkMode.INSTANT.value,
                GenerationItemAsset.input_role
                == GenerationInputRole.PRODUCT_SOURCE.value,
            )
            .subquery()
        )
        instant_name_rows = self.session.execute(
            select(
                ranked_instant_names.c.generation_job_id,
                ranked_instant_names.c.primary_name,
            ).where(ranked_instant_names.c.input_rank == 1),
        )
        for job_id, primary_name in instant_name_rows:
            current = summaries[job_id]
            summaries[job_id] = GenerationInputSummary(
                count=current.count,
                primary_name=primary_name,
            )

        batch_rows = self.session.execute(
            select(
                GenerationItem.generation_job_id,
                func.count(func.distinct(GenerationItem.source_product_position)),
                func.min(GenerationItem.product_name_snapshot),
            )
            .join(
                GenerationJob,
                GenerationJob.generation_job_id == GenerationItem.generation_job_id,
            )
            .where(
                GenerationItem.generation_job_id.in_(job_ids),
                GenerationJob.work_mode == GenerationWorkMode.BATCH.value,
            )
            .group_by(GenerationItem.generation_job_id),
        )
        for job_id, count, primary_name in batch_rows:
            resolved_count = int(count)
            summaries[job_id] = GenerationInputSummary(
                count=resolved_count,
                primary_name=primary_name if resolved_count == 1 else None,
            )
        return summaries

    def get_job_for_actor(
        self,
        *,
        actor: ActorContext,
        generation_job_id: UUID,
    ) -> GenerationJob | None:
        statement = DataScopePolicy.apply(
            select(GenerationJob)
            .where(GenerationJob.generation_job_id == generation_job_id)
            .options(*self._detail_options()),
            team_id_column=GenerationJob.team_id,
            created_by_user_id_column=GenerationJob.created_by_user_id,
            actor=actor,
        )
        return self.session.scalar(statement.execution_options(populate_existing=True))

    def get_job_for_write(
        self,
        *,
        actor: ActorContext,
        generation_job_id: UUID,
    ) -> GenerationJob | None:
        statement = DataScopePolicy.apply(
            select(GenerationJob).where(
                GenerationJob.generation_job_id == generation_job_id,
                GenerationJob.team_id == actor.team_id,
            ),
            team_id_column=GenerationJob.team_id,
            created_by_user_id_column=GenerationJob.created_by_user_id,
            actor=actor,
        )
        return self.session.scalar(statement.with_for_update())

    def get_job_by_id(self, generation_job_id: UUID) -> GenerationJob | None:
        return self.session.scalar(
            select(GenerationJob)
            .where(GenerationJob.generation_job_id == generation_job_id)
            .options(*self._detail_options())
            .execution_options(populate_existing=True),
        )

    def lock_items_for_retry(
        self,
        *,
        generation_job_id: UUID,
        item_ids: Sequence[UUID],
    ) -> list[GenerationItem]:
        return list(
            self.session.scalars(
                select(GenerationItem)
                .where(
                    GenerationItem.generation_job_id == generation_job_id,
                    GenerationItem.generation_item_id.in_(item_ids),
                )
                .order_by(GenerationItem.generation_item_id)
                .with_for_update(),
            ),
        )

    def get_item_for_job_for_update(
        self,
        *,
        generation_job_id: UUID,
        generation_item_id: UUID,
    ) -> GenerationItem | None:
        return self.session.scalar(
            select(GenerationItem)
            .where(
                GenerationItem.generation_job_id == generation_job_id,
                GenerationItem.generation_item_id == generation_item_id,
            )
            .with_for_update(),
        )

    def lock_material_group_references(self, material_group_id: UUID) -> None:
        job_ids = list(
            self.session.scalars(
                select(GenerationItem.generation_job_id)
                .where(
                    GenerationItem.source_product_material_group_id
                    == material_group_id,
                )
                .distinct(),
            ),
        )
        if not job_ids:
            return
        list(
            self.session.scalars(
                select(GenerationJob.generation_job_id)
                .where(GenerationJob.generation_job_id.in_(job_ids))
                .order_by(GenerationJob.generation_job_id)
                .with_for_update(),
            ),
        )
        list(
            self.session.scalars(
                select(GenerationItem.generation_item_id)
                .where(
                    GenerationItem.source_product_material_group_id
                    == material_group_id,
                )
                .order_by(GenerationItem.generation_item_id)
                .with_for_update(),
            ),
        )

    def get_item_for_execution(
        self,
        generation_item_id: UUID,
    ) -> GenerationItem | None:
        generation_job_id = self.session.scalar(
            select(GenerationItem.generation_job_id).where(
                GenerationItem.generation_item_id == generation_item_id,
            ),
        )
        if generation_job_id is None:
            return None
        self.session.scalar(
            select(GenerationJob)
            .where(GenerationJob.generation_job_id == generation_job_id)
            .with_for_update(),
        )
        return self.session.scalar(
            select(GenerationItem)
            .where(GenerationItem.generation_item_id == generation_item_id)
            .options(
                selectinload(GenerationItem.input_assets).joinedload(
                    GenerationItemAsset.asset,
                ),
                selectinload(GenerationItem.job),
                selectinload(GenerationItem.provider_execution),
            )
            .with_for_update(),
        )

    def next_item_id_for_provider_execution(self) -> UUID | None:
        return self.session.scalar(
            select(GenerationItem.generation_item_id)
            .where(
                GenerationItem.status.in_(
                    [
                        GenerationItemStatus.PENDING.value,
                        GenerationItemStatus.RUNNING.value,
                    ],
                ),
            )
            .order_by(
                case(
                    (GenerationItem.status == GenerationItemStatus.RUNNING.value, 0),
                    else_=1,
                ),
                GenerationItem.created_at,
                GenerationItem.generation_item_id,
            )
            .limit(1),
        )

    def add_provider_execution(
        self,
        execution: GenerationProviderExecution,
    ) -> None:
        self.session.add(execution)

    def material_groups_exist_for_team(
        self,
        *,
        team_id: UUID,
        material_group_ids: Sequence[UUID],
    ) -> set[UUID]:
        if not material_group_ids:
            return set()
        return set(
            self.session.scalars(
                select(ProductMaterialGroup.material_group_id)
                .where(
                    ProductMaterialGroup.team_id == team_id,
                    ProductMaterialGroup.material_group_id.in_(material_group_ids),
                )
                .with_for_update(),
            ),
        )

    def get_material_group_for_output(
        self,
        *,
        team_id: UUID,
        material_group_id: UUID,
    ) -> ProductMaterialGroup | None:
        return self.session.scalar(
            select(ProductMaterialGroup)
            .where(
                ProductMaterialGroup.team_id == team_id,
                ProductMaterialGroup.material_group_id == material_group_id,
            )
            .with_for_update(),
        )

    def has_active_jobs_for_material_group(self, material_group_id: UUID) -> bool:
        statement = (
            select(GenerationItem.generation_item_id)
            .join(GenerationJob)
            .where(
                GenerationItem.source_product_material_group_id == material_group_id,
                GenerationJob.status.in_(
                    [
                        GenerationJobStatus.PENDING.value,
                        GenerationJobStatus.RUNNING.value,
                    ],
                ),
            )
            .limit(1)
        )
        return self.session.scalar(statement) is not None

    def add_job(self, job: GenerationJob) -> None:
        self.session.add(job)

    def add_material_group_asset(
        self,
        group: ProductMaterialGroup,
        link: MaterialGroupAsset,
    ) -> None:
        group.asset_links.append(link)
