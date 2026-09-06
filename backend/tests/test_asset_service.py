import hashlib
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.core.config import Settings
from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.assets.contracts import AssetOwnership
from app.modules.assets.enums import AssetMediaType, AssetSourceType
from app.modules.assets.exceptions import (
    AssetInUseError,
    AssetStorageError,
    AssetTooLargeError,
    AssetTypeUnsupportedError,
)
from app.modules.assets.models import Asset
from app.modules.assets.service import AssetService
from app.modules.assets.storage import LocalAssetStorage
from tests.support import FakeSession


ACTOR = ActorContext(
    user_id=uuid4(),
    user_display_name="素材测试用户",
    team_id=uuid4(),
    membership_id=uuid4(),
    role_code="member",
    data_scope=DataScope.TEAM,
)
HUMAN_OWNERSHIP = AssetOwnership(
    team_id=ACTOR.team_id,
    created_by_user_id=ACTOR.user_id,
)
SYSTEM_OWNERSHIP = AssetOwnership(
    team_id=ACTOR.team_id,
    created_by_user_id=None,
)


class FakeAssetRepository:
    def __init__(self) -> None:
        self.assets: dict[UUID, Asset] = {}
        self.referenced: set[UUID] = set()

    def add(self, asset: Asset) -> None:
        self.assets[asset.asset_id] = asset

    def get(self, asset_id: UUID) -> Asset | None:
        return self.assets.get(asset_id)

    def get_for_actor(
        self,
        *,
        actor: ActorContext,
        asset_id: UUID,
    ) -> Asset | None:
        asset = self.get(asset_id)
        return asset if asset is not None and self._visible(asset, actor) else None

    def get_for_actor_for_update(
        self,
        *,
        actor: ActorContext,
        asset_id: UUID,
    ) -> Asset | None:
        return self.get_for_actor(actor=actor, asset_id=asset_id)

    def list_by_ids_for_actor(
        self,
        *,
        actor: ActorContext,
        asset_ids: list[UUID],
    ) -> list[Asset]:
        return [
            asset
            for asset_id in asset_ids
            if (asset := self.get_for_actor(actor=actor, asset_id=asset_id)) is not None
        ]

    def is_referenced(self, asset_id: UUID) -> bool:
        return asset_id in self.referenced

    def delete(self, asset: Asset) -> None:
        del self.assets[asset.asset_id]

    def list(
        self,
        *,
        actor: ActorContext,
        offset: int,
        limit: int,
        search: str | None,
    ) -> list[Asset]:
        values = [
            asset
            for asset in reversed(self.assets.values())
            if self._visible(asset, actor)
        ]
        if search:
            values = [
                asset
                for asset in values
                if search.casefold() in asset.original_filename.casefold()
            ]
        return values[offset : offset + limit]

    def count(self, *, actor: ActorContext, search: str | None) -> int:
        return len(
            self.list(
                actor=actor,
                offset=0,
                limit=10_000,
                search=search,
            ),
        )

    @staticmethod
    def _visible(asset: Asset, actor: ActorContext) -> bool:
        if actor.data_scope is DataScope.ALL:
            return True
        if asset.team_id != actor.team_id:
            return False
        if actor.data_scope is DataScope.TEAM:
            return True
        return asset.created_by_user_id == actor.user_id


def make_service(
    tmp_path: Path,
    *,
    max_bytes: int = 1024,
) -> tuple[AssetService, FakeAssetRepository, FakeSession]:
    repository = FakeAssetRepository()
    session = FakeSession()
    return (
        AssetService(
            session,  # type: ignore[arg-type]
            repository,  # type: ignore[arg-type]
            LocalAssetStorage(tmp_path / "assets", max_bytes),
            Settings(asset_storage_dir=tmp_path / "unused"),
        ),
        repository,
        session,
    )


def test_upload_saves_file_hash_and_metadata_before_commit(tmp_path: Path) -> None:
    service, repository, session = make_service(tmp_path)
    payload = b"\xff\xd8\xff" + b"safe-test-image"

    asset = service.upload(
        actor=ACTOR,
        original_filename="test-01.jpg",
        content_type="image/jpeg",
        stream=BytesIO(payload),
    )

    assert repository.assets == {asset.asset_id: asset}
    assert asset.original_filename == "test-01.jpg"
    assert asset.media_type == AssetMediaType.IMAGE.value
    assert asset.source_type == AssetSourceType.UPLOAD.value
    assert asset.team_id == ACTOR.team_id
    assert asset.created_by_user_id == ACTOR.user_id
    assert asset.content_type == "image/jpeg"
    assert asset.size_bytes == len(payload)
    assert asset.sha256 == hashlib.sha256(payload).hexdigest()
    _, content = service.get_content(ACTOR, asset.asset_id)
    with content:
        assert content.read() == payload
    assert session.commits == 1


