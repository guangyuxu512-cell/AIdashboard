from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, delete, inspect, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.database import get_database_engine
from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.access.models import Team
from app.modules.ai_workbench.enums import (
    GenerationItemStatus,
    GenerationJobStatus,
    GenerationMode,
    GenerationWorkMode,
    OutputFormat,
)
from app.modules.ai_workbench.exceptions import GenerationItemStateConflictError
from app.modules.ai_workbench.generation_executor import GenerationExecutor
from app.modules.ai_workbench.generation_service import GenerationService
from app.modules.ai_workbench.models import (
    GenerationItem,
    GenerationItemAsset,
    GenerationJob,
    GenerationProviderExecution,
)
from app.modules.ai_workbench.provider import (
    GeneratedProviderImage,
    GenerationProviderRequest,
    ImageProviderFailure,
)
from app.modules.ai_workbench.schemas import (
    GenerationRetryRequest,
    InstantGenerationSubmit,
)
from app.modules.assets.enums import AssetSourceType
from app.modules.assets.models import Asset
from app.modules.assets.service import AssetService
from app.modules.assets.storage import LocalAssetStorage
from app.modules.users.models import User


pytestmark = pytest.mark.integration
FEATURE_DATABASE = "control_center_feat_ai_provider"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + (b"stage-2a1-provider" * 8)


@pytest.fixture(scope="module")
def provider_postgresql_engine() -> Engine:
    engine = get_database_engine()
    if not engine.url.drivername.startswith("postgresql"):
        pytest.fail("AI provider integration tests require PostgreSQL")
    if engine.url.database != FEATURE_DATABASE:
        pytest.fail(f"AI provider tests only run against {FEATURE_DATABASE}")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == FEATURE_DATABASE
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "20260905_0030"
        )
    inspector = inspect(engine)
    assert "generation_provider_executions" in inspector.get_table_names()
    assert {column["name"] for column in inspector.get_columns(
        "generation_provider_executions",
    )} == {
        "generation_item_id",
        "provider_code",
        "external_task_id",
        "attempt_count",
        "created_at",
        "updated_at",
    }
    assert inspector.get_pk_constraint("generation_provider_executions")[
        "constrained_columns"
    ] == ["generation_item_id"]
    return engine


class FakeProvider:
    provider_code = "toapis"

    def __init__(
        self,
        *,
        task_id: str,
        failure: ImageProviderFailure | None = None,
    ) -> None:
        self.task_id = task_id
        self.failure = failure
        self.create_calls = 0
        self.waited_task_ids: list[str] = []
        self.requests: list[GenerationProviderRequest] = []

    def create_task(self, request: GenerationProviderRequest) -> str:
        self.create_calls += 1
        self.requests.append(request)
        assert request.input_images
        assert all(image.stream.read(8) == b"\x89PNG\r\n\x1a\n" for image in request.input_images)
        return self.task_id

    def wait_for_image(self, external_task_id: str) -> GeneratedProviderImage:
        self.waited_task_ids.append(external_task_id)
        if self.failure is not None:
            raise self.failure
        return GeneratedProviderImage(
            original_filename="generated.png",
            content_type="image/png",
            stream=BytesIO(PNG_BYTES),
        )


def current_actor(*, user_id: UUID, team_id: UUID) -> ActorContext:
    return ActorContext(
        user_id=user_id,
        user_display_name="stage-2a1 AI Provider",
        team_id=team_id,
        membership_id=uuid4(),
        role_code="member",
        data_scope=DataScope.TEAM,
    )


def submit_request(asset_id: UUID, *, key: str) -> InstantGenerationSubmit:
    return InstantGenerationSubmit(
        work_mode=GenerationWorkMode.INSTANT,
        submission_key=key,
        mode=GenerationMode.NORMAL_GENERATION,
        product_asset_ids=[asset_id],
        prompt="stage-2a1 完整 Literal Prompt",
        output_format=OutputFormat.SINGLE,
        size="1:1",  # type: ignore[arg-type]
        count=1,
    )


