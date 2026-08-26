from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.core.config import Settings
from app.modules.assets.exceptions import (
    AssetInUseError,
    AssetTooLargeError,
    AssetTypeUnsupportedError,
)
from app.modules.assets.models import Asset
from app.modules.assets.service import AssetService
from app.modules.assets.storage import AssetStorage
from tests.support import FakeSession


class FakeAssetRepository:
    def __init__(self) -> None:
        self.assets: dict[UUID, Asset] = {}
        self.referenced: set[UUID] = set()

    def add(self, asset: Asset) -> None:
        self.assets[asset.asset_id] = asset

    def get(self, asset_id: UUID) -> Asset | None:
        return self.assets.get(asset_id)

    def get_for_update(self, asset_id: UUID) -> Asset | None:
        return self.get(asset_id)

    def is_referenced(self, asset_id: UUID) -> bool:
        return asset_id in self.referenced

    def delete(self, asset: Asset) -> None:
        del self.assets[asset.asset_id]

    def list(self, *, offset: int, limit: int, search: str | None) -> list[Asset]:
        values = list(reversed(self.assets.values()))
        if search:
            values = [
                asset
                for asset in values
                if search.casefold() in asset.original_filename.casefold()
            ]
        return values[offset : offset + limit]

    def count(self, *, search: str | None) -> int:
        return len(self.list(offset=0, limit=10_000, search=search))


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
            AssetStorage(tmp_path / "assets", max_bytes),
            Settings(asset_storage_dir=tmp_path / "unused"),
        ),
        repository,
        session,
    )


def test_upload_saves_file_hash_and_metadata_before_commit(tmp_path: Path) -> None:
    service, repository, session = make_service(tmp_path)
    payload = b"\xff\xd8\xff" + b"safe-test-image"

    asset = service.upload(
        original_filename="test-01.jpg",
        content_type="image/jpeg",
        stream=BytesIO(payload),
    )

    assert repository.assets == {asset.asset_id: asset}
    assert asset.original_filename == "test-01.jpg"
    assert asset.content_type == "image/jpeg"
    assert asset.size_bytes == len(payload)
    assert len(asset.sha256) == 64
    assert service.get_content(asset.asset_id)[1].read_bytes() == payload
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
            original_filename=filename,
            content_type=content_type,
            stream=BytesIO(payload),
        )

    assert repository.assets == {}


def test_upload_rejects_oversized_image_without_file_or_row(tmp_path: Path) -> None:
    service, repository, _ = make_service(tmp_path, max_bytes=8)

    with pytest.raises(AssetTooLargeError):
        service.upload(
            original_filename="large.jpg",
            content_type="image/jpeg",
            stream=BytesIO(b"\xff\xd8\xff" + b"x" * 20),
        )

    assert repository.assets == {}
    assert list((tmp_path / "assets").iterdir()) == []


def test_list_supports_filename_search_and_pagination(tmp_path: Path) -> None:
    service, _, _ = make_service(tmp_path)
    service.upload(
        original_filename="first.jpg",
        content_type="image/jpeg",
        stream=BytesIO(b"\xff\xd8\xfffirst"),
    )
    service.upload(
        original_filename="second.png",
        content_type="image/png",
        stream=BytesIO(b"\x89PNG\r\n\x1a\nsecond"),
    )

    items, total = service.list(page=1, page_size=20, search="SECOND")

    assert total == 1
    assert [asset.original_filename for asset in items] == ["second.png"]


def test_delete_is_blocked_when_any_task_references_asset(tmp_path: Path) -> None:
    service, repository, session = make_service(tmp_path)
    asset = service.upload(
        original_filename="in-use.webp",
        content_type="image/webp",
        stream=BytesIO(b"RIFF\x04\x00\x00\x00WEBPdata"),
    )
    repository.referenced.add(asset.asset_id)

    with pytest.raises(AssetInUseError):
        service.delete(asset.asset_id)

    assert repository.get(asset.asset_id) is asset
    assert service.get_content(asset.asset_id)[1].is_file()
    assert session.rollbacks == 1


def test_delete_unreferenced_asset_removes_row_and_file(tmp_path: Path) -> None:
    service, repository, _ = make_service(tmp_path)
    asset = service.upload(
        original_filename="unused.jpg",
        content_type="image/jpeg",
        stream=BytesIO(b"\xff\xd8\xffunused"),
    )
    path = service.get_content(asset.asset_id)[1]

    service.delete(asset.asset_id)

    assert repository.get(asset.asset_id) is None
    assert not path.exists()