@pytest.mark.parametrize(
    ("filename", "content_type", "payload"),
    [
        ("test.gif", "image/gif", b"GIF89a"),
        ("fake.jpg", "image/jpeg", b"not-an-image"),
        ("mismatch.png", "image/png", b"\xff\xd8\xffpayload"),
    ],
)
def test_upload_rejects_unsupported_or_mismatched_images(
    tmp_path: Path,
    filename: str,
    content_type: str,
    payload: bytes,
) -> None:
    service, repository, _ = make_service(tmp_path)

    with pytest.raises(AssetTypeUnsupportedError):
        service.upload(
            actor=ACTOR,
            original_filename=filename,
            content_type=content_type,
            stream=BytesIO(payload),
        )

    assert repository.assets == {}


def test_upload_rejects_oversized_image_without_file_or_row(tmp_path: Path) -> None:
    service, repository, _ = make_service(tmp_path, max_bytes=8)

    with pytest.raises(AssetTooLargeError):
        service.upload(
            actor=ACTOR,
            original_filename="large.jpg",
            content_type="image/jpeg",
            stream=BytesIO(b"\xff\xd8\xff" + b"x" * 20),
        )

    assert repository.assets == {}
    assert list((tmp_path / "assets").iterdir()) == []


def test_list_supports_filename_search_and_pagination(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path)
    service.upload(
        actor=ACTOR,
        original_filename="first.jpg",
        content_type="image/jpeg",
        stream=BytesIO(b"\xff\xd8\xfffirst"),
    )
    service.upload(
        actor=ACTOR,
        original_filename="second.png",
        content_type="image/png",
        stream=BytesIO(b"\x89PNG\r\n\x1a\nsecond"),
    )

    items, total = service.list(
        actor=ACTOR,
        page=1,
        page_size=20,
        search="SECOND",
    )

    assert total == 1
    assert [asset.original_filename for asset in items] == ["second.png"]


def test_internal_create_does_not_depend_on_http_upload_file(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path)

    asset = service.create(
        original_filename="generated.png",
        content_type="image/png",
        stream=BytesIO(b"\x89PNG\r\n\x1a\ngenerated"),
        media_type=AssetMediaType.IMAGE,
        source_type=AssetSourceType.AI_GENERATED,
        ownership=SYSTEM_OWNERSHIP,
    )

    assert asset.media_type == AssetMediaType.IMAGE.value
    assert asset.source_type == AssetSourceType.AI_GENERATED.value
    assert asset.team_id == ACTOR.team_id
    assert asset.created_by_user_id is None
    assert asset.storage_key.endswith(".png")


def test_current_asset_creation_does_not_enable_video_upload(tmp_path: Path) -> None:
    service, repository, _ = make_service(tmp_path)

    with pytest.raises(AssetTypeUnsupportedError):
        service.create(
            original_filename="future.mp4",
            content_type="video/mp4",
            stream=BytesIO(b"future-video"),
            media_type=AssetMediaType.VIDEO,
            source_type=AssetSourceType.IMPORTED,
            ownership=SYSTEM_OWNERSHIP,
        )

    assert repository.assets == {}


def test_same_filename_creates_independent_asset_records(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path)
    payload = b"\xff\xd8\xffsame-content"

    first = service.upload(
        actor=ACTOR,
        original_filename="same.jpg",
        content_type="image/jpeg",
        stream=BytesIO(payload),
    )
    second = service.upload(
        actor=ACTOR,
        original_filename="same.jpg",
        content_type="image/jpeg",
        stream=BytesIO(payload),
    )

    assert first.asset_id != second.asset_id
    assert first.storage_key != second.storage_key
    assert first.sha256 == second.sha256


def test_path_components_are_not_used_as_storage_key(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path)

    asset = service.upload(
        actor=ACTOR,
        original_filename="../../outside.png",
        content_type="image/png",
        stream=BytesIO(b"\x89PNG\r\n\x1a\nsafe"),
    )

    assert asset.original_filename == "outside.png"
    assert "/" not in asset.storage_key
    assert "\\" not in asset.storage_key
    assert service.storage.exists(asset.storage_key)


def test_storage_failure_does_not_create_asset_row(tmp_path: Path) -> None:
    invalid_root = tmp_path / "not-a-directory"
    invalid_root.write_text("occupied", encoding="utf-8")
    repository = FakeAssetRepository()
    session = FakeSession()
    service = AssetService(
        session,  # type: ignore[arg-type]
        repository,  # type: ignore[arg-type]
        LocalAssetStorage(invalid_root, 1024),
        Settings(asset_storage_dir=tmp_path / "unused"),
    )

    with pytest.raises(AssetStorageError):
        service.upload(
            actor=ACTOR,
            original_filename="image.jpg",
            content_type="image/jpeg",
            stream=BytesIO(b"\xff\xd8\xffpayload"),
        )

    assert repository.assets == {}
    assert session.commits == 0