def test_provider_execution_persistence_recovery_retry_and_asset_ownership(
    provider_postgresql_engine: Engine,
    tmp_path: Path,
) -> None:
    engine = provider_postgresql_engine
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    settings = Settings(
        _env_file=None,
        asset_storage_dir=tmp_path / "assets",
        asset_max_upload_bytes=1024 * 1024,
    )
    storage = LocalAssetStorage(
        settings.asset_storage_dir,
        settings.asset_max_upload_bytes,
    )
    user_id = uuid4()
    team_id = uuid4()
    actor = current_actor(user_id=user_id, team_id=team_id)
    job_ids: list[UUID] = []

    def service_factory(session: Session) -> GenerationService:
        return GenerationService(
            session,
            asset_service=AssetService(
                session,
                storage=storage,
                settings=settings,
            ),
        )

    try:
        with factory() as session:
            session.add(
                User(
                    user_id=user_id,
                    display_name="stage-2a1 AI Provider",
                    enabled=True,
                ),
            )
            session.add(
                Team(
                    team_id=team_id,
                    name="stage-2a1 AI Provider Team",
                    enabled=True,
                ),
            )
            session.commit()
            input_asset = AssetService(
                session,
                storage=storage,
                settings=settings,
            ).upload(
                actor=actor,
                original_filename="input.png",
                content_type="image/png",
                stream=BytesIO(PNG_BYTES),
            )
            input_asset_id = input_asset.asset_id

        with factory() as session:
            job = service_factory(session).submit(
                actor,
                submit_request(input_asset_id, key="stage-2a1-provider-success"),
            )
            job_ids.append(job.generation_job_id)
            success_item_id = job.items[0].generation_item_id

        success_provider = FakeProvider(task_id="stage-2a1-task-success")
        executor = GenerationExecutor(
            session_factory=factory,
            service_factory=service_factory,
            provider=success_provider,
            storage=storage,
        )
        assert executor.execute_next() is True

        with factory() as session:
            item = session.get(GenerationItem, success_item_id)
            execution = session.get(GenerationProviderExecution, success_item_id)
            output = session.get(Asset, item.output_asset_id if item else None)
            assert item is not None
            assert execution is not None
            assert output is not None
            assert item.status == GenerationItemStatus.SUCCESS.value
            assert item.attempt_count == execution.attempt_count == 1
            assert execution.external_task_id == "stage-2a1-task-success"
            assert output.source_type == AssetSourceType.AI_GENERATED.value
            assert output.team_id == team_id
            assert output.created_by_user_id == user_id
            assert storage.exists(output.storage_key)
            assert not hasattr(execution, "provider_payload")
            assert not hasattr(execution, "result_url")

        with factory() as session:
            recovery_job = service_factory(session).submit(
                actor,
                submit_request(input_asset_id, key="stage-2a1-provider-recovery"),
            )
            job_ids.append(recovery_job.generation_job_id)
            recovery_item_id = recovery_job.items[0].generation_item_id
        with factory() as session:
            service = service_factory(session)
            prepared = service.prepare_next_provider_execution(provider_code="toapis")
            assert prepared is not None
            assert prepared.generation_item_id == recovery_item_id
            service.record_provider_execution(
                recovery_item_id,
                expected_attempt_count=1,
                provider_code="toapis",
                external_task_id="stage-2a1-task-resume",
            )

        recovery_provider = FakeProvider(task_id="must-not-be-created")
        recovery_executor = GenerationExecutor(
            session_factory=factory,
            service_factory=service_factory,
            provider=recovery_provider,
            storage=storage,
        )
        assert recovery_executor.execute_next() is True
        assert recovery_provider.create_calls == 0
        assert recovery_provider.waited_task_ids == ["stage-2a1-task-resume"]

        with factory() as session:
            failed_job = service_factory(session).submit(
                actor,
                submit_request(input_asset_id, key="stage-2a1-provider-retry"),
            )
            job_ids.append(failed_job.generation_job_id)
            failed_item_id = failed_job.items[0].generation_item_id
        failure_provider = FakeProvider(
            task_id="stage-2a1-task-attempt-1",
            failure=ImageProviderFailure(
                "PROVIDER_REJECTED",
                "图片生成服务拒绝了请求",
                retryable=False,
            ),
        )
        failure_executor = GenerationExecutor(
            session_factory=factory,
            service_factory=service_factory,
            provider=failure_provider,
            storage=storage,
        )
        assert failure_executor.execute_next() is True

        with factory() as session:
            failed_item = session.get(GenerationItem, failed_item_id)
            failed_job_row = session.get(
                GenerationJob,
                failed_item.generation_job_id if failed_item else None,
            )
            assert failed_item is not None
            assert failed_job_row is not None
            assert failed_item.status == GenerationItemStatus.FAILED.value
            assert failed_item.last_failure_code == "PROVIDER_REJECTED"
            assert failed_job_row.status == GenerationJobStatus.FAILED.value
            service_factory(session).retry_failed_items(
                actor,
                failed_job_row.generation_job_id,
                GenerationRetryRequest.model_validate(
                    {
                        "items": [
                            {
                                "item_id": str(failed_item_id),
                                "expected_attempt_count": 1,
                            },
                        ],
                    },
                ),
            )

        with factory() as session:
            with pytest.raises(GenerationItemStateConflictError):
                service_factory(session).complete_item(
                    failed_item_id,
                    original_filename="stale.png",
                    content_type="image/png",
                    stream=BytesIO(PNG_BYTES),
                    expected_attempt_count=1,
                )

        retry_provider = FakeProvider(task_id="stage-2a1-task-attempt-2")
        retry_executor = GenerationExecutor(
            session_factory=factory,
            service_factory=service_factory,
            provider=retry_provider,
            storage=storage,
        )
        assert retry_executor.execute_next() is True
        with factory() as session:
            retried_item = session.get(GenerationItem, failed_item_id)
            execution = session.get(GenerationProviderExecution, failed_item_id)
            assert retried_item is not None
            assert execution is not None
            assert retried_item.status == GenerationItemStatus.SUCCESS.value
            assert retried_item.attempt_count == 2
            assert execution.attempt_count == 2
            assert execution.external_task_id == "stage-2a1-task-attempt-2"
    finally:
        with factory() as session:
            item_ids = list(
                session.scalars(
                    select(GenerationItem.generation_item_id).where(
                        GenerationItem.generation_job_id.in_(job_ids),
                    ),
                ),
            )
            asset_rows = list(
                session.scalars(select(Asset).where(Asset.team_id == team_id)),
            )
            if item_ids:
                session.execute(
                    delete(GenerationProviderExecution).where(
                        GenerationProviderExecution.generation_item_id.in_(item_ids),
                    ),
                )
                session.execute(
                    delete(GenerationItemAsset).where(
                        GenerationItemAsset.generation_item_id.in_(item_ids),
                    ),
                )
                session.execute(
                    delete(GenerationItem).where(
                        GenerationItem.generation_item_id.in_(item_ids),
                    ),
                )
            if job_ids:
                session.execute(
                    delete(GenerationJob).where(
                        GenerationJob.generation_job_id.in_(job_ids),
                    ),
                )
            session.execute(delete(Asset).where(Asset.team_id == team_id))
            session.execute(delete(Team).where(Team.team_id == team_id))
            session.execute(delete(User).where(User.user_id == user_id))
            session.commit()
        for asset_row in asset_rows:
            storage.delete(asset_row.storage_key)
