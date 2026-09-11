from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from io import BytesIO
from pathlib import Path
from threading import Barrier, Lock
from time import monotonic, sleep
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
    ProviderCreateOutcomeUnknownError,
)
from app.modules.ai_workbench.generation_executor import GenerationExecutor
from app.modules.ai_workbench.generation_service import GenerationService
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
from app.modules.ai_workbench.provider import (
    GeneratedProviderImage,
    GenerationProviderRequest,
    ImageProviderFailure,
)
from app.modules.ai_workbench.schemas import (
    BatchGenerationSubmit,
    GenerationRetryRequest,
    InstantGenerationSubmit,
)
from app.modules.assets.enums import AssetSourceType
from app.modules.assets.exceptions import AssetStorageError
from app.modules.assets.models import Asset
from app.modules.assets.service import AssetService
from app.modules.assets.storage import LocalAssetStorage, StoredAsset
from app.modules.users.models import User


MODEL_ID = UUID("13b4f558-cd56-4f11-99fc-c64275e14031")


pytestmark = pytest.mark.integration
FEATURE_DATABASE = "control_center_feat_ai_batch_generation_download"
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
            "20260911_0034"
        )
    inspector = inspect(engine)
    assert "generation_provider_executions" in inspector.get_table_names()
    columns = {
        column["name"]: column
        for column in inspector.get_columns("generation_provider_executions")
    }
    assert set(columns) == {
        "generation_item_id",
        "provider_code",
        "external_task_id",
        "attempt_count",
        "created_at",
        "updated_at",
    }
    assert columns["external_task_id"]["nullable"] is True
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
        create_failure: ImageProviderFailure | None = None,
        before_create: Callable[[], None] | None = None,
    ) -> None:
        self.task_id = task_id
        self.failure = failure
        self.create_failure = create_failure
        self.before_create = before_create
        self.create_calls = 0
        self.waited_task_ids: list[str] = []
        self.requests: list[GenerationProviderRequest] = []

    def create_task(self, request: GenerationProviderRequest) -> str:
        if self.before_create is not None:
            self.before_create()
        self.create_calls += 1
        self.requests.append(request)
        assert request.input_images
        assert all(image.stream.read(8) == b"\x89PNG\r\n\x1a\n" for image in request.input_images)
        if self.create_failure is not None:
            raise self.create_failure
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


class FailOnceOutputStorage(LocalAssetStorage):
    """A controlled storage failure after the remote provider result is known."""

    def __init__(self, root: Path, max_upload_bytes: int) -> None:
        super().__init__(root, max_upload_bytes)
        self.fail_next_store = False

    def store(
        self,
        *,
        asset_id: UUID,
        suffix: str,
        chunks: Iterable[bytes],
        storage_key: str | None = None,
    ) -> StoredAsset:
        if self.fail_next_store:
            self.fail_next_store = False
            raise AssetStorageError()
        return super().store(
            asset_id=asset_id,
            suffix=suffix,
            chunks=chunks,
            storage_key=storage_key,
        )


class CrashBeforeTaskIdPersistenceService(GenerationService):
    def record_provider_execution(
        self,
        generation_item_id: UUID,
        *,
        expected_attempt_count: int,
        provider_code: str,
        external_task_id: str,
    ) -> None:
        raise SystemExit("stage-2a1 simulated process interruption")


class ConcurrentProvider:
    """Provider double that proves two database-backed executions overlap."""

    provider_code = "toapis"

    def __init__(self) -> None:
        self._barrier = Barrier(2, timeout=5)
        self._lock = Lock()
        self.create_calls: list[UUID] = []
        self.wait_started_at: list[float] = []
        self.wait_finished_at: list[float] = []
        self.waited_task_ids: list[str] = []

    def create_task(self, request: GenerationProviderRequest) -> str:
        with self._lock:
            self.create_calls.append(request.generation_item_id)
        return f"stage-2a1-concurrent-{request.generation_item_id}"

    def wait_for_image(self, external_task_id: str) -> GeneratedProviderImage:
        with self._lock:
            self.wait_started_at.append(monotonic())
            self.waited_task_ids.append(external_task_id)
        self._barrier.wait()
        sleep(0.05)
        with self._lock:
            self.wait_finished_at.append(monotonic())
        return GeneratedProviderImage(
            original_filename="generated.png",
            content_type="image/png",
            stream=BytesIO(PNG_BYTES),
        )


