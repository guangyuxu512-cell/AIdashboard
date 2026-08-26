from collections.abc import Iterable
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import tempfile
from typing import BinaryIO, Protocol
from uuid import UUID

from app.modules.assets.exceptions import (
    AssetStorageError,
    AssetTooLargeError,
)


@dataclass(frozen=True)
class StoredAsset:
    storage_key: str
    size_bytes: int
    sha256: str


class AssetStorage(Protocol):
    def store(
        self,
        *,
        asset_id: UUID,
        suffix: str,
        chunks: Iterable[bytes],
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
    ) -> StoredAsset:
        storage_key = f"{asset_id.hex}{suffix}"
        descriptor = -1
        temporary_path: Path | None = None
        final_path = self._path_for(storage_key)
        try:
            self.root.mkdir(parents=True, exist_ok=True)
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
            self._path_for(storage_key).unlink(missing_ok=True)
        except OSError as error:
            raise AssetStorageError() from error

    def exists(self, storage_key: str) -> bool:
        try:
            return self._path_for(storage_key).is_file()
        except OSError as error:
            raise AssetStorageError() from error

    def _path_for(self, storage_key: str) -> Path:
        candidate = (self.root / storage_key).resolve()
        if candidate.parent != self.root:
            raise AssetStorageError()
        return candidate
