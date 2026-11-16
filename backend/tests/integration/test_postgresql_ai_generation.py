from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, delete, inspect, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_database_engine
from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.access.models import Team
from app.modules.ai_workbench.enums import (
    BatchProductScope,
    BatchTemplateSource,
    GenerationItemStatus,
    GenerationJobStatus,
    GenerationMode,
    GenerationWorkMode,
    MaterialRole,
    OutputFormat,
    OutputRole,
)
from app.modules.ai_workbench.exceptions import (
    GenerationItemStateConflictError,
    GenerationJobNotFoundError,
    GenerationRetryConflictError,
    GenerationSubmissionConflictError,
    ProductMaterialGroupHasActiveGenerationJobsError,
    ProductMaterialGroupNotFoundError,
)
from app.modules.ai_workbench.generation_service import GenerationService
from app.modules.ai_workbench.models import (
    GenerationItem,
    GenerationItemAsset,
    GenerationJob,
    MaterialGroupAsset,
    MaterialGroupTemplateBinding,
    ProductMaterialGroup,
    PromptTemplate,
    TemplateGroup,
)
from app.modules.ai_workbench.repository import GenerationRepository
from app.modules.ai_workbench.schemas import (
    BatchGenerationSubmit,
    GenerationItemArchiveRequest,
    GenerationRetryRequest,
    InstantGenerationSubmit,
    MaterialGroupAssetAttach,
    ProductMaterialGroupCreate,
    PromptTemplateCreate,
    TemplateBindingReplace,
    TemplateGroupCreate,
)
from app.modules.ai_workbench.service import AiWorkbenchService
from app.modules.assets.enums import AssetMediaType, AssetSourceType
from app.modules.assets.exceptions import AssetInUseError, AssetNotFoundError
from app.modules.assets.models import Asset
from app.modules.assets.service import AssetService
from app.modules.assets.storage import LocalAssetStorage
from app.modules.users.models import User


pytestmark = pytest.mark.integration
FEATURE_DATABASE = "control_center_feat_ai_generation"
MODEL_ID = UUID("13b4f558-cd56-4f11-99fc-c64275e14031")
GENERATION_TABLES = {
    "generation_jobs",
    "generation_items",
    "generation_item_assets",
}


@pytest.fixture(scope="module")
def generation_postgresql_engine() -> Engine:
    engine = get_database_engine()
    if not engine.url.drivername.startswith("postgresql"):
        pytest.fail("AI generation integration tests require PostgreSQL")
    if engine.url.database != FEATURE_DATABASE:
        pytest.fail(f"AI generation tests only run against {FEATURE_DATABASE}")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == FEATURE_DATABASE
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "20260903_0027"
        )
    assert GENERATION_TABLES <= set(inspect(engine).get_table_names())
    return engine


def actor(
    *,
    user_id: UUID,
    team_id: UUID,
    scope: DataScope,
) -> ActorContext:
    return ActorContext(
        user_id=user_id,
        user_display_name=f"stage-2a1 Generation {scope.value}",
        team_id=team_id,
        membership_id=uuid4(),
        role_code="member",
        data_scope=scope,
    )


def asset(
    *,
    asset_id: UUID,
    team_id: UUID,
    created_by_user_id: UUID,
    filename: str,
) -> Asset:
    return Asset(
        asset_id=asset_id,
        team_id=team_id,
        created_by_user_id=created_by_user_id,
        original_filename=filename,
        storage_key=f"stage-2a1-generation/{asset_id}.png",
        media_type=AssetMediaType.IMAGE.value,
        source_type=AssetSourceType.UPLOAD.value,
        content_type="image/png",
        size_bytes=64,
        sha256="a" * 64,
    )


def instant_submit(
    asset_id: UUID,
    *,
    key: str,
    prompt: str = "完整商品主图提示词",
    count: int = 2,
) -> InstantGenerationSubmit:
    return InstantGenerationSubmit(
        work_mode=GenerationWorkMode.INSTANT,
        submission_key=key,
        model_id=MODEL_ID,
        mode=GenerationMode.NORMAL_GENERATION,
        product_asset_ids=[asset_id],
        prompt=prompt,
        output_format=OutputFormat.SINGLE,
        size="1:1",  # type: ignore[arg-type]
        count=count,
    )