def _clear_provider_test_residue(engine: Engine) -> None:
    """Remove only this module's named rows after an interrupted Feature run."""

    with Session(engine) as session:
        team_ids = list(
            session.scalars(
                select(Team.team_id).where(Team.name.like("stage-2a1%")),
            ),
        )
        user_ids = list(
            session.scalars(
                select(User.user_id).where(User.display_name.like("stage-2a1%")),
            ),
        )
        if team_ids:
            asset_ids = list(
                session.scalars(
                    select(Asset.asset_id).where(Asset.team_id.in_(team_ids)),
                ),
            )
            material_group_ids = list(
                session.scalars(
                    select(ProductMaterialGroup.material_group_id).where(
                        ProductMaterialGroup.team_id.in_(team_ids),
                    ),
                ),
            )
            template_group_ids = list(
                session.scalars(
                    select(TemplateGroup.template_group_id).where(
                        TemplateGroup.team_id.in_(team_ids),
                    ),
                ),
            )
            job_ids = list(
                session.scalars(
                    select(GenerationJob.generation_job_id).where(
                        GenerationJob.team_id.in_(team_ids),
                    ),
                ),
            )
            item_ids = (
                list(
                    session.scalars(
                        select(GenerationItem.generation_item_id).where(
                            GenerationItem.generation_job_id.in_(job_ids),
                        ),
                    ),
                )
                if job_ids
                else []
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
            if asset_ids:
                session.execute(
                    delete(GenerationItemAsset).where(
                        GenerationItemAsset.asset_id.in_(asset_ids),
                    ),
                )
            if job_ids:
                session.execute(
                    delete(GenerationJob).where(
                        GenerationJob.generation_job_id.in_(job_ids),
                    ),
                )
            if material_group_ids:
                session.execute(
                    delete(MaterialGroupAsset).where(
                        MaterialGroupAsset.material_group_id.in_(
                            material_group_ids,
                        ),
                    ),
                )
                session.execute(
                    delete(MaterialGroupTemplateBinding).where(
                        MaterialGroupTemplateBinding.material_group_id.in_(
                            material_group_ids,
                        ),
                    ),
                )
                session.execute(
                    delete(ProductMaterialGroup).where(
                        ProductMaterialGroup.material_group_id.in_(
                            material_group_ids,
                        ),
                    ),
                )
            if template_group_ids:
                session.execute(
                    delete(PromptTemplate).where(
                        PromptTemplate.template_group_id.in_(template_group_ids),
                    ),
                )
                session.execute(
                    delete(TemplateGroup).where(
                        TemplateGroup.template_group_id.in_(template_group_ids),
                    ),
                )
            session.execute(delete(Asset).where(Asset.team_id.in_(team_ids)))
            session.execute(delete(Team).where(Team.team_id.in_(team_ids)))
        if user_ids:
            session.execute(delete(User).where(User.user_id.in_(user_ids)))
        session.commit()


@pytest.fixture(autouse=True)
def clear_interrupted_provider_test_residue(
    provider_postgresql_engine: Engine,
) -> Iterator[None]:
    _clear_provider_test_residue(provider_postgresql_engine)
    yield
    _clear_provider_test_residue(provider_postgresql_engine)


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
        model_id=MODEL_ID,
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
    storage = FailOnceOutputStorage(
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
            prepared = service.prepare_next_provider_execution()
            assert prepared is not None
            assert prepared.generation_item_id == recovery_item_id
            assert prepared.provider_task_create_required is True
            assert prepared.external_task_id is None
        with factory() as session:
            intent = session.get(GenerationProviderExecution, recovery_item_id)
            assert intent is not None
            assert intent.attempt_count == 1
            assert intent.external_task_id is None
        with factory() as session:
            service = service_factory(session)
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

        # A completed remote task may fail only while the output Asset is being
        # persisted. Its known external task id must survive retry, so recovery
        # polls/downloads that result again instead of issuing another POST.
        with factory() as session:
            output_failure_job = service_factory(session).submit(
                actor,
                submit_request(
                    input_asset_id,
                    key="stage-2a1-provider-output-persistence-recovery",
                ),
            )
            job_ids.append(output_failure_job.generation_job_id)
            output_failure_item_id = output_failure_job.items[0].generation_item_id

        storage.fail_next_store = True
        output_failure_provider = FakeProvider(
            task_id="stage-2a1-task-output-persistence",
        )
        output_failure_executor = GenerationExecutor(
            session_factory=factory,
            service_factory=service_factory,
            provider=output_failure_provider,
            storage=storage,
        )
        assert output_failure_executor.execute_next() is True
        assert output_failure_provider.create_calls == 1
        assert output_failure_provider.waited_task_ids == [
            "stage-2a1-task-output-persistence",
        ]

        with factory() as session:
            failed_item = session.get(GenerationItem, output_failure_item_id)
            failed_execution = session.get(
                GenerationProviderExecution,
                output_failure_item_id,
            )
            assert failed_item is not None
            assert failed_execution is not None
            assert failed_item.status == GenerationItemStatus.FAILED.value
            assert failed_item.last_failure_code == "OUTPUT_PERSISTENCE_FAILED"
            assert failed_item.attempt_count == failed_execution.attempt_count == 1
            assert (
                failed_execution.external_task_id
                == "stage-2a1-task-output-persistence"
            )
            service_factory(session).retry_failed_items(
                actor,
                output_failure_job.generation_job_id,
                GenerationRetryRequest.model_validate(
                    {
                        "items": [
                            {
                                "item_id": str(output_failure_item_id),
                                "expected_attempt_count": 1,
                            },
                        ],
                    },
                ),
            )

        output_recovery_provider = FakeProvider(task_id="must-not-be-created")
        output_recovery_executor = GenerationExecutor(
            session_factory=factory,
            service_factory=service_factory,
            provider=output_recovery_provider,
            storage=storage,
        )
        assert output_recovery_executor.execute_next() is True
        assert output_recovery_provider.create_calls == 0
        assert output_recovery_provider.waited_task_ids == [
            "stage-2a1-task-output-persistence",
        ]
        with factory() as session:
            recovered_item = session.get(GenerationItem, output_failure_item_id)
            recovered_execution = session.get(
                GenerationProviderExecution,
                output_failure_item_id,
            )
            assert recovered_item is not None
            assert recovered_execution is not None
            assert recovered_item.status == GenerationItemStatus.SUCCESS.value
            assert recovered_item.attempt_count == recovered_execution.attempt_count == 1
            assert (
                recovered_execution.external_task_id
                == "stage-2a1-task-output-persistence"
            )
            recovered_output = session.get(Asset, recovered_item.output_asset_id)
            assert recovered_output is not None
            assert storage.exists(recovered_output.storage_key)
            with storage.open(recovered_output.storage_key) as output_stream:
                assert output_stream.read() == PNG_BYTES

        with factory() as session:
            crash_job = service_factory(session).submit(
                actor,
                submit_request(input_asset_id, key="stage-2a1-provider-crash"),
            )
            job_ids.append(crash_job.generation_job_id)
            crash_item_id = crash_job.items[0].generation_item_id

        def crash_service_factory(session: Session) -> GenerationService:
            return CrashBeforeTaskIdPersistenceService(
                session,
                asset_service=AssetService(
                    session,
                    storage=storage,
                    settings=settings,
                ),
            )

        def assert_durable_intent_before_create() -> None:
            with factory() as session:
                intent = session.get(GenerationProviderExecution, crash_item_id)
                assert intent is not None
                assert intent.attempt_count == 1
                assert intent.external_task_id is None

        crash_provider = FakeProvider(
            task_id="stage-2a1-task-crash-window",
            before_create=assert_durable_intent_before_create,
        )
        crash_executor = GenerationExecutor(
            session_factory=factory,
            service_factory=crash_service_factory,
            provider=crash_provider,
            storage=storage,
        )
        with pytest.raises(
            SystemExit,
            match="stage-2a1 simulated process interruption",
        ):
            crash_executor.execute_next()
        assert crash_provider.create_calls == 1

        with factory() as session:
            crashed_item = session.get(GenerationItem, crash_item_id)
            crash_intent = session.get(GenerationProviderExecution, crash_item_id)
            assert crashed_item is not None
            assert crash_intent is not None
            assert crashed_item.status == GenerationItemStatus.RUNNING.value
            assert crash_intent.attempt_count == crashed_item.attempt_count == 1
            assert crash_intent.external_task_id is None

        fail_closed_provider = FakeProvider(task_id="must-not-be-created")
        fail_closed_executor = GenerationExecutor(
            session_factory=factory,
            service_factory=service_factory,
            provider=fail_closed_provider,
            storage=storage,
        )
        assert fail_closed_executor.execute_next() is True
        assert fail_closed_provider.create_calls == 0
        assert fail_closed_provider.waited_task_ids == []

        with factory() as session:
            crashed_item = session.get(GenerationItem, crash_item_id)
            crash_intent = session.get(GenerationProviderExecution, crash_item_id)
            crashed_job = session.get(
                GenerationJob,
                crashed_item.generation_job_id if crashed_item else None,
            )
            assert crashed_item is not None
            assert crash_intent is not None
            assert crashed_job is not None
            assert crashed_item.status == GenerationItemStatus.FAILED.value
            assert (
                crashed_item.last_failure_code
                == ProviderCreateOutcomeUnknownError.code
            )
            assert (
                crashed_item.last_failure_message
                == ProviderCreateOutcomeUnknownError.message
            )
            assert crashed_job.status == GenerationJobStatus.FAILED.value
            assert crash_intent.external_task_id is None
            with pytest.raises(ProviderCreateOutcomeUnknownError):
                service_factory(session).retry_failed_items(
                    actor,
                    crashed_job.generation_job_id,
                    GenerationRetryRequest.model_validate(
                        {
                            "items": [
                                {
                                    "item_id": str(crash_item_id),
                                    "expected_attempt_count": 1,
                                },
                            ],
                        },
                    ),
                )
            session.refresh(crashed_item)
            assert crashed_item.status == GenerationItemStatus.FAILED.value
            assert crashed_item.attempt_count == 1

        with factory() as session:
            ambiguous_job = service_factory(session).submit(
                actor,
                submit_request(input_asset_id, key="stage-2a1-provider-ambiguous"),
            )
            job_ids.append(ambiguous_job.generation_job_id)
            ambiguous_item_id = ambiguous_job.items[0].generation_item_id

        ambiguous_provider = FakeProvider(
            task_id="stage-2a1-remote-task-created-without-response",
            create_failure=ImageProviderFailure(
                ProviderCreateOutcomeUnknownError.code,
                ProviderCreateOutcomeUnknownError.message,
                retryable=False,
            ),
        )
        ambiguous_executor = GenerationExecutor(
            session_factory=factory,
            service_factory=service_factory,
            provider=ambiguous_provider,
            storage=storage,
        )
        assert ambiguous_executor.execute_next() is True
        assert ambiguous_provider.create_calls == 1

        no_repeat_provider = FakeProvider(task_id="must-not-be-created")
        no_repeat_executor = GenerationExecutor(
            session_factory=factory,
            service_factory=service_factory,
            provider=no_repeat_provider,
            storage=storage,
        )
        assert no_repeat_executor.execute_next() is False
        assert no_repeat_provider.create_calls == 0

        with factory() as session:
            ambiguous_item = session.get(GenerationItem, ambiguous_item_id)
            ambiguous_intent = session.get(
                GenerationProviderExecution,
                ambiguous_item_id,
            )
            assert ambiguous_item is not None
            assert ambiguous_intent is not None
            assert ambiguous_item.status == GenerationItemStatus.FAILED.value
            assert (
                ambiguous_item.last_failure_code
                == ProviderCreateOutcomeUnknownError.code
            )
            assert ambiguous_intent.external_task_id is None
            with pytest.raises(ProviderCreateOutcomeUnknownError):
                service_factory(session).retry_failed_items(
                    actor,
                    ambiguous_job.generation_job_id,
                    GenerationRetryRequest.model_validate(
                        {
                            "items": [
                                {
                                    "item_id": str(ambiguous_item_id),
                                    "expected_attempt_count": 1,
                                },
                            ],
                        },
                    ),
                )

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


def test_postgresql_executor_runs_two_distinct_items_concurrently(
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
                    display_name="stage-2a1 concurrent AI Provider",
                    enabled=True,
                ),
            )
            session.add(
                Team(
                    team_id=team_id,
                    name="stage-2a1 concurrent AI Provider Team",
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

        with factory() as session:
            first = service_factory(session).submit(
                actor,
                submit_request(
                    input_asset.asset_id,
                    key="stage-2a1-provider-concurrent-first",
                ),
            )
            second = service_factory(session).submit(
                actor,
                submit_request(
                    input_asset.asset_id,
                    key="stage-2a1-provider-concurrent-second",
                ),
            )
            job_ids.extend([first.generation_job_id, second.generation_job_id])
            expected_item_ids = {
                first.items[0].generation_item_id,
                second.items[0].generation_item_id,
            }

        provider = ConcurrentProvider()
        executor = GenerationExecutor(
            session_factory=factory,
            service_factory=service_factory,
            provider=provider,
            storage=storage,
        )
        assert executor.execute_available(2) == 2

        assert set(provider.create_calls) == expected_item_ids
        assert len(provider.create_calls) == 2
        assert len(provider.wait_started_at) == 2
        assert max(provider.wait_started_at) - min(provider.wait_started_at) < 0.5
        assert len(provider.wait_finished_at) == 2
        assert (
            max(provider.wait_finished_at) - min(provider.wait_started_at)
        ) < 0.5

        with factory() as session:
            items = list(
                session.scalars(
                    select(GenerationItem).where(
                        GenerationItem.generation_item_id.in_(expected_item_ids),
                    ),
                ),
            )
            assert {item.status for item in items} == {
                GenerationItemStatus.SUCCESS.value,
            }
            executions = list(
                session.scalars(
                    select(GenerationProviderExecution).where(
                        GenerationProviderExecution.generation_item_id.in_(
                            expected_item_ids,
                        ),
                    ),
                ),
            )
            assert len(executions) == 2
            assert {execution.external_task_id for execution in executions} == set(
                provider.waited_task_ids,
            )
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


def test_normal_batch_provider_receives_the_frozen_product_fidelity_snapshot(
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
    source_storage_key: str | None = None
    user_id = uuid4()
    team_id = uuid4()
    actor = current_actor(user_id=user_id, team_id=team_id)

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
                    display_name="stage-2a1 normal batch capture",
                    enabled=True,
                ),
            )
            session.add(
                Team(
                    team_id=team_id,
                    name="stage-2a1 normal batch capture Team",
                    enabled=True,
                ),
            )
            session.commit()
            source_asset = AssetService(
                session,
                storage=storage,
                settings=settings,
            ).upload(
                actor=actor,
                original_filename="source.png",
                content_type="image/png",
                stream=BytesIO(PNG_BYTES),
            )
            source_storage_key = source_asset.storage_key
            material_group = ProductMaterialGroup(
                team_id=team_id,
                created_by_user_id=user_id,
                name="stage-2a1 source product",
            )
            template_group = TemplateGroup(
                team_id=team_id,
                created_by_user_id=user_id,
                name="stage-2a1 normal templates",
                mode=GenerationMode.NORMAL_GENERATION.value,
            )
            session.add_all([material_group, template_group])
            session.flush()
            session.add_all(
                [
                    MaterialGroupAsset(
                        material_group_id=material_group.material_group_id,
                        asset_id=source_asset.asset_id,
                        role=MaterialRole.PRODUCT_SOURCE.value,
                    ),
                    MaterialGroupTemplateBinding(
                        material_group_id=material_group.material_group_id,
                        template_group_id=template_group.template_group_id,
                        generation_mode=GenerationMode.NORMAL_GENERATION.value,
                        position=0,
                    ),
                    PromptTemplate(
                        template_group_id=template_group.template_group_id,
                        name="stage-2a1 literal template",
                        output_role=OutputRole.MAIN_IMAGE.value,
                        output_format=OutputFormat.SINGLE.value,
                        size="1:1",
                        count=1,
                        variables=[],
                        prompt="创意模板中可能存在与产品原图冲突的描述",
                        sort_order=1,
                    ),
                ],
            )
            session.commit()

        with factory() as session:
            job = service_factory(session).submit(
                actor,
                BatchGenerationSubmit(
                    work_mode=GenerationWorkMode.BATCH,
                    submission_key="stage-2a1-normal-batch-provider-capture",
                    model_id=MODEL_ID,
                    mode=GenerationMode.NORMAL_GENERATION,
                    product_scope=BatchProductScope.SELECTED,
                    selected_product_ids=[material_group.material_group_id],
                    template_source=BatchTemplateSource.PRODUCT_CONFIGURED,
                ),
            )
            generation_item_id = job.items[0].generation_item_id
            frozen_final_prompt = job.items[0].final_prompt

        provider = FakeProvider(task_id="stage-2a1-normal-batch-provider-capture")
        executor = GenerationExecutor(
            session_factory=factory,
            service_factory=service_factory,
            provider=provider,
            storage=storage,
        )
        assert executor.execute_next() is True
        assert len(provider.requests) == 1
        request = provider.requests[0]
        assert request.generation_item_id == generation_item_id
        assert request.final_prompt == frozen_final_prompt
        assert "产品原图真实性优先" in request.final_prompt
        assert [image.asset_id for image in request.input_images] == [
            source_asset.asset_id,
        ]

        with factory() as session:
            item = session.get(GenerationItem, generation_item_id)
            assert item is not None
            assert item.status == GenerationItemStatus.SUCCESS.value
            assert item.final_prompt == request.final_prompt
    finally:
        _clear_provider_test_residue(engine)
        if source_storage_key and storage.exists(source_storage_key):
            storage.delete(source_storage_key)
