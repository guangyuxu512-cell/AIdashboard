from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.database import get_database_engine
from app.integrations.image_generation import ToApisImageProvider
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
from app.modules.ai_workbench.generation_executor import GenerationExecutor
from app.modules.ai_workbench.generation_service import GenerationService
from app.modules.ai_workbench.models import (
    GenerationItem,
    GenerationItemAsset,
    GenerationJob,
    GenerationProviderExecution,
)
from app.modules.ai_workbench.schemas import InstantGenerationSubmit
from app.modules.assets.models import Asset
from app.modules.assets.service import AssetService
from app.modules.assets.storage import LocalAssetStorage
from app.modules.assets.validation import detect_image_content_type
from app.modules.users.models import User


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("BACKEND_RUN_REAL_TOAPIS") != "1",
        reason="real ToAPIs call requires explicit BACKEND_RUN_REAL_TOAPIS=1",
    ),
]
FEATURE_DATABASE = "control_center_feat_ai_provider"
CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def test_real_toapis_normal_and_style_generation_create_owned_assets(
    tmp_path: Path,
) -> None:
    product_path = _configured_image("AI_PROVIDER_REAL_PRODUCT_IMAGE")
    style_path = _configured_image("AI_PROVIDER_REAL_STYLE_IMAGE")
    base_settings = get_settings()
    assert base_settings.toapis_api_key is not None
    engine = get_database_engine()
    assert engine.url.database == FEATURE_DATABASE
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "20260905_0030"
        )

    settings = base_settings.model_copy(
        update={"asset_storage_dir": tmp_path / "real-provider-assets"},
    )
    storage = LocalAssetStorage(
        settings.asset_storage_dir,
        settings.asset_max_upload_bytes,
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    user_id = uuid4()
    team_id = uuid4()
    actor = ActorContext(
        user_id=user_id,
        user_display_name="stage-2a1 Real ToAPIs",
        team_id=team_id,
        membership_id=uuid4(),
        role_code="member",
        data_scope=DataScope.TEAM,
    )
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

    provider = _provider(settings)
    executor = GenerationExecutor(
        session_factory=factory,
        service_factory=service_factory,
        provider=provider,
        storage=storage,
    )

    try:
        with factory() as session:
            session.add(
                User(
                    user_id=user_id,
                    display_name="stage-2a1 Real ToAPIs",
                    enabled=True,
                ),
            )
            session.add(
                Team(
                    team_id=team_id,
                    name="stage-2a1 Real ToAPIs Team",
                    enabled=True,
                ),
            )
            session.commit()
            assets = AssetService(
                session,
                storage=storage,
                settings=settings,
            )
            product_asset = _upload(assets, actor, product_path)
            style_asset = _upload(assets, actor, style_path)

        normal_job_id = _submit(
            factory,
            service_factory,
            actor,
            product_asset_id=product_asset.asset_id,
            reference_asset_ids=[],
            mode=GenerationMode.NORMAL_GENERATION,
            key=f"stage-2a1-real-normal-{uuid4()}",
            prompt=(
                "保持输入商品的真实外观、材质和结构，生成一张干净白底、主体居中的"
                "电商商品主图，不添加文字、标志或水印。"
            ),
        )
        job_ids.append(normal_job_id)
        assert executor.execute_next() is True
        _assert_success(factory, storage, normal_job_id, team_id, user_id)

        style_job_id = _submit(
            factory,
            service_factory,
            actor,
            product_asset_id=product_asset.asset_id,
            reference_asset_ids=[style_asset.asset_id],
            mode=GenerationMode.STYLE_REPLICATION,
            key=f"stage-2a1-real-style-{uuid4()}",
            prompt=(
                "保持第一张图片中商品的真实外观、颜色、材质和结构，参考第二张图片的"
                "构图与光影风格，生成一张无文字、无标志、无水印的电商主图。"
            ),
        )
        job_ids.append(style_job_id)
        assert executor.execute_next() is True
        _assert_success(factory, storage, style_job_id, team_id, user_id)
    finally:
        _cleanup(factory, storage, job_ids, team_id, user_id)


def _configured_image(env_name: str) -> Path:
    value = os.getenv(env_name)
    if not value:
        pytest.fail(f"{env_name} is required for the real ToAPIs test")
    path = Path(value)
    if not path.is_file() or path.suffix.lower() not in CONTENT_TYPES:
        pytest.fail(f"{env_name} must point to a supported local image")
    return path


def _provider(settings: Settings) -> ToApisImageProvider:
    assert settings.toapis_api_key is not None
    return ToApisImageProvider(
        api_key=settings.toapis_api_key,
        base_url=settings.toapis_base_url,
        model_code=settings.toapis_model_code,
        resolution=settings.toapis_resolution,
        quality=settings.toapis_quality,
        poll_interval_seconds=settings.toapis_poll_interval_seconds,
        poll_timeout_seconds=settings.toapis_poll_timeout_seconds,
        request_timeout_seconds=settings.toapis_request_timeout_seconds,
        max_output_bytes=settings.asset_max_upload_bytes,
    )


def _upload(
    service: AssetService,
    actor: ActorContext,
    path: Path,
) -> Asset:
    with path.open("rb") as stream:
        return service.upload(
            actor=actor,
            original_filename=path.name,
            content_type=CONTENT_TYPES[path.suffix.lower()],
            stream=stream,
        )


def _submit(
    factory: sessionmaker[Session],
    service_factory: Callable[[Session], GenerationService],
    actor: ActorContext,
    *,
    product_asset_id: UUID,
    reference_asset_ids: list[UUID],
    mode: GenerationMode,
    key: str,
    prompt: str,
) -> UUID:
    with factory() as session:
        service = service_factory(session)
        job = service.submit(
            actor,
            InstantGenerationSubmit(
                work_mode=GenerationWorkMode.INSTANT,
                submission_key=key,
                mode=mode,
                product_asset_ids=[product_asset_id],
                reference_asset_ids=reference_asset_ids,
                prompt=prompt,
                output_format=OutputFormat.SINGLE,
                size="1:1",  # type: ignore[arg-type]
                count=1,
            ),
        )
        return job.generation_job_id


def _assert_success(
    factory: sessionmaker[Session],
    storage: LocalAssetStorage,
    job_id: UUID,
    team_id: UUID,
    user_id: UUID,
) -> None:
    with factory() as session:
        job = session.get(GenerationJob, job_id)
        assert job is not None
        item = session.scalar(
            select(GenerationItem).where(
                GenerationItem.generation_job_id == job_id,
            ),
        )
        assert item is not None
        assert item.status == GenerationItemStatus.SUCCESS.value, (
            f"{item.last_failure_code}: {item.last_failure_message}"
        )
        execution = session.get(GenerationProviderExecution, item.generation_item_id)
        assert item.output_asset_id is not None
        output = session.get(Asset, item.output_asset_id)
        assert execution is not None
        assert output is not None
        assert job.status == GenerationJobStatus.SUCCESS.value
        assert execution.provider_code == "toapis"
        assert execution.attempt_count == item.attempt_count == 1
        assert output.team_id == team_id
        assert output.created_by_user_id == user_id
        assert storage.exists(output.storage_key)
        with storage.open(output.storage_key) as stream:
            assert detect_image_content_type(stream.read(16)) is not None


def _cleanup(
    factory: sessionmaker[Session],
    storage: LocalAssetStorage,
    job_ids: list[UUID],
    team_id: UUID,
    user_id: UUID,
) -> None:
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
                delete(GenerationJob).where(GenerationJob.generation_job_id.in_(job_ids)),
            )
        session.execute(delete(Asset).where(Asset.team_id == team_id))
        session.execute(delete(Team).where(Team.team_id == team_id))
        session.execute(delete(User).where(User.user_id == user_id))
        session.commit()
    for asset_row in asset_rows:
        storage.delete(asset_row.storage_key)