def test_source_stream_failure_is_mapped_without_creating_file(tmp_path: Path) -> None:
    class FailingStream(BytesIO):
        def read(self, size: int = -1) -> bytes:
            del size
            raise OSError("source unavailable")

    service, repository, session = make_service(tmp_path)

    with pytest.raises(AssetStorageError):
        service.upload(
            actor=ACTOR,
            original_filename="image.jpg",
            content_type="image/jpeg",
            stream=FailingStream(),
        )

    assert repository.assets == {}
    assert session.commits == 0
    assert not (tmp_path / "assets").exists()


def test_database_failure_removes_newly_stored_file(tmp_path: Path) -> None:
    class FailingCommitSession(FakeSession):
        def commit(self) -> None:
            raise RuntimeError("database unavailable")

    repository = FakeAssetRepository()
    session = FailingCommitSession()
    storage = LocalAssetStorage(tmp_path / "assets", 1024)
    service = AssetService(
        session,  # type: ignore[arg-type]
        repository,  # type: ignore[arg-type]
        storage,
        Settings(asset_storage_dir=tmp_path / "unused"),
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        service.upload(
            actor=ACTOR,
            original_filename="image.jpg",
            content_type="image/jpeg",
            stream=BytesIO(b"\xff\xd8\xffpayload"),
        )

    assert session.rollbacks == 1
    assert list((tmp_path / "assets").iterdir()) == []


def test_refresh_failure_before_commit_removes_newly_stored_file(
    tmp_path: Path,
) -> None:
    class FailingRefreshSession(FakeSession):
        def refresh(self, entity: object) -> None:
            del entity
            raise RuntimeError("database refresh unavailable")

    repository = FakeAssetRepository()
    session = FailingRefreshSession()
    storage = LocalAssetStorage(tmp_path / "assets", 1024)
    service = AssetService(
        session,  # type: ignore[arg-type]
        repository,  # type: ignore[arg-type]
        storage,
        Settings(asset_storage_dir=tmp_path / "unused"),
    )

    with pytest.raises(RuntimeError, match="database refresh unavailable"):
        service.upload(
            actor=ACTOR,
            original_filename="image.jpg",
            content_type="image/jpeg",
            stream=BytesIO(b"\xff\xd8\xffpayload"),
        )

    assert session.commits == 0
    assert session.rollbacks == 1
    assert list((tmp_path / "assets").iterdir()) == []


def test_transactional_asset_stage_compensates_when_outer_business_write_fails(
    tmp_path: Path,
) -> None:
    service, _, session = make_service(tmp_path)

    with pytest.raises(RuntimeError, match="item binding failed"):
        with service.stage_for_transaction(
            original_filename="generated.png",
            content_type="image/png",
            stream=BytesIO(b"\x89PNG\r\n\x1a\ngenerated"),
            media_type=AssetMediaType.IMAGE,
            source_type=AssetSourceType.AI_GENERATED,
            ownership=HUMAN_OWNERSHIP,
        ):
            raise RuntimeError("item binding failed")

    assert session.commits == 0
    assert session.rollbacks == 1
    assert list((tmp_path / "assets").iterdir()) == []


def test_delete_is_blocked_when_any_task_references_asset(tmp_path: Path) -> None:
    service, repository, session = make_service(tmp_path)
    asset = service.upload(
        actor=ACTOR,
        original_filename="in-use.webp",
        content_type="image/webp",
        stream=BytesIO(b"RIFF\x04\x00\x00\x00WEBPdata"),
    )
    repository.referenced.add(asset.asset_id)

    with pytest.raises(AssetInUseError):
        service.delete(ACTOR, asset.asset_id)

    assert repository.get(asset.asset_id) is asset
    assert service.storage.exists(asset.storage_key)
    assert session.rollbacks == 1


def test_delete_unreferenced_asset_removes_row_and_file(tmp_path: Path) -> None:
    service, repository, _ = make_service(tmp_path)
    asset = service.upload(
        actor=ACTOR,
        original_filename="unused.jpg",
        content_type="image/jpeg",
        stream=BytesIO(b"\xff\xd8\xffunused"),
    )
    storage_key = asset.storage_key

    service.delete(ACTOR, asset.asset_id)

    assert repository.get(asset.asset_id) is None
    assert not service.storage.exists(storage_key)