def create_batch_source(
    service: AiWorkbenchService,
    current_actor: ActorContext,
    source_asset_id: UUID,
    *,
    name: str,
) -> tuple[ProductMaterialGroup, TemplateGroup]:
    material_group = service.create_product_material_group(
        current_actor,
        ProductMaterialGroupCreate(name=name),
    )
    service.attach_asset(
        current_actor,
        material_group.material_group_id,
        MaterialGroupAssetAttach(
            asset_id=source_asset_id,
            role=MaterialRole.PRODUCT_SOURCE,
        ),
    )
    template_group = service.create_template_group(
        current_actor,
        TemplateGroupCreate(
            name=f"{name} 模板",
            mode=GenerationMode.NORMAL_GENERATION,
        ),
    )
    service.create_prompt_template(
        current_actor,
        template_group.template_group_id,
        PromptTemplateCreate(
            name="主图",
            output_role=OutputRole.MAIN_IMAGE,
            output_format=OutputFormat.SINGLE,
            size="1:1",  # type: ignore[arg-type]
            count=1,
            variables=[],
            prompt="批量完整提示词",
        ),
    )
    material_group = service.replace_template_bindings(
        current_actor,
        material_group.material_group_id,
        GenerationMode.NORMAL_GENERATION,
        TemplateBindingReplace(
            template_group_ids=[template_group.template_group_id],
        ),
    )
    return material_group, template_group


def batch_submit(material_group_id: UUID, *, key: str) -> BatchGenerationSubmit:
    return BatchGenerationSubmit(
        work_mode=GenerationWorkMode.BATCH,
        submission_key=key,
        model_id=MODEL_ID,
        mode=GenerationMode.NORMAL_GENERATION,
        product_scope=BatchProductScope.SELECTED,
        selected_product_ids=[material_group_id],
        template_source=BatchTemplateSource.PRODUCT_CONFIGURED,
    )


def retry_request(item: GenerationItem) -> GenerationRetryRequest:
    return GenerationRetryRequest.model_validate(
        {
            "items": [
                {
                    "item_id": str(item.generation_item_id),
                    "expected_attempt_count": item.attempt_count,
                },
            ],
        },
    )


def test_ai_generation_schema_constraints(
    generation_postgresql_engine: Engine,
) -> None:
    inspector = inspect(generation_postgresql_engine)
    assert GENERATION_TABLES <= set(inspector.get_table_names())
    assert {
        "source_product_position",
        "source_template_group_position",
        "source_prompt_template_position",
        "output_ordinal",
    } <= {
        column["name"] for column in inspector.get_columns("generation_items")
    }
    assert {
        "ck_generation_items_source_product_position_non_negative",
        "ck_generation_items_source_template_group_position_non_negative",
        "ck_generation_items_source_prompt_position_non_negative",
        "ck_generation_items_output_ordinal_non_negative",
    } <= {
        constraint["name"]
        for constraint in inspector.get_check_constraints("generation_items")
    }

    item_foreign_keys = {
        item["name"]: item for item in inspector.get_foreign_keys("generation_items")
    }
    assert item_foreign_keys["fk_generation_items_source_material_group"][
        "options"
    ]["ondelete"] == "SET NULL"
    assert item_foreign_keys["fk_generation_items_source_template_group"][
        "options"
    ]["ondelete"] == "SET NULL"
    assert item_foreign_keys["fk_generation_items_source_prompt_template"][
        "options"
    ]["ondelete"] == "SET NULL"
    assert item_foreign_keys["fk_generation_items_archived_material_group"][
        "options"
    ]["ondelete"] == "SET NULL"
    assert item_foreign_keys["fk_generation_items_output_asset"]["options"][
        "ondelete"
    ] == "RESTRICT"
    input_foreign_keys = {
        item["name"]: item
        for item in inspector.get_foreign_keys("generation_item_assets")
    }
    assert input_foreign_keys["fk_generation_item_assets_asset"]["options"][
        "ondelete"
    ] == "RESTRICT"
    assert {
        "ix_generation_jobs_team_created_job",
        "ix_generation_jobs_team_creator_created_job",
    } <= {item["name"] for item in inspector.get_indexes("generation_jobs")}


