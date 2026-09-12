from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from pathlib import Path
from random import Random
from uuid import UUID, uuid4

import pytest
from PIL import Image
from sqlalchemy import Engine, delete, inspect, select, text
from sqlalchemy.orm import Session

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
from app.modules.ai_workbench.generation_service import GenerationService
from app.modules.ai_workbench.models import (
    GenerationItem,
    GenerationItemAsset,
    GenerationJob,
    GenerationProviderExecution,
)
from app.modules.ai_workbench.schemas import InstantGenerationSubmit
from app.modules.assets.enums import AssetSourceType
from app.modules.assets.models import Asset
from app.modules.assets.service import AssetService
from app.modules.assets.storage import LocalAssetStorage
from app.modules.users.models import User


pytestmark = pytest.mark.integration

FEATURE_DATABASE = "control_center_feat_ai_workbench_input_preview_output"
EXPECTED_REVISION = "20260912_0035"
MODEL_ID = UUID("13b4f558-cd56-4f11-99fc-c64275e14031")
TEST_PREFIX = "stage-0106-output-compression"


@pytest.fixture(scope="module")
def output_compression_postgresql_engine() -> Engine:
    engine = get_database_engine()
    if not engine.url.drivername.startswith("postgresql"):
        pytest.fail("AI output compression integration tests require PostgreSQL")
    if engine.url.database != FEATURE_DATABASE:
        pytest.fail(
            "AI output compression tests only run against "
            f"{FEATURE_DATABASE}",
        )
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == FEATURE_DATABASE
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            EXPECTED_REVISION
        )
    columns = {
        column["name"]
        for column in inspect(engine).get_columns("generation_jobs")
    }
    assert "compress_output_under_1000kb" in columns
    return engine


def _actor(*, user_id: UUID, team_id: UUID) -> ActorContext:
    return ActorContext(
        user_id=user_id,
        user_display_name=TEST_PREFIX,
        team_id=team_id,
        membership_id=uuid4(),
        role_code="member",
        data_scope=DataScope.TEAM,
    )


def _large_generated_jpeg() -> bytes:
    width, height = 1_600, 1_200
    random = Random(1_006)
    image = Image.frombytes(
        "RGB",
        (width, height),
        random.randbytes(width * height * 3),
    )
    output = BytesIO()
    image.save(output, format="JPEG", quality=100)
    payload = output.getvalue()
    assert len(payload) > 1_000_000
    return payload


def _small_input_png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (8, 8), color=(240, 240, 240)).save(output, format="PNG")
    return output.getvalue()


def _clear_residue(engine: Engine) -> None:
    """Remove only rows created by this isolated Feature DB integration test."""

    with Session(engine) as session:
        team_ids = list(
            session.scalars(
                select(Team.team_id).where(Team.name.like(f"{TEST_PREFIX}%")),
            ),
        )
        user_ids = list(
            session.scalars(
                select(User.user_id).where(
                    User.display_name.like(f"{TEST_PREFIX}%"),
                ),
            ),
        )
        if team_ids:
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
            if job_ids:
                session.execute(
                    delete(GenerationJob).where(
                        GenerationJob.generation_job_id.in_(job_ids),
                    ),
                )
            session.execute(delete(Asset).where(Asset.team_id.in_(team_ids)))
            session.execute(delete(Team).where(Team.team_id.in_(team_ids)))
        if user_ids:
            session.execute(delete(User).where(User.user_id.in_(user_ids)))
        session.commit()


@pytest.fixture(autouse=True)
def clear_output_compression_residue(
    output_compression_postgresql_engine: Engine,
) -> None:
    _clear_residue(output_compression_postgresql_engine)
    yield
    _clear_residue(output_compression_postgresql_engine)


def test_compressed_generation_output_persists_only_the_final_asset(
    output_compression_postgresql_engine: Engine,
    tmp_path: Path,
) -> None:
    settings = Settings(
        _env_file=None,
        asset_storage_dir=tmp_path / "assets",
        asset_max_upload_bytes=8 * 1024 * 1024,
    )
    storage = LocalAssetStorage(
        settings.asset_storage_dir,
        settings.asset_max_upload_bytes,
    )
    user_id = uuid4()
    team_id = uuid4()
    actor = _actor(user_id=user_id, team_id=team_id)

    def service(session: Session) -> GenerationService:
        return GenerationService(
            session,
            asset_service=AssetService(
                session,
                storage=storage,
                settings=settings,
            ),
        )

    with Session(output_compression_postgresql_engine, expire_on_commit=False) as session:
        session.add_all(
            [
                Team(team_id=team_id, name=TEST_PREFIX, enabled=True),
                User(
                    user_id=user_id,
                    display_name=TEST_PREFIX,
                    enabled=True,
                ),
            ],
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
            stream=BytesIO(_small_input_png()),
        )
        job = service(session).submit(
            actor,
            InstantGenerationSubmit(
                work_mode=GenerationWorkMode.INSTANT,
                submission_key="stage-0106-compressed-output",
                model_id=MODEL_ID,
                mode=GenerationMode.NORMAL_GENERATION,
                product_asset_ids=[input_asset.asset_id],
                prompt="完整普通文本提示词",
                output_format=OutputFormat.SINGLE,
                size="1:1",  # type: ignore[arg-type]
                count=1,
                compress_output_under_1000kb=True,
            ),
        )
        item_id = job.items[0].generation_item_id
        service(session).complete_item(
            item_id,
            original_filename="provider-large.jpeg",
            content_type="image/jpeg",
            stream=BytesIO(_large_generated_jpeg()),
        )

    with Session(output_compression_postgresql_engine) as session:
        item = session.get(GenerationItem, item_id)
        assert item is not None
        job = session.get(GenerationJob, item.generation_job_id)
        output = session.get(Asset, item.output_asset_id)
        assert job is not None
        assert output is not None
        assert job.compress_output_under_1000kb is True
        assert job.status == GenerationJobStatus.SUCCESS.value
        assert item.status == GenerationItemStatus.SUCCESS.value
        assert output.source_type == AssetSourceType.AI_GENERATED.value
        assert output.team_id == team_id
        assert output.created_by_user_id == user_id
        assert output.size_bytes < 1_000_000
        assert output.content_type == "image/jpeg"
        assert output.original_filename.endswith(".jpg")
        with storage.open(output.storage_key) as content:
            final_bytes = content.read()
        assert len(final_bytes) == output.size_bytes
        assert sha256(final_bytes).hexdigest() == output.sha256
        with Image.open(BytesIO(final_bytes)) as image:
            image.load()
            assert image.format == "JPEG"
