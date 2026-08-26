import hashlib
from pathlib import Path
from uuid import uuid4

import pytest

from app.modules.assets.exceptions import AssetStorageError, AssetTooLargeError
from app.modules.assets.storage import LocalAssetStorage


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
