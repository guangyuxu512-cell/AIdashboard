import hashlib
from pathlib import Path
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.assets.exceptions import (
    AssetStorageError,
    AssetStorageUnavailableError,
    AssetTooLargeError,
)
from app.modules.assets.storage import (
    MOUNTED_STORAGE_MARKER_CONTENT,
    MOUNTED_STORAGE_MARKER_NAME,
    LocalAssetStorage,
    MountedAssetStorage,
    create_asset_storage,
)


def test_local_storage_store_open_exists_delete_and_atomic_cleanup(
    tmp_path: Path,
) -> None:
    storage = LocalAssetStorage(tmp_path / "assets", 1024)
    payload = [b"first-", b"second"]

    stored = storage.store(asset_id=uuid4(), suffix=".png", chunks=payload)

    assert stored.size_bytes == len(b"first-second")
    assert stored.sha256 == hashlib.sha256(b"first-second").hexdigest()
    assert storage.exists(stored.storage_key)
    with storage.open(stored.storage_key) as content:
        assert content.read() == b"first-second"
    assert not list((tmp_path / "assets").glob("*.upload"))

    storage.delete(stored.storage_key)
    assert not storage.exists(stored.storage_key)


def test_local_storage_cleans_temporary_file_when_size_limit_fails(
    tmp_path: Path,
) -> None:
    storage = LocalAssetStorage(tmp_path / "assets", 4)

    with pytest.raises(AssetTooLargeError):
        storage.store(asset_id=uuid4(), suffix=".png", chunks=[b"12345"])

    assert list((tmp_path / "assets").iterdir()) == []


@pytest.mark.parametrize("storage_key", ["../outside.png", "nested/file.png"])
def test_local_storage_rejects_keys_outside_its_root(
    tmp_path: Path,
    storage_key: str,
) -> None:
    storage = LocalAssetStorage(tmp_path / "assets", 1024)

    with pytest.raises(AssetStorageError):
        storage.open(storage_key)
    with pytest.raises(AssetStorageError):
        storage.delete(storage_key)
    with pytest.raises(AssetStorageError):
        storage.exists(storage_key)


def test_mounted_storage_requires_marker_and_preserves_asset_contract(
    tmp_path: Path,
) -> None:
    root = tmp_path / "mounted-assets"
    root.mkdir()
    (root / MOUNTED_STORAGE_MARKER_NAME).write_bytes(MOUNTED_STORAGE_MARKER_CONTENT)
    storage = MountedAssetStorage(root, 1024)

    stored = storage.store(asset_id=uuid4(), suffix=".png", chunks=[b"mounted"])

    with storage.open(stored.storage_key) as content:
        assert content.read() == b"mounted"
    assert storage.exists(stored.storage_key)
    storage.delete(stored.storage_key)
    assert not storage.exists(stored.storage_key)
    assert (root / MOUNTED_STORAGE_MARKER_NAME).read_bytes() == (
        MOUNTED_STORAGE_MARKER_CONTENT
    )


def test_mounted_storage_refuses_missing_or_unverified_root(tmp_path: Path) -> None:
    root = tmp_path / "mounted-assets"
    storage = MountedAssetStorage(root, 1024)

    with pytest.raises(AssetStorageUnavailableError):
        storage.store(asset_id=uuid4(), suffix=".png", chunks=[b"must-not-write"])
    assert not root.exists()

    root.mkdir()
    with pytest.raises(AssetStorageUnavailableError):
        storage.verify_ready()
    assert list(root.iterdir()) == []


def test_mounted_storage_refuses_unwritable_mount(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "mounted-assets"
    root.mkdir()
    (root / MOUNTED_STORAGE_MARKER_NAME).write_bytes(MOUNTED_STORAGE_MARKER_CONTENT)
    storage = MountedAssetStorage(root, 1024)
    monkeypatch.setattr(
        "app.modules.assets.storage.os.access",
        lambda _path, _mode: False,
    )

    with pytest.raises(AssetStorageUnavailableError):
        storage.verify_ready()


def test_storage_factory_selects_mounted_mode(tmp_path: Path) -> None:
    storage = create_asset_storage(
        Settings(
            asset_storage_mode="mounted",
            asset_storage_dir=tmp_path / "mounted-assets",
        ),
    )

    assert isinstance(storage, MountedAssetStorage)
