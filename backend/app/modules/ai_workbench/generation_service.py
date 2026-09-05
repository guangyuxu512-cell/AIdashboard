from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import BinaryIO
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
from app.modules.ai_workbench.enums import (
    BatchProductScope,
    BatchTemplateSource,
    GenerationInputRole,
    GenerationItemStatus,
    GenerationJobStatus,
    GenerationMode,
    GenerationSize,
    GenerationOutputRange,
    GenerationWorkMode,
    MaterialRole,
    OutputFormat,
    OutputRole,
)
from app.modules.ai_workbench.exceptions import (
    GenerationItemNotFoundError,
    GenerationItemStateConflictError,
    GenerationJobNotFoundError,
    GenerationPlanInvalidError,
    GenerationPlanTooLargeError,
    ProviderCreateOutcomeUnknownError,
    GenerationRetryConflictError,
    GenerationSubmissionConflictError,
    ProductMaterialGroupNotFoundError,
    PromptTemplateNotFoundError,
    TemplateBindingInvalidError,
)
from app.modules.ai_workbench.limits import (
    MAX_GENERATION_INPUT_ASSETS,
    MAX_GENERATION_ITEM_INPUT_ASSETS,
    MAX_GENERATION_ITEMS,
    MAX_GENERATION_SELECTION_IDS,
)
from app.modules.ai_workbench.models import (
    GenerationItem,
    GenerationItemAsset,
    GenerationJob,
    GenerationProviderExecution,
    MaterialGroupAsset,
    ProductMaterialGroup,
    PromptTemplate,
    TemplateGroup,
)
from app.modules.ai_workbench.repository import (
    GenerationCounts,
    GenerationInputSummary,
    GenerationRepository,
    ProductMaterialGroupRepository,
    TemplateRepository,
)
from app.modules.ai_workbench.schemas import (
    BatchGenerationSubmit,
    GenerationItemArchiveRequest,
    GenerationRetryRequest,
    GenerationSubmit,
    InstantGenerationSubmit,
)
from app.modules.assets.contracts import AssetOwnership
from app.modules.assets.enums import AssetMediaType, AssetSourceType
from app.modules.assets.exceptions import AssetNotFoundError
from app.modules.assets.models import Asset
from app.modules.assets.service import AssetService
from app.shared.identifiers import generate_id


OUTPUT_PERSISTENCE_FAILURE_CODE = "OUTPUT_PERSISTENCE_FAILED"
OUTPUT_PERSISTENCE_FAILURE_MESSAGE = "生成结果保存失败"


@dataclass(frozen=True, slots=True)
class PlannedProduct:
    product: ProductMaterialGroup
    product_sources: tuple[MaterialGroupAsset, ...]
    style_references: tuple[MaterialGroupAsset, ...]
    template_groups: tuple[TemplateGroup, ...]


@dataclass(frozen=True, slots=True)
class GenerationExecutionInput:
    asset_id: UUID
    original_filename: str
    content_type: str
    storage_key: str


@dataclass(frozen=True, slots=True)
class GenerationExecution:
    generation_item_id: UUID
    generation_job_id: UUID
    attempt_count: int
    team_id: UUID
    created_by_user_id: UUID
    mode: GenerationMode
    final_prompt: str
    output_role: OutputRole
    output_format: OutputFormat
    size: GenerationSize
    input_assets: tuple[GenerationExecutionInput, ...]
    external_task_id: str | None
    provider_task_create_required: bool


def generation_counts(items: Sequence[GenerationItem]) -> GenerationCounts:
    statuses = [item.status for item in items]
    return GenerationCounts(
        total_count=len(statuses),
        pending_count=statuses.count(GenerationItemStatus.PENDING.value),
        running_count=statuses.count(GenerationItemStatus.RUNNING.value),
        success_count=statuses.count(GenerationItemStatus.SUCCESS.value),
        failed_count=statuses.count(GenerationItemStatus.FAILED.value),
    )


def derive_generation_job_status(items: Sequence[GenerationItem]) -> GenerationJobStatus:
    counts = generation_counts(items)
    if counts.total_count == 0:
        raise ValueError("GenerationJob must contain at least one item")
    if counts.pending_count == counts.total_count:
        return GenerationJobStatus.PENDING
    if counts.success_count == counts.total_count:
        return GenerationJobStatus.SUCCESS
    if counts.failed_count == counts.total_count:
        return GenerationJobStatus.FAILED
    if counts.success_count + counts.failed_count == counts.total_count:
        return GenerationJobStatus.PARTIAL_FAILED
    return GenerationJobStatus.RUNNING