def test_instant_generation_idempotency_scope_status_retry_and_asset_ownership(
    generation_postgresql_engine: Engine,
    tmp_path: Path,
) -> None:
    team_a_id, team_b_id = uuid4(), uuid4()
    user_a_id, user_a2_id, user_b_id = uuid4(), uuid4(), uuid4()
    input_a_id, input_a2_id, input_b_id = uuid4(), uuid4(), uuid4()
    team_ids = {team_a_id, team_b_id}
    user_ids = {user_a_id, user_a2_id, user_b_id}
    input_asset_ids = {input_a_id, input_a2_id, input_b_id}

    try:
        with Session(generation_postgresql_engine, expire_on_commit=False) as session:
            session.add_all(
                [
                    Team(team_id=team_a_id, name="stage-2a1 Gen Team A", enabled=True),
                    Team(team_id=team_b_id, name="stage-2a1 Gen Team B", enabled=True),
                    User(user_id=user_a_id, display_name="stage-2a1 Gen A", enabled=True),
                    User(user_id=user_a2_id, display_name="stage-2a1 Gen A2", enabled=True),
                    User(user_id=user_b_id, display_name="stage-2a1 Gen B", enabled=True),
                ],
            )
            session.commit()
            session.add_all(
                [
                    asset(
                        asset_id=input_a_id,
                        team_id=team_a_id,
                        created_by_user_id=user_a_id,
                        filename="input-a.png",
                    ),
                    asset(
                        asset_id=input_a2_id,
                        team_id=team_a_id,
                        created_by_user_id=user_a2_id,
                        filename="input-a2.png",
                    ),
                    asset(
                        asset_id=input_b_id,
                        team_id=team_b_id,
                        created_by_user_id=user_b_id,
                        filename="input-b.png",
                    ),
                ],
            )
            session.commit()

            self_a = actor(
                user_id=user_a_id,
                team_id=team_a_id,
                scope=DataScope.SELF,
            )
            self_a2 = actor(
                user_id=user_a2_id,
                team_id=team_a_id,
                scope=DataScope.SELF,
            )
            team_b = actor(
                user_id=user_b_id,
                team_id=team_b_id,
                scope=DataScope.TEAM,
            )
            all_a = actor(
                user_id=user_a_id,
                team_id=team_a_id,
                scope=DataScope.ALL,
            )
            storage = LocalAssetStorage(tmp_path / "outputs", 1024)
            asset_service = AssetService(
                session,
                storage=storage,
                settings=Settings(asset_storage_dir=tmp_path / "unused"),
            )
            service = GenerationService(session, asset_service=asset_service)
            workbench_service = AiWorkbenchService(session)
            archive_group = workbench_service.create_product_material_group(
                self_a,
                ProductMaterialGroupCreate(name="stage-2a1 Instant Archive"),
            )
            other_archive_group = workbench_service.create_product_material_group(
                self_a,
                ProductMaterialGroupCreate(name="stage-2a1 Other Archive"),
            )
            cross_team_archive_group = workbench_service.create_product_material_group(
                team_b,
                ProductMaterialGroupCreate(name="stage-2a1 Cross Team Archive"),
            )
            job_a = service.submit(self_a, instant_submit(input_a_id, key="int-a"))
            assert job_a.status == GenerationJobStatus.PENDING.value
            assert len(job_a.items) == 2
            assert service.submit(
                self_a,
                instant_submit(input_a_id, key="int-a"),
            ).generation_job_id == job_a.generation_job_id
            with pytest.raises(GenerationSubmissionConflictError):
                service.submit(
                    self_a,
                    instant_submit(input_a_id, key="int-a", prompt="不同提示词"),
                )

            service.submit(self_a2, instant_submit(input_a2_id, key="int-a2"))
            job_b = service.submit(team_b, instant_submit(input_b_id, key="int-b"))
            self_jobs, self_total = service.list(
                actor=self_a,
                page=1,
                page_size=20,
                work_mode=None,
                mode=None,
                status=None,
            )
            assert self_total == 1
            assert self_jobs[0][0].generation_job_id == job_a.generation_job_id
            assert self_jobs[0][2].count == 1
            assert self_jobs[0][2].primary_name == "input-a.png"
            team_jobs, team_total = service.list(
                actor=actor(
                    user_id=user_a_id,
                    team_id=team_a_id,
                    scope=DataScope.TEAM,
                ),
                page=1,
                page_size=20,
                work_mode=None,
                mode=None,
                status=None,
            )
            assert team_total == 2
            assert len(team_jobs) == 2
            all_jobs, all_total = service.list(
                actor=all_a,
                page=1,
                page_size=20,
                work_mode=None,
                mode=None,
                status=None,
            )
            assert all_total == 3
            assert len(all_jobs) == 3
            with pytest.raises(AssetNotFoundError):
                service.submit(all_a, instant_submit(input_b_id, key="cross-team"))

            first, second = job_a.items
            service.mark_item_running(first.generation_item_id)
            job_a = service.complete_item(
                first.generation_item_id,
                original_filename="generated.png",
                content_type="image/png",
                stream=BytesIO(b"\x89PNG\r\n\x1a\nfirst"),
            )
            first = job_a.items[0]
            assert first.output_asset is not None
            assert first.output_asset.team_id == team_a_id
            assert first.output_asset.created_by_user_id == user_a_id
            assert first.output_asset.source_type == AssetSourceType.AI_GENERATED.value
            job_a = service.archive_instant_item(
                self_a,
                job_a.generation_job_id,
                first.generation_item_id,
                GenerationItemArchiveRequest(
                    material_group_id=archive_group.material_group_id,
                ),
            )
            first = job_a.items[0]
            assert first.archived_material_group_id == archive_group.material_group_id
            assert first.archived_material_group_name_snapshot == archive_group.name
            assert first.archived_at is not None
            assert session.scalar(
                select(MaterialGroupAsset).where(
                    MaterialGroupAsset.material_group_id
                    == archive_group.material_group_id,
                    MaterialGroupAsset.asset_id == first.output_asset_id,
                    MaterialGroupAsset.role == MaterialRole.AI_OUTPUT.value,
                ),
            ) is not None
            service.archive_instant_item(
                self_a,
                job_a.generation_job_id,
                first.generation_item_id,
                GenerationItemArchiveRequest(
                    material_group_id=archive_group.material_group_id,
                ),
            )
            with pytest.raises(GenerationItemStateConflictError):
                service.archive_instant_item(
                    self_a,
                    job_a.generation_job_id,
                    first.generation_item_id,
                    GenerationItemArchiveRequest(
                        material_group_id=other_archive_group.material_group_id,
                    ),
                )
            job_a = service.fail_item(
                second.generation_item_id,
                failure_code="SAFE_PROVIDER_FAILURE",
                failure_message="安全失败摘要",
            )
            assert job_a.status == GenerationJobStatus.PARTIAL_FAILED.value
            failed = job_a.items[1]
            first_retry = retry_request(failed)
            job_a = service.retry_failed_items(
                self_a,
                job_a.generation_job_id,
                first_retry,
            )
            assert job_a.status == GenerationJobStatus.RUNNING.value
            assert job_a.items[1].attempt_count == 2
            repeated = service.retry_failed_items(
                self_a,
                job_a.generation_job_id,
                first_retry,
            )
            assert repeated.items[1].attempt_count == 2
            with pytest.raises(GenerationRetryConflictError):
                service.retry_failed_items(
                    self_a,
                    job_a.generation_job_id,
                    retry_request(repeated.items[1]),
                )
            job_a = service.complete_item(
                second.generation_item_id,
                original_filename="generated-2.png",
                content_type="image/png",
                stream=BytesIO(b"\x89PNG\r\n\x1a\nsecond"),
            )
            assert job_a.status == GenerationJobStatus.SUCCESS.value
            assert job_a.items[1].last_failure_code == "SAFE_PROVIDER_FAILURE"
            assert job_a.items[1].attempt_count == 2
            with pytest.raises(ProductMaterialGroupNotFoundError):
                service.archive_instant_item(
                    all_a,
                    job_a.generation_job_id,
                    job_a.items[1].generation_item_id,
                    GenerationItemArchiveRequest(
                        material_group_id=(
                            cross_team_archive_group.material_group_id
                        ),
                    ),
                )
            assert job_a.items[1].archived_at is None
            failing_archive_service = GenerationService(
                session,
                generation_repository=FailingArchiveRepository(session),
                asset_service=asset_service,
            )
            with pytest.raises(RuntimeError, match="forced archive failure"):
                failing_archive_service.archive_instant_item(
                    self_a,
                    job_a.generation_job_id,
                    job_a.items[1].generation_item_id,
                    GenerationItemArchiveRequest(
                        material_group_id=other_archive_group.material_group_id,
                    ),
                )
            job_a = service.get(self_a, job_a.generation_job_id)
            assert job_a.items[1].status == GenerationItemStatus.SUCCESS.value
            assert job_a.items[1].archived_at is None
            assert session.scalar(
                select(MaterialGroupAsset).where(
                    MaterialGroupAsset.material_group_id
                    == other_archive_group.material_group_id,
                    MaterialGroupAsset.asset_id == job_a.items[1].output_asset_id,
                ),
            ) is None

            with pytest.raises(AssetInUseError):
                asset_service.delete(self_a, input_a_id)
            assert (
                session.scalar(select(Asset).where(Asset.asset_id == input_a_id))
                is not None
            )
            with pytest.raises(GenerationJobNotFoundError):
                service.retry_failed_items(
                    all_a,
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
    finally:
        _cleanup_generation_data(
            generation_postgresql_engine,
            team_ids=team_ids,
            user_ids=user_ids,
            input_asset_ids=input_asset_ids,
        )


class FailingArchiveRepository(GenerationRepository):
    def add_material_group_asset(
        self,
        group: ProductMaterialGroup,
        link: MaterialGroupAsset,
    ) -> None:
        del group
        del link
        raise RuntimeError("forced archive failure")


def test_batch_generation_delete_guard_set_null_archive_and_rollback(
    generation_postgresql_engine: Engine,
    tmp_path: Path,
) -> None:
    team_id, user_id = uuid4(), uuid4()
    source_asset_id = uuid4()
    team_ids = {team_id}
    user_ids = {user_id}
    input_asset_ids = {source_asset_id}

    try:
        with Session(generation_postgresql_engine, expire_on_commit=False) as session:
            session.add(Team(team_id=team_id, name="stage-2a1 Batch Team", enabled=True))
            session.add(
                User(user_id=user_id, display_name="stage-2a1 Batch User", enabled=True),
            )
            session.commit()
            session.add(
                asset(
                    asset_id=source_asset_id,
                    team_id=team_id,
                    created_by_user_id=user_id,
                    filename="batch-source.png",
                ),
            )
            session.commit()
            current_actor = actor(
                user_id=user_id,
                team_id=team_id,
                scope=DataScope.TEAM,
            )
            workbench_service = AiWorkbenchService(session)
            material_group, _ = create_batch_source(
                workbench_service,
                current_actor,
                source_asset_id,
                name="stage-2a1 Batch Success",
            )
            storage = LocalAssetStorage(tmp_path / "batch-outputs", 1024)
            asset_service = AssetService(
                session,
                storage=storage,
                settings=Settings(asset_storage_dir=tmp_path / "unused"),
            )
            generation_service = GenerationService(
                session,
                asset_service=asset_service,
            )
            job = generation_service.submit(
                current_actor,
                batch_submit(material_group.material_group_id, key="batch-success"),
            )
            listed_jobs, listed_total = generation_service.list(
                actor=current_actor,
                page=1,
                page_size=20,
                work_mode=GenerationWorkMode.BATCH,
                mode=None,
                status=None,
            )
            assert listed_total == 1
            assert listed_jobs[0][2].count == 1
            assert listed_jobs[0][2].primary_name == material_group.name
            with pytest.raises(ProductMaterialGroupHasActiveGenerationJobsError):
                workbench_service.delete_product_material_group(
                    current_actor,
                    material_group.material_group_id,
                )

            item = job.items[0]
            job = generation_service.complete_item(
                item.generation_item_id,
                original_filename="batch-result.png",
                content_type="image/png",
                stream=BytesIO(b"\x89PNG\r\n\x1a\nbatch"),
            )
            item = job.items[0]
            assert job.status == GenerationJobStatus.SUCCESS.value
            assert item.archived_material_group_id == material_group.material_group_id
            assert item.archived_material_group_name_snapshot == material_group.name
            assert item.output_asset is not None
            output_asset_id = item.output_asset.asset_id
            assert session.scalar(
                select(MaterialGroupAsset).where(
                    MaterialGroupAsset.material_group_id
                    == material_group.material_group_id,
                    MaterialGroupAsset.asset_id == output_asset_id,
                    MaterialGroupAsset.role == MaterialRole.AI_OUTPUT.value,
                ),
            ) is not None

            workbench_service.delete_product_material_group(
                current_actor,
                material_group.material_group_id,
            )
            job = generation_service.get(current_actor, job.generation_job_id)
            item = job.items[0]
            assert item.source_product_material_group_id is None
            assert item.archived_material_group_id is None
            assert item.product_name_snapshot == material_group.name
            assert item.archived_material_group_name_snapshot == material_group.name
            assert session.scalar(
                select(Asset).where(Asset.asset_id == output_asset_id),
            ) is not None
            with pytest.raises(AssetInUseError):
                asset_service.delete(current_actor, output_asset_id)

            failed_group, _ = create_batch_source(
                workbench_service,
                current_actor,
                source_asset_id,
                name="stage-2a1 Batch Failed",
            )
            failed_job = generation_service.submit(
                current_actor,
                batch_submit(failed_group.material_group_id, key="batch-failed"),
            )
            failed_job = generation_service.fail_item(
                failed_job.items[0].generation_item_id,
                failure_code="SAFE_FAILURE",
                failure_message="待重试",
            )
            assert failed_job.status == GenerationJobStatus.FAILED.value
            failed_item = failed_job.items[0]
            workbench_service.delete_product_material_group(
                current_actor,
                failed_group.material_group_id,
            )
            with pytest.raises(ProductMaterialGroupNotFoundError):
                generation_service.retry_failed_items(
                    current_actor,
                    failed_job.generation_job_id,
                    retry_request(failed_item),
                )
            current_failed = generation_service.get(
                current_actor,
                failed_job.generation_job_id,
            ).items[0]
            assert current_failed.status == GenerationItemStatus.FAILED.value
            assert current_failed.attempt_count == 1

            rollback_group, _ = create_batch_source(
                workbench_service,
                current_actor,
                source_asset_id,
                name="stage-2a1 Batch Rollback",
            )
            rollback_service = GenerationService(
                session,
                generation_repository=FailingArchiveRepository(session),
                asset_service=asset_service,
            )
            rollback_job = rollback_service.submit(
                current_actor,
                batch_submit(rollback_group.material_group_id, key="batch-rollback"),
            )
            before_files = set((tmp_path / "batch-outputs").glob("*"))
            with pytest.raises(RuntimeError, match="forced archive failure"):
                rollback_service.complete_item(
                    rollback_job.items[0].generation_item_id,
                    original_filename="rollback.png",
                    content_type="image/png",
                    stream=BytesIO(b"\x89PNG\r\n\x1a\nrollback"),
                )
            after_files = set((tmp_path / "batch-outputs").glob("*"))
            assert after_files == before_files
            rollback_job = generation_service.get(
                current_actor,
                rollback_job.generation_job_id,
            )
            assert rollback_job.items[0].status == GenerationItemStatus.FAILED.value
            assert rollback_job.items[0].output_asset_id is None
            assert (
                rollback_job.items[0].last_failure_code
                == "OUTPUT_PERSISTENCE_FAILED"
            )
            assert rollback_job.items[0].last_failure_message == "生成结果保存失败"
    finally:
        _cleanup_generation_data(
            generation_postgresql_engine,
            team_ids=team_ids,
            user_ids=user_ids,
            input_asset_ids=input_asset_ids,
        )


def test_batch_retry_and_material_group_delete_have_consistent_lock_order(
    generation_postgresql_engine: Engine,
) -> None:
    team_id, user_id, source_asset_id = uuid4(), uuid4(), uuid4()
    team_ids = {team_id}
    user_ids = {user_id}
    input_asset_ids = {source_asset_id}

    try:
        with Session(generation_postgresql_engine, expire_on_commit=False) as session:
            session.add(Team(team_id=team_id, name="stage-2a1 Race Team", enabled=True))
            session.add(
                User(user_id=user_id, display_name="stage-2a1 Race User", enabled=True),
            )
            session.commit()
            session.add(
                asset(
                    asset_id=source_asset_id,
                    team_id=team_id,
                    created_by_user_id=user_id,
                    filename="race-source.png",
                ),
            )
            session.commit()
            current_actor = actor(
                user_id=user_id,
                team_id=team_id,
                scope=DataScope.TEAM,
            )
            workbench_service = AiWorkbenchService(session)
            material_group, _ = create_batch_source(
                workbench_service,
                current_actor,
                source_asset_id,
                name="stage-2a1 Retry Delete Race",
            )
            generation_service = GenerationService(session)
            job = generation_service.submit(
                current_actor,
                batch_submit(material_group.material_group_id, key="retry-delete-race"),
            )
            job = generation_service.fail_item(
                job.items[0].generation_item_id,
                failure_code="SAFE_FAILURE",
                failure_message="等待重试",
            )
            generation_job_id = job.generation_job_id
            generation_item_id = job.items[0].generation_item_id
            material_group_id = material_group.material_group_id
            retry = retry_request(job.items[0])

        start = Barrier(2)

        def delete_group() -> str:
            with Session(generation_postgresql_engine) as session:
                start.wait(timeout=10)
                try:
                    AiWorkbenchService(session).delete_product_material_group(
                        current_actor,
                        material_group_id,
                    )
                except ProductMaterialGroupHasActiveGenerationJobsError:
                    return "blocked"
                return "deleted"

        def retry_item() -> str:
            with Session(generation_postgresql_engine) as session:
                start.wait(timeout=10)
                try:
                    GenerationService(session).retry_failed_items(
                        current_actor,
                        generation_job_id,
                        retry,
                    )
                except ProductMaterialGroupNotFoundError:
                    return "missing"
                return "retried"

        with ThreadPoolExecutor(max_workers=2) as executor:
            delete_future = executor.submit(delete_group)
            retry_future = executor.submit(retry_item)
            outcome = (
                delete_future.result(timeout=15),
                retry_future.result(timeout=15),
            )

        assert outcome in {("deleted", "missing"), ("blocked", "retried")}
        with Session(generation_postgresql_engine) as session:
            current_item = session.get(GenerationItem, generation_item_id)
            assert current_item is not None
            if outcome == ("deleted", "missing"):
                assert session.get(ProductMaterialGroup, material_group_id) is None
                assert current_item.status == GenerationItemStatus.FAILED.value
                assert current_item.attempt_count == 1
                assert current_item.source_product_material_group_id is None
            else:
                assert session.get(ProductMaterialGroup, material_group_id) is not None
                assert current_item.status == GenerationItemStatus.PENDING.value
                assert current_item.attempt_count == 2
    finally:
        _cleanup_generation_data(
            generation_postgresql_engine,
            team_ids=team_ids,
            user_ids=user_ids,
            input_asset_ids=input_asset_ids,
        )


def _cleanup_generation_data(
    engine: Engine,
    *,
    team_ids: set[UUID],
    user_ids: set[UUID],
    input_asset_ids: set[UUID],
) -> None:
    with Session(engine) as session:
        job_ids = select(GenerationJob.generation_job_id).where(
            GenerationJob.team_id.in_(team_ids),
        )
        item_ids = select(GenerationItem.generation_item_id).where(
            GenerationItem.generation_job_id.in_(job_ids),
        )
        session.execute(
            delete(GenerationItemAsset).where(
                GenerationItemAsset.generation_item_id.in_(item_ids),
            ),
        )
        session.execute(
            delete(GenerationItem).where(GenerationItem.generation_job_id.in_(job_ids)),
        )
        session.execute(
            delete(GenerationJob).where(GenerationJob.team_id.in_(team_ids)),
        )
        group_ids = select(ProductMaterialGroup.material_group_id).where(
            ProductMaterialGroup.team_id.in_(team_ids),
        )
        template_group_ids = select(TemplateGroup.template_group_id).where(
            TemplateGroup.team_id.in_(team_ids),
        )
        session.execute(
            delete(MaterialGroupTemplateBinding).where(
                MaterialGroupTemplateBinding.material_group_id.in_(group_ids),
            ),
        )
        session.execute(
            delete(MaterialGroupAsset).where(
                MaterialGroupAsset.material_group_id.in_(group_ids),
            ),
        )
        session.execute(
            delete(PromptTemplate).where(
                PromptTemplate.template_group_id.in_(template_group_ids),
            ),
        )
        session.execute(
            delete(ProductMaterialGroup).where(
                ProductMaterialGroup.team_id.in_(team_ids),
            ),
        )
        session.execute(
            delete(TemplateGroup).where(TemplateGroup.team_id.in_(team_ids)),
        )
        session.execute(
            delete(Asset).where(
                (Asset.team_id.in_(team_ids)) | (Asset.asset_id.in_(input_asset_ids)),
            ),
        )
        session.execute(delete(User).where(User.user_id.in_(user_ids)))
        session.execute(delete(Team).where(Team.team_id.in_(team_ids)))
        session.commit()
