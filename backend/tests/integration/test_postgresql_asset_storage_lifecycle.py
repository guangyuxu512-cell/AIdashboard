from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, delete, make_url, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_database_engine
from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.access.models import Team
from app.modules.assets.contracts import AssetOwnership
from app.modules.assets.enums import AssetMediaType, AssetSourceType
from app.modules.assets.exceptions import AssetStorageUnavailableError
from app.modules.assets.models import Asset
from app.modules.assets.service import AssetService
from app.modules.assets.storage import (
    MOUNTED_STORAGE_MARKER_CONTENT,
    MOUNTED_STORAGE_MARKER_NAME,
    MountedAssetStorage,
)
from app.modules.users.models import User


pytestmark = pytest.mark.integration

FEATURE_DATABASE = "control_center_feat_nas_asset_storage"


@pytest.fixture(scope="session")
def feature_postgresql_engine() -> Engine:
    database_url = get_settings().database_url
    assert database_url is not None
    url = make_url(str(database_url))
    assert url.drivername.startswith("postgresql")
    assert url.database == FEATURE_DATABASE

    engine = get_database_engine()
    assert engine.url == url
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == FEATURE_DATABASE
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "20260906_0032"
        )
    return engine


def test_postgresql_mounted_storage_preflight_failure_keeps_asset_and_file(
    feature_postgresql_engine: Engine,
    tmp_path: Path,
) -> None:
    team_id = uuid4()
    user_id = uuid4()
    asset_id: UUID | None = None
    storage_key: str | None = None
    payload = b"\x89PNG\r\n\x1a\nmounted-storage-preflight"
    root = tmp_path / "mounted-assets"
    root.mkdir()
    marker = root / MOUNTED_STORAGE_MARKER_NAME
    marker.write_bytes(MOUNTED_STORAGE_MARKER_CONTENT)
    storage = MountedAssetStorage(root, 1024 * 1024)
    actor = ActorContext(
        user_id=user_id,
        user_display_name="NAS Asset Lifecycle",
        team_id=team_id,
        membership_id=uuid4(),
        role_code="member",
        data_scope=DataScope.TEAM,
    )

    try:
        with Session(feature_postgresql_engine, expire_on_commit=False) as session:
            session.add_all(
                [
                    Team(
                        team_id=team_id,
                        name=f"stage-2a1-nas-assets-{team_id}",
                        enabled=True,
                    ),
                    User(
                        user_id=user_id,
                        display_name="NAS Asset Lifecycle User",
                        enabled=True,
                    ),
                ],
            )
            session.commit()
            service = AssetService(session, storage=storage)
            asset = service.create(
                original_filename="mounted.png",
                content_type="image/png",
                stream=BytesIO(payload),
                media_type=AssetMediaType.IMAGE,
                source_type=AssetSourceType.IMPORTED,
                ownership=AssetOwnership(team_id, user_id),
            )
            asset_id = asset.asset_id
            storage_key = asset.storage_key
            marker.unlink()

            with pytest.raises(AssetStorageUnavailableError):
                service.delete(actor, asset_id)

        assert asset_id is not None
        assert storage_key is not None
        with Session(feature_postgresql_engine) as observer:
            assert (
                observer.scalar(select(Asset).where(Asset.asset_id == asset_id))
                is not None
            )
        assert (root / storage_key).read_bytes() == payload
    finally:
        with Session(feature_postgresql_engine) as session:
            if asset_id is not None:
                session.execute(delete(Asset).where(Asset.asset_id == asset_id))
            session.execute(delete(User).where(User.user_id == user_id))
            session.execute(delete(Team).where(Team.team_id == team_id))
            session.commit()