def generation_input_summary(job: GenerationJob) -> GenerationInputSummary:
    ordered_items = sorted(
        job.items,
        key=lambda item: (item.position, str(item.generation_item_id)),
    )
    if job.work_mode == GenerationWorkMode.INSTANT.value:
        seen_assets: set[UUID] = set()
        primary_name: str | None = None
        for item in ordered_items:
            for link in sorted(
                item.input_assets,
                key=lambda candidate: (
                    candidate.position,
                    str(candidate.asset_id),
                ),
            ):
                if link.input_role != GenerationInputRole.PRODUCT_SOURCE.value:
                    continue
                if primary_name is None:
                    primary_name = link.asset.original_filename
                seen_assets.add(link.asset_id)
        return GenerationInputSummary(
            count=len(seen_assets),
            primary_name=primary_name,
        )

    products: dict[int, str | None] = {}
    for item in ordered_items:
        if item.source_product_position is None:
            continue
        products.setdefault(
            item.source_product_position,
            item.product_name_snapshot,
        )
    return GenerationInputSummary(
        count=len(products),
        primary_name=next(iter(products.values())) if len(products) == 1 else None,
    )


class GenerationService:
    def __init__(
        self,
        session: Session,
        *,
        generation_repository: GenerationRepository | None = None,
        template_repository: TemplateRepository | None = None,
        material_group_repository: ProductMaterialGroupRepository | None = None,
        asset_service: AssetService | None = None,
    ) -> None:
        self.session = session
        self.generation_repository = generation_repository or GenerationRepository(
            session,
        )
        self.template_repository = template_repository or TemplateRepository(session)
        self.material_group_repository = (
            material_group_repository or ProductMaterialGroupRepository(session)
        )
        self.asset_service = asset_service or AssetService(session)

    def submit(
        self,
        actor: ActorContext,
        data: GenerationSubmit,
    ) -> GenerationJob:
        fingerprint = self._submission_fingerprint(data)
        existing = self.generation_repository.get_by_submission(
            team_id=actor.team_id,
            created_by_user_id=actor.user_id,
            submission_key=data.submission_key,
        )
        if existing is not None:
            return self._resolve_existing_submission(existing, fingerprint)

        try:
            if isinstance(data, InstantGenerationSubmit):
                items = self._plan_instant(actor, data)
            else:
                items = self._plan_batch(actor, data)
            job = GenerationJob(
                generation_job_id=items[0].generation_job_id,
                team_id=actor.team_id,
                created_by_user_id=actor.user_id,
                created_by_display_name=actor.user_display_name,
                work_mode=data.work_mode.value,
                mode=data.mode.value,
                status=GenerationJobStatus.PENDING.value,
                submission_key=data.submission_key,
                submission_fingerprint=fingerprint,
                items=items,
            )
            self.generation_repository.add_job(job)
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raced = self.generation_repository.get_by_submission(
                team_id=actor.team_id,
                created_by_user_id=actor.user_id,
                submission_key=data.submission_key,
            )
            if raced is None:
                raise
            return self._resolve_existing_submission(raced, fingerprint)
        except Exception:
            self.session.rollback()
            raise
        return self.get(actor, job.generation_job_id)

    def list(
        self,
        *,
        actor: ActorContext,
        page: int,
        page_size: int,
        work_mode: GenerationWorkMode | None,
        mode: GenerationMode | None,
        status: GenerationJobStatus | None,
    ) -> tuple[
        list[tuple[GenerationJob, GenerationCounts, GenerationInputSummary]],
        int,
    ]:
        jobs = self.generation_repository.list_jobs(
            actor=actor,
            offset=(page - 1) * page_size,
            limit=page_size,
            work_mode=work_mode,
            mode=mode,
            status=status,
        )
        job_ids = [job.generation_job_id for job in jobs]
        counts = self.generation_repository.counts_by_job_ids(job_ids)
        input_summaries = self.generation_repository.input_summaries_by_job_ids(job_ids)
        return (
            [
                (
                    job,
                    counts.get(job.generation_job_id, GenerationCounts()),
                    input_summaries.get(
                        job.generation_job_id,
                        GenerationInputSummary(),
                    ),
                )
                for job in jobs
            ],
            self.generation_repository.count_jobs(
                actor=actor,
                work_mode=work_mode,
                mode=mode,
                status=status,
            ),
        )

    def get(self, actor: ActorContext, generation_job_id: UUID) -> GenerationJob:
        job = self.generation_repository.get_job_for_actor(
            actor=actor,
            generation_job_id=generation_job_id,
        )
        if job is None:
            raise GenerationJobNotFoundError()
        return job

    def retry_failed_items(
        self,
        actor: ActorContext,
        generation_job_id: UUID,
        data: GenerationRetryRequest,
    ) -> GenerationJob:
        try:
            job = self.generation_repository.get_job_for_write(
                actor=actor,
                generation_job_id=generation_job_id,
            )
            if job is None:
                raise GenerationJobNotFoundError()
            requested = {item.item_id: item for item in data.items}
            locked_items = self.generation_repository.lock_items_for_retry(
                generation_job_id=generation_job_id,
                item_ids=list(requested),
            )
            if len(locked_items) != len(requested):
                raise GenerationItemNotFoundError()

            actionable: list[GenerationItem] = []
            for item in locked_items:
                expected = requested[item.generation_item_id].expected_attempt_count
                if item.attempt_count > expected:
                    continue
                if (
                    item.attempt_count < expected
                    or item.status != GenerationItemStatus.FAILED.value
                ):
                    raise GenerationRetryConflictError()
                if (
                    item.last_failure_code
                    == ProviderCreateOutcomeUnknownError.code
                ):
                    raise ProviderCreateOutcomeUnknownError()
                actionable.append(item)

            if not actionable:
                self.session.rollback()
                return self.get(actor, generation_job_id)

            if job.work_mode == GenerationWorkMode.BATCH.value:
                source_group_ids = {
                    item.source_product_material_group_id
                    for item in actionable
                    if item.source_product_material_group_id is not None
                }
                existing_group_ids = (
                    self.generation_repository.material_groups_exist_for_team(
                        team_id=job.team_id,
                        material_group_ids=list(source_group_ids),
                    )
                )
                if any(
                    item.source_product_material_group_id is None
                    for item in actionable
                ) or existing_group_ids != source_group_ids:
                    raise ProductMaterialGroupNotFoundError()

            for item in actionable:
                item.status = GenerationItemStatus.PENDING.value
                item.attempt_count += 1
                item.started_at = None
                item.finished_at = None
            self._sync_job_status(job)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return self.get(actor, generation_job_id)

    def archive_instant_item(
        self,
        actor: ActorContext,
        generation_job_id: UUID,
        generation_item_id: UUID,
        data: GenerationItemArchiveRequest,
    ) -> GenerationJob:
        try:
            job = self.generation_repository.get_job_for_write(
                actor=actor,
                generation_job_id=generation_job_id,
            )
            if job is None:
                raise GenerationJobNotFoundError()
            item = self.generation_repository.get_item_for_job_for_update(
                generation_job_id=generation_job_id,
                generation_item_id=generation_item_id,
            )
            if item is None:
                raise GenerationItemNotFoundError()
            if (
                job.work_mode != GenerationWorkMode.INSTANT.value
                or item.status != GenerationItemStatus.SUCCESS.value
                or item.output_asset_id is None
            ):
                raise GenerationItemStateConflictError()
            if item.archived_at is not None:
                if item.archived_material_group_id == data.material_group_id:
                    self.session.rollback()
                    return self.get(actor, generation_job_id)
                raise GenerationItemStateConflictError()

            archive_group = self.material_group_repository.get_group_for_write(
                actor=actor,
                material_group_id=data.material_group_id,
            )
            if archive_group is None or archive_group.team_id != job.team_id:
                raise ProductMaterialGroupNotFoundError()
            self.generation_repository.add_material_group_asset(
                archive_group,
                MaterialGroupAsset(
                    material_group_id=archive_group.material_group_id,
                    asset_id=item.output_asset_id,
                    role=MaterialRole.AI_OUTPUT.value,
                ),
            )
            item.archived_material_group_id = archive_group.material_group_id
            item.archived_material_group_name_snapshot = archive_group.name
            item.archived_at = datetime.now(UTC)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return self.get(actor, generation_job_id)

    def mark_item_running(self, generation_item_id: UUID) -> GenerationJob:
        try:
            item = self._execution_item(generation_item_id)
            if item.status != GenerationItemStatus.PENDING.value:
                raise GenerationItemStateConflictError()
            now = datetime.now(UTC)
            item.status = GenerationItemStatus.RUNNING.value
            item.started_at = now
            item.finished_at = None
            if item.job.started_at is None:
                item.job.started_at = now
            self._sync_job_status(item.job, now=now)
            self.session.commit()
            job_id = item.generation_job_id
        except Exception:
            self.session.rollback()
            raise
        return self._get_execution_job(job_id)

    def prepare_next_provider_execution(
        self,
        *,
        provider_code: str,
    ) -> GenerationExecution | None:
        normalized_provider = provider_code.strip()
        if not normalized_provider or len(normalized_provider) > 32:
            raise ValueError("provider_code must contain 1 to 32 characters")
        generation_item_id = (
            self.generation_repository.next_item_id_for_provider_execution()
        )
        if generation_item_id is None:
            self.session.rollback()
            return None
        try:
            item = self._execution_item(generation_item_id)
            if item.status not in {
                GenerationItemStatus.PENDING.value,
                GenerationItemStatus.RUNNING.value,
            }:
                self.session.rollback()
                return None
            now = datetime.now(UTC)
            if item.status == GenerationItemStatus.PENDING.value:
                item.status = GenerationItemStatus.RUNNING.value
                item.started_at = now
                item.finished_at = None
                if item.job.started_at is None:
                    item.job.started_at = now
                self._sync_job_status(item.job, now=now)

            execution = item.provider_execution
            provider_task_create_required = False
            if execution is None:
                execution = GenerationProviderExecution(
                    generation_item_id=item.generation_item_id,
                    provider_code=normalized_provider,
                    external_task_id=None,
                    attempt_count=item.attempt_count,
                )
                item.provider_execution = execution
                self.generation_repository.add_provider_execution(execution)
                provider_task_create_required = True
            elif execution.attempt_count != item.attempt_count:
                execution.provider_code = normalized_provider
                execution.external_task_id = None
                execution.attempt_count = item.attempt_count
                provider_task_create_required = True
            elif execution.provider_code != normalized_provider:
                raise GenerationItemStateConflictError()
            snapshot = self._execution_snapshot(
                item,
                external_task_id=execution.external_task_id,
                provider_task_create_required=provider_task_create_required,
            )
            self.session.commit()
            return snapshot
        except Exception:
            self.session.rollback()
            raise

    def record_provider_execution(
        self,
        generation_item_id: UUID,
        *,
        expected_attempt_count: int,
        provider_code: str,
        external_task_id: str,
    ) -> None:
        normalized_provider = provider_code.strip()
        normalized_task_id = external_task_id.strip()
        if not normalized_provider or len(normalized_provider) > 32:
            raise ValueError("provider_code must contain 1 to 32 characters")
        if not normalized_task_id or len(normalized_task_id) > 255:
            raise ValueError("external_task_id must contain 1 to 255 characters")
        try:
            item = self._execution_item(generation_item_id)
            self._assert_current_attempt(item, expected_attempt_count)
            if item.status != GenerationItemStatus.RUNNING.value:
                raise GenerationItemStateConflictError()
            execution = item.provider_execution
            if execution is None:
                raise GenerationItemStateConflictError()
            if (
                execution.provider_code != normalized_provider
                or execution.attempt_count != expected_attempt_count
            ):
                raise GenerationItemStateConflictError()
            if execution.external_task_id is not None:
                if execution.external_task_id == normalized_task_id:
                    self.session.rollback()
                    return
                raise GenerationItemStateConflictError()
            execution.external_task_id = normalized_task_id
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def fail_item(
        self,
        generation_item_id: UUID,
        *,
        failure_code: str,
        failure_message: str,
        expected_attempt_count: int | None = None,
    ) -> GenerationJob:
        normalized_code = failure_code.strip()
        normalized_message = failure_message.strip()
        if not normalized_code or len(normalized_code) > 64:
            raise ValueError("failure_code must contain 1 to 64 characters")
        if not normalized_message or len(normalized_message) > 2000:
            raise ValueError("failure_message must contain 1 to 2000 characters")
        try:
            item = self._execution_item(generation_item_id)
            self._assert_current_attempt(item, expected_attempt_count)
            if item.status not in {
                GenerationItemStatus.PENDING.value,
                GenerationItemStatus.RUNNING.value,
            }:
                raise GenerationItemStateConflictError()
            now = datetime.now(UTC)
            item.status = GenerationItemStatus.FAILED.value
            item.last_failure_code = normalized_code
            item.last_failure_message = normalized_message
            item.last_failed_at = now
            item.finished_at = now
            if item.job.started_at is None:
                item.job.started_at = now
            self._sync_job_status(item.job, now=now)
            self.session.commit()
            job_id = item.generation_job_id
        except Exception:
            self.session.rollback()
            raise
        return self._get_execution_job(job_id)

    def complete_item(
        self,
        generation_item_id: UUID,
        *,
        original_filename: str | None,
        content_type: str | None,
        stream: BinaryIO,
        expected_attempt_count: int | None = None,
    ) -> GenerationJob:
        try:
            item = self._execution_item(generation_item_id)
            self._assert_current_attempt(item, expected_attempt_count)
            if item.status == GenerationItemStatus.SUCCESS.value:
                if item.output_asset_id is None:
                    raise GenerationItemStateConflictError()
                self.session.rollback()
                return self._get_execution_job(item.generation_job_id)
            if item.status not in {
                GenerationItemStatus.PENDING.value,
                GenerationItemStatus.RUNNING.value,
            }:
                raise GenerationItemStateConflictError()
            job_id = item.generation_job_id
        except Exception:
            self.session.rollback()
            raise

        try:
            archive_group: ProductMaterialGroup | None = None
            if item.job.work_mode == GenerationWorkMode.BATCH.value:
                if item.source_product_material_group_id is None:
                    raise ProductMaterialGroupNotFoundError()
                archive_group = self.generation_repository.get_material_group_for_output(
                    team_id=item.job.team_id,
                    material_group_id=item.source_product_material_group_id,
                )
                if archive_group is None:
                    raise ProductMaterialGroupNotFoundError()

            with self.asset_service.stage_for_transaction(
                original_filename=original_filename,
                content_type=content_type,
                stream=stream,
                media_type=AssetMediaType.IMAGE,
                source_type=AssetSourceType.AI_GENERATED,
                ownership=AssetOwnership(
                    team_id=item.job.team_id,
                    created_by_user_id=item.job.created_by_user_id,
                ),
            ) as asset:
                now = datetime.now(UTC)
                item.output_asset_id = asset.asset_id
                item.output_asset = asset
                if archive_group is not None:
                    self.generation_repository.add_material_group_asset(
                        archive_group,
                        MaterialGroupAsset(
                            material_group_id=archive_group.material_group_id,
                            asset_id=asset.asset_id,
                            role=MaterialRole.AI_OUTPUT.value,
                        ),
                    )
                    item.archived_material_group_id = archive_group.material_group_id
                    item.archived_material_group_name_snapshot = archive_group.name
                    item.archived_at = now
                item.status = GenerationItemStatus.SUCCESS.value
                item.finished_at = now
                if item.job.started_at is None:
                    item.job.started_at = now
                self._sync_job_status(item.job, now=now)
                self.session.commit()
        except Exception:
            self.session.rollback()
            self.fail_item(
                generation_item_id,
                failure_code=OUTPUT_PERSISTENCE_FAILURE_CODE,
                failure_message=OUTPUT_PERSISTENCE_FAILURE_MESSAGE,
                expected_attempt_count=expected_attempt_count,
            )
            raise
        return self._get_execution_job(job_id)

    def _plan_instant(
        self,
        actor: ActorContext,
        data: InstantGenerationSubmit,
    ) -> list[GenerationItem]:
        if (
            len(data.product_asset_ids) + len(data.reference_asset_ids)
            > MAX_GENERATION_ITEM_INPUT_ASSETS
        ):
            raise GenerationPlanTooLargeError()
        assets = self._locked_assets(
            actor,
            [*data.product_asset_ids, *data.reference_asset_ids],
        )
        source_prompt: PromptTemplate | None = None
        source_group: TemplateGroup | None = None
        if data.prompt_template_id is not None:
            source_prompt = self.template_repository.get_prompt_source_for_generation(
                actor=actor,
                team_id=actor.team_id,
                prompt_template_id=data.prompt_template_id,
            )
            if source_prompt is None:
                raise PromptTemplateNotFoundError()
            source_group = source_prompt.template_group
            if (
                not source_prompt.enabled
                or not source_group.enabled
                or source_group.mode != data.mode.value
            ):
                raise PromptTemplateNotFoundError()

        job_id = generate_id()
        items: list[GenerationItem] = []
        for position in range(data.count):
            item_id = generate_id()
            item = GenerationItem(
                generation_item_id=item_id,
                generation_job_id=job_id,
                position=position,
                status=GenerationItemStatus.PENDING.value,
                final_prompt=data.prompt,
                output_role=OutputRole.MAIN_IMAGE.value,
                output_format=data.output_format.value,
                size=data.size.value,
                output_ordinal=position,
                source_template_group_id=(
                    source_group.template_group_id if source_group else None
                ),
                source_prompt_template_id=(
                    source_prompt.prompt_template_id if source_prompt else None
                ),
                template_group_name_snapshot=source_group.name if source_group else None,
                prompt_template_name_snapshot=(
                    source_prompt.name if source_prompt else None
                ),
                attempt_count=1,
            )
            item.input_assets = self._input_links(
                item_id,
                data.product_asset_ids,
                data.reference_asset_ids,
                assets,
            )
            items.append(item)
        for item in items:
            item.generation_job_id = job_id
        return items

    def _plan_batch(
        self,
        actor: ActorContext,
        data: BatchGenerationSubmit,
    ) -> list[GenerationItem]:
        selected_product_ids: Sequence[UUID] | None = None
        if data.product_scope is BatchProductScope.SELECTED:
            selected_product_ids = data.selected_product_ids
        products = self.material_group_repository.list_groups_for_generation(
            actor=actor,
            team_id=actor.team_id,
            material_group_ids=selected_product_ids,
            limit=MAX_GENERATION_SELECTION_IDS + 1,
        )
        if len(products) > MAX_GENERATION_SELECTION_IDS:
            raise GenerationPlanTooLargeError()
        if selected_product_ids is not None:
            products_by_id = {product.material_group_id: product for product in products}
            if set(products_by_id) != set(selected_product_ids):
                raise ProductMaterialGroupNotFoundError()
            products = [products_by_id[product_id] for product_id in selected_product_ids]

        configured_group_ids: list[UUID] = []
        if data.template_source is BatchTemplateSource.PRODUCT_CONFIGURED:
            for product in products:
                configured_group_ids.extend(
                    binding.template_group_id
                    for binding in product.template_bindings
                    if binding.generation_mode == data.mode.value
                )
            template_group_ids = list(dict.fromkeys(configured_group_ids))
        else:
            template_group_ids = data.selected_template_group_ids
        if len(template_group_ids) > MAX_GENERATION_SELECTION_IDS:
            raise GenerationPlanTooLargeError()
        template_groups = self.template_repository.list_groups_for_generation(
            actor=actor,
            team_id=actor.team_id,
            template_group_ids=template_group_ids,
        )
        groups_by_id = {
            group.template_group_id: group
            for group in template_groups
            if group.mode == data.mode.value
        }
        if data.template_source is BatchTemplateSource.CURRENT_SELECTION and (
            set(groups_by_id) != set(template_group_ids)
        ):
            raise TemplateBindingInvalidError()

        planned_products: list[PlannedProduct] = []
        for product in products:
            if not product.enabled or not self._mode_enabled(product, data.mode):
                continue
            product_sources = self._material_assets(
                product,
                MaterialRole.PRODUCT_SOURCE,
            )
            if not product_sources:
                continue
            style_references = self._material_assets(
                product,
                MaterialRole.STYLE_REFERENCE,
            )
            if data.mode is GenerationMode.STYLE_REPLICATION and not style_references:
                continue
            if data.mode is GenerationMode.NORMAL_GENERATION:
                style_references = ()

            if data.template_source is BatchTemplateSource.CURRENT_SELECTION:
                group_ids = data.selected_template_group_ids
            else:
                group_ids = [
                    binding.template_group_id
                    for binding in sorted(
                        product.template_bindings,
                        key=lambda item: (item.position, str(item.template_group_id)),
                    )
                    if binding.generation_mode == data.mode.value
                ]
            selected_groups = tuple(
                group
                for group_id in group_ids
                if (group := groups_by_id.get(group_id)) is not None
                and group.enabled
                and self._enabled_prompts(group, data.output_range)
            )
            if not selected_groups:
                continue
            input_count = len(product_sources) + (
                1 if data.mode is GenerationMode.STYLE_REPLICATION else 0
            )
            if input_count > MAX_GENERATION_ITEM_INPUT_ASSETS:
                raise GenerationPlanTooLargeError()
            planned_products.append(
                PlannedProduct(
                    product=product,
                    product_sources=product_sources,
                    style_references=style_references,
                    template_groups=selected_groups,
                ),
            )

        requested_asset_ids = list(
            dict.fromkeys(
                link.asset_id
                for plan in planned_products
                for link in (*plan.product_sources, *plan.style_references)
            ),
        )
        if len(requested_asset_ids) > MAX_GENERATION_INPUT_ASSETS:
            raise GenerationPlanTooLargeError()
        planned_item_count = 0
        for plan in planned_products:
            style_reference_count = (
                len(plan.style_references)
                if data.mode is GenerationMode.STYLE_REPLICATION
                else 1
            )
            for group in plan.template_groups:
                planned_item_count += style_reference_count * sum(
                    prompt.count
                    for prompt in self._enabled_prompts(group, data.output_range)
                )
                if planned_item_count > MAX_GENERATION_ITEMS:
                    raise GenerationPlanTooLargeError()
        assets = self._locked_assets(actor, requested_asset_ids)
        items: list[GenerationItem] = []
        job_id = generate_id()
        for product_position, plan in enumerate(planned_products):
            product_source_ids = [link.asset_id for link in plan.product_sources]
            style_reference_positions = {
                link.asset_id: position
                for position, link in enumerate(plan.style_references)
            }
            style_reference_ids: list[UUID | None]
            if data.mode is GenerationMode.STYLE_REPLICATION:
                style_reference_ids = [
                    link.asset_id for link in plan.style_references
                ]
            else:
                style_reference_ids = [None]
            for template_group_position, group in enumerate(plan.template_groups):
                for prompt_template_position, prompt in enumerate(
                    self._enabled_prompts(group, data.output_range),
                ):
                    for style_reference_id in style_reference_ids:
                        for output_ordinal in range(prompt.count):
                            item_id = generate_id()
                            reference_ids = (
                                [style_reference_id]
                                if style_reference_id is not None
                                else []
                            )
                            item = GenerationItem(
                                generation_item_id=item_id,
                                generation_job_id=job_id,
                                position=len(items),
                                status=GenerationItemStatus.PENDING.value,
                                final_prompt=prompt.prompt,
                                output_role=prompt.output_role,
                                output_format=prompt.output_format,
                                size=prompt.size,
                                source_product_position=product_position,
                                source_template_group_position=(
                                    template_group_position
                                ),
                                source_prompt_template_position=(
                                    prompt_template_position
                                ),
                                output_ordinal=output_ordinal,
                                source_product_material_group_id=(
                                    plan.product.material_group_id
                                ),
                                source_template_group_id=group.template_group_id,
                                source_prompt_template_id=prompt.prompt_template_id,
                                product_name_snapshot=plan.product.name,
                                template_group_name_snapshot=group.name,
                                prompt_template_name_snapshot=prompt.name,
                                attempt_count=1,
                            )
                            item.input_assets = self._input_links(
                                item_id,
                                product_source_ids,
                                reference_ids,
                                assets,
                                reference_position_by_id=(
                                    style_reference_positions
                                ),
                            )
                            items.append(item)
        if not items:
            raise GenerationPlanInvalidError()
        for item in items:
            item.generation_job_id = job_id
        return items

    def _locked_assets(
        self,
        actor: ActorContext,
        asset_ids: Sequence[UUID],
    ) -> dict[UUID, Asset]:
        unique_ids = list(dict.fromkeys(asset_ids))
        assets = self.asset_service.list_accessible_by_ids_for_update(
            actor,
            unique_ids,
        )
        by_id = {asset.asset_id: asset for asset in assets}
        if set(by_id) != set(unique_ids) or any(
            asset.team_id != actor.team_id
            or asset.media_type != AssetMediaType.IMAGE.value
            for asset in assets
        ):
            raise AssetNotFoundError()
        return by_id

    @staticmethod
    def _input_links(
        item_id: UUID,
        product_asset_ids: Sequence[UUID],
        reference_asset_ids: Sequence[UUID],
        assets: dict[UUID, Asset],
        reference_position_by_id: dict[UUID, int] | None = None,
    ) -> list[GenerationItemAsset]:
        links = [
            GenerationItemAsset(
                generation_item_id=item_id,
                input_role=GenerationInputRole.PRODUCT_SOURCE.value,
                position=position,
                asset_id=asset_id,
                asset=assets[asset_id],
            )
            for position, asset_id in enumerate(product_asset_ids)
        ]
        links.extend(
            GenerationItemAsset(
                generation_item_id=item_id,
                input_role=GenerationInputRole.STYLE_REFERENCE.value,
                position=(
                    reference_position_by_id.get(asset_id, position)
                    if reference_position_by_id is not None
                    else position
                ),
                asset_id=asset_id,
                asset=assets[asset_id],
            )
            for position, asset_id in enumerate(reference_asset_ids)
        )
        return links

    @staticmethod
    def _material_assets(
        product: ProductMaterialGroup,
        role: MaterialRole,
    ) -> tuple[MaterialGroupAsset, ...]:
        return tuple(
            sorted(
                (link for link in product.asset_links if link.role == role.value),
                key=lambda link: (link.created_at, str(link.asset_id)),
            ),
        )

    @staticmethod
    def _enabled_prompts(
        group: TemplateGroup,
        output_range: GenerationOutputRange,
    ) -> tuple[PromptTemplate, ...]:
        return tuple(
            prompt
            for prompt in sorted(
                group.prompt_templates,
                key=lambda item: (item.sort_order, str(item.prompt_template_id)),
            )
            if prompt.enabled
            and (
                output_range is GenerationOutputRange.ALL
                or prompt.output_role == output_range.value
            )
        )

    @staticmethod
    def _mode_enabled(
        product: ProductMaterialGroup,
        mode: GenerationMode,
    ) -> bool:
        if mode is GenerationMode.NORMAL_GENERATION:
            return product.normal_generation_enabled
        return product.style_replication_enabled

    @staticmethod
    def _submission_fingerprint(data: GenerationSubmit) -> str:
        normalized = data.model_dump(mode="json", exclude={"submission_key"})
        encoded = json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _resolve_existing_submission(
        job: GenerationJob,
        fingerprint: str,
    ) -> GenerationJob:
        if job.submission_fingerprint != fingerprint:
            raise GenerationSubmissionConflictError()
        return job

    def _execution_item(self, generation_item_id: UUID) -> GenerationItem:
        item = self.generation_repository.get_item_for_execution(
            generation_item_id,
        )
        if item is None:
            raise GenerationItemNotFoundError()
        return item

    @staticmethod
    def _assert_current_attempt(
        item: GenerationItem,
        expected_attempt_count: int | None,
    ) -> None:
        if (
            expected_attempt_count is not None
            and item.attempt_count != expected_attempt_count
        ):
            raise GenerationItemStateConflictError()

    @staticmethod
    def _execution_snapshot(
        item: GenerationItem,
        *,
        external_task_id: str | None,
        provider_task_create_required: bool,
    ) -> GenerationExecution:
        role_order = {
            GenerationInputRole.PRODUCT_SOURCE.value: 0,
            GenerationInputRole.STYLE_REFERENCE.value: 1,
        }
        links = sorted(
            item.input_assets,
            key=lambda link: (
                role_order[link.input_role],
                link.position,
                str(link.asset_id),
            ),
        )
        return GenerationExecution(
            generation_item_id=item.generation_item_id,
            generation_job_id=item.generation_job_id,
            attempt_count=item.attempt_count,
            team_id=item.job.team_id,
            created_by_user_id=item.job.created_by_user_id,
            mode=GenerationMode(item.job.mode),
            final_prompt=item.final_prompt,
            output_role=OutputRole(item.output_role),
            output_format=OutputFormat(item.output_format),
            size=GenerationSize(item.size),
            input_assets=tuple(
                GenerationExecutionInput(
                    asset_id=link.asset_id,
                    original_filename=link.asset.original_filename,
                    content_type=link.asset.content_type,
                    storage_key=link.asset.storage_key,
                )
                for link in links
            ),
            external_task_id=external_task_id,
            provider_task_create_required=provider_task_create_required,
        )

    def _get_execution_job(self, generation_job_id: UUID) -> GenerationJob:
        job = self.generation_repository.get_job_by_id(generation_job_id)
        if job is None:
            raise GenerationJobNotFoundError()
        return job

    @staticmethod
    def _sync_job_status(
        job: GenerationJob,
        *,
        now: datetime | None = None,
    ) -> None:
        resolved_now = now or datetime.now(UTC)
        status = derive_generation_job_status(job.items)
        job.status = status.value
        if status in {
            GenerationJobStatus.SUCCESS,
            GenerationJobStatus.PARTIAL_FAILED,
            GenerationJobStatus.FAILED,
        }:
            job.finished_at = resolved_now
        else:
            job.finished_at = None
