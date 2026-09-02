from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.access.models import Team
from app.modules.access.roles import DEFAULT_TEAM_NAME
from app.modules.assets.contracts import AssetOwnership
from app.modules.assets.enums import AssetMediaType, AssetSourceType
from app.modules.assets.exceptions import AssetInUseError, AssetNotFoundError
from app.modules.assets.models import Asset
from app.modules.assets.service import AssetService
from app.modules.assets.storage import LocalAssetStorage
from app.modules.devices.models import Device
from app.modules.tasks.models import Task, TaskAsset
from app.modules.tasks.schemas import TaskCreate
from app.modules.tasks.service import TaskService
from app.modules.workers.models import DeviceRuntime, DeviceSkillCapability
from app.modules.workers.service import WorkerPrincipal


pytestmark = pytest.mark.integration


def _cleanup(engine: Engine, device_ids: set[UUID], asset_ids: set[UUID]) -> None:
    with Session(engine) as session:
        task_ids = select(Task.task_id).where(Task.target_device_id.in_(device_ids))
        session.execute(delete(TaskAsset).where(TaskAsset.task_id.in_(task_ids)))
        session.execute(delete(Task).where(Task.target_device_id.in_(device_ids)))
        session.execute(
            delete(DeviceSkillCapability).where(
                DeviceSkillCapability.device_id.in_(device_ids),
            ),
        )
        session.execute(
            delete(DeviceRuntime).where(DeviceRuntime.device_id.in_(device_ids)),
        )
        session.execute(delete(Device).where(Device.device_id.in_(device_ids)))
        session.execute(delete(Asset).where(Asset.asset_id.in_(asset_ids)))
        session.commit()


def test_ordered_task_assets_are_claimed_and_download_is_device_isolated(
    postgresql_engine: Engine,
    tmp_path: Path,
) -> None:
    device_a, device_b = uuid4(), uuid4()
    device_ids = {device_a, device_b}
    asset_ids: set[UUID] = set()
    now = datetime.now(UTC)
    storage = LocalAssetStorage(tmp_path / "assets", 1024 * 1024)
    settings = Settings(asset_storage_dir=tmp_path / "assets")
    first_payload = b"\xff\xd8\xfffirst-image"
    second_payload = b"\x89PNG\r\n\x1a\nsecond-image"
    try:
        with Session(postgresql_engine, expire_on_commit=False) as session:
            session.add_all(
                [
                    Device(
                        device_id=device_a, display_name="Asset Device A", enabled=True
                    ),
                    Device(
                        device_id=device_b, display_name="Asset Device B", enabled=True
                    ),
                    DeviceRuntime(
                        device_id=device_a,
                        worker_version="0.4.6",
                        last_seen_at=now,
                        started_at=now,
                        connection_status="online",
                    ),
                    DeviceSkillCapability(
                        device_id=device_a,
                        skill_id="system.echo",
                        display_name="Echo",
                        runtime="python",
                        provider_code=None,
                        skill_version="1",
                        classification="internal",
                    ),
                ],
            )
            session.commit()

            asset_service = AssetService(
                session,
                storage=storage,
                settings=settings,
            )
            default_team = session.scalar(
                select(Team).where(Team.name == DEFAULT_TEAM_NAME),
            )
            assert default_team is not None
            ownership = AssetOwnership(
                team_id=default_team.team_id,
                created_by_user_id=None,
            )
            actor = ActorContext(
                user_id=uuid4(),
                user_display_name="Task Asset集成测试",
                team_id=default_team.team_id,
                membership_id=uuid4(),
                role_code="member",
                data_scope=DataScope.TEAM,
            )
            first = asset_service.create(
                original_filename="same.jpg",
                content_type="image/jpeg",
                stream=BytesIO(first_payload),
                media_type=AssetMediaType.IMAGE,
                source_type=AssetSourceType.UPLOAD,
                ownership=ownership,
            )
            second = asset_service.create(
                original_filename="same.png",
                content_type="image/png",
                stream=BytesIO(second_payload),
                media_type=AssetMediaType.IMAGE,
                source_type=AssetSourceType.UPLOAD,
                ownership=ownership,
            )
            asset_ids.update({first.asset_id, second.asset_id})
            assert first.media_type == AssetMediaType.IMAGE.value
            assert first.source_type == AssetSourceType.UPLOAD.value

            task_service = TaskService(session)
            task = task_service.create(
                TaskCreate(
                    target_device_id=device_a,
                    asset_ids=[second.asset_id, first.asset_id],
                    skill_id="system.echo",
                    input={"message": "safe transfer"},
                ),
            )
            links = list(
                session.scalars(
                    select(TaskAsset)
                    .where(TaskAsset.task_id == task.task_id)
                    .order_by(TaskAsset.position),
                ),
            )
            assert [(link.asset_id, link.position) for link in links] == [
                (second.asset_id, 0),
                (first.asset_id, 1),
            ]

            claimed = task_service.claim_with_account(
                WorkerPrincipal(device_id=device_a),
                now=now,
            )
            assert claimed is not None
            assert [asset.asset_id for asset in claimed.assets] == [
                second.asset_id,
                first.asset_id,
            ]
            _, content = asset_service.get_worker_content(
                WorkerPrincipal(device_id=device_a),
                task_id=task.task_id,
                asset_id=first.asset_id,
            )
            with content:
                assert content.read() == first_payload
            with pytest.raises(AssetNotFoundError):
                asset_service.get_worker_content(
                    WorkerPrincipal(device_id=device_b),
                    task_id=task.task_id,
                    asset_id=first.asset_id,
                )
            with pytest.raises(AssetInUseError):
                asset_service.delete(actor, first.asset_id)
    finally:
        _cleanup(postgresql_engine, device_ids, asset_ids)
