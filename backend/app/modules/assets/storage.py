from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import os
from pathlib import Path, PurePosixPath
import tempfile
from typing import BinaryIO, Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from app.core.config import Settings
from app.modules.assets.exceptions import (
    AssetStorageError,
    AssetStorageUnavailableError,
    AssetTooLargeError,
)


MOUNTED_STORAGE_MARKER_NAME = ".control-center-asset-storage-v1"
MOUNTED_STORAGE_MARKER_CONTENT = b"control-center-asset-storage-v1\n"
ASSET_STORAGE_TIMEZONE_NAME = "Asia/Shanghai"
_ASSET_STORAGE_TIMEZONE = ZoneInfo(ASSET_STORAGE_TIMEZONE_NAME)


@dataclass(frozen=True)
class StoredAsset:
    storage_key: str
    size_bytes: int
    sha256: str


class AssetStorage(Protocol):
    def verify_ready(self) -> None: ...

    def store(
        self,
        *,
        asset_id: UUID,
        suffix: str,
        chunks: Iterable[bytes],
        storage_key: str | None = None,
    ) -> StoredAsset: ...

    def open(self, storage_key: str) -> BinaryIO: ...

    def delete(self, storage_key: str) -> None: ...

    def exists(self, storage_key: str) -> bool: ...


class LocalAssetStorage:
    def __init__(self, root: Path, max_upload_bytes: int) -> None:
        self.root = root.resolve()
        self.max_upload_bytes = max_upload_bytes

    def store(
        self,
        *,
        asset_id: UUID,
        suffix: str,
        chunks: Iterable[bytes],
        storage_key: str | None = None,
    ) -> StoredAsset:
        storage_key = storage_key or asset_storage_key(asset_id, suffix)
        descriptor = -1
        temporary_path: Path | None = None
        final_path = self._path_for(storage_key)
        try:
            self._prepare_root_for_store()
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{asset_id.hex}-",
                suffix=".upload",
                dir=self.root,
            )
            temporary_path = Path(temporary_name)
            digest = hashlib.sha256()
            size = 0
            with os.fdopen(descriptor, "wb") as output:
                descriptor = -1
                for chunk in chunks:
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > self.max_upload_bytes:
                        raise AssetTooLargeError()
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            final_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path.replace(final_path)
            return StoredAsset(
                storage_key=storage_key,
                size_bytes=size,
                sha256=digest.hexdigest(),
            )
        except AssetTooLargeError:
            raise
        except OSError as error:
            raise AssetStorageError() from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def open(self, storage_key: str) -> BinaryIO:
        try:
            return self._path_for(storage_key).open("rb")
        except OSError as error:
            raise AssetStorageError() from error

    def delete(self, storage_key: str) -> None:
        try:
            path = self._path_for(storage_key)
            path.unlink(missing_ok=True)
            self._remove_empty_parent_directories(path.parent)
        except OSError as error:
            raise AssetStorageError() from error

    def exists(self, storage_key: str) -> bool:
        try:
            return self._path_for(storage_key).is_file()
        except OSError as error:
            raise AssetStorageError() from error

    def verify_ready(self) -> None:
        try:
            self._prepare_root_for_store()
        except OSError as error:
            raise AssetStorageError() from error

    def _prepare_root_for_store(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, storage_key: str) -> Path:
        if not _is_supported_storage_key(storage_key):
            raise AssetStorageError()
        candidate = (self.root / PurePosixPath(storage_key)).resolve()
        if self.root not in candidate.parents:
            raise AssetStorageError()
        return candidate

    def _remove_empty_parent_directories(self, directory: Path) -> None:
        while directory != self.root:
            try:
                directory.rmdir()
            except OSError:
                return
            directory = directory.parent


def asset_storage_key(
    asset_id: UUID,
    suffix: str,
    *,
    written_at: datetime | None = None,
) -> str:
    """Return a stable dated key for a new original Asset file."""

    instant = written_at or datetime.now(UTC)
    if instant.tzinfo is None:
        raise ValueError("Asset storage timestamp must include a timezone")
    date_directory = instant.astimezone(_ASSET_STORAGE_TIMEZONE).strftime("%Y/%m/%d")
    return f"{date_directory}/{asset_id.hex}{suffix}"


def _is_supported_storage_key(storage_key: str) -> bool:
    if not storage_key or "\\" in storage_key:
        return False
    path = PurePosixPath(storage_key)
    parts = path.parts
    if path.is_absolute() or any(part in {"", ".", ".."} for part in parts):
        return False
    if len(parts) == 1:
        return True
    if not (
        len(parts) == 4
        and len(parts[0]) == 4
        and all(part.isdigit() for part in parts[:3])
        and len(parts[1]) == 2
        and len(parts[2]) == 2
        and bool(parts[3])
    ):
        return False
    try:
        datetime(int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return False
    return True


class MountedAssetStorage(LocalAssetStorage):
    """Asset storage rooted at an already-mounted, verified host directory."""

    def _prepare_root_for_store(self) -> None:
        self._assert_mount_ready()

    def verify_ready(self) -> None:
        self._assert_mount_ready()

    def open(self, storage_key: str) -> BinaryIO:
        self._assert_mount_ready()
        return super().open(storage_key)

    def delete(self, storage_key: str) -> None:
        self._assert_mount_ready()
        super().delete(storage_key)

    def exists(self, storage_key: str) -> bool:
        self._assert_mount_ready()
        return super().exists(storage_key)

    def _assert_mount_ready(self) -> None:
        try:
            marker_path = self.root / MOUNTED_STORAGE_MARKER_NAME
            if (
                not self.root.is_dir()
                or marker_path.read_bytes() != MOUNTED_STORAGE_MARKER_CONTENT
                or not os.access(self.root, os.R_OK | os.W_OK | os.X_OK)
            ):
                raise AssetStorageUnavailableError()
        except AssetStorageUnavailableError:
            raise
        except OSError as error:
            raise AssetStorageUnavailableError() from error


def create_asset_storage(settings: Settings) -> AssetStorage:
    storage_type = (
        MountedAssetStorage
        if settings.asset_storage_mode == "mounted"
        else LocalAssetStorage
    )
    return storage_type(
        settings.asset_storage_dir,
        settings.asset_max_upload_bytes,
    )


def verify_asset_storage(settings: Settings) -> None:
    create_asset_storage(settings).verify_ready()
