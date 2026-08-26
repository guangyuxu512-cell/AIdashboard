import hashlib
import os
from pathlib import Path
import tempfile
from typing import BinaryIO
from uuid import UUID

from app.modules.assets.exceptions import (
    AssetStorageError,
    AssetTooLargeError,
    AssetTypeUnsupportedError,
)


ALLOWED_IMAGE_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def normalize_original_filename(value: str | None) -> tuple[str, str]:
    filename = (value or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not filename or len(filename) > 255:
        raise AssetTypeUnsupportedError()
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_IMAGE_TYPES:
        raise AssetTypeUnsupportedError()
    return filename, suffix


def detect_image_content_type(header: bytes) -> str | None:
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp"
    return None


class AssetStorage:
    def __init__(self, root: Path, max_upload_bytes: int) -> None:
        self.root = root.resolve()
        self.max_upload_bytes = max_upload_bytes

    def save(
        self,
        *,
        asset_id: UUID,
        original_filename: str,
        declared_content_type: str | None,
        stream: BinaryIO,
    ) -> tuple[str, str, int, str]:
        _, suffix = normalize_original_filename(original_filename)
        expected_content_type = ALLOWED_IMAGE_TYPES[suffix]
        if declared_content_type and declared_content_type.lower() != expected_content_type:
            raise AssetTypeUnsupportedError()
        storage_key = f"{asset_id.hex}{suffix}"
        self.root.mkdir(parents=True, exist_ok=True)
        descriptor = -1
        temporary_path: Path | None = None
        final_path = self.path_for(storage_key)
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{asset_id.hex}-",
                suffix=".upload",
                dir=self.root,
            )
            temporary_path = Path(temporary_name)
            digest = hashlib.sha256()
            size = 0
            header = bytearray()
            with os.fdopen(descriptor, "wb") as output:
                descriptor = -1
                while chunk := stream.read(64 * 1024):
                    size += len(chunk)
                    if size > self.max_upload_bytes:
                        raise AssetTooLargeError()
                    if len(header) < 16:
                        header.extend(chunk[: 16 - len(header)])
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            if size == 0 or detect_image_content_type(bytes(header)) != expected_content_type:
                raise AssetTypeUnsupportedError()
            temporary_path.replace(final_path)
            return storage_key, expected_content_type, size, digest.hexdigest()
        except (AssetTooLargeError, AssetTypeUnsupportedError):
            raise
        except OSError as error:
            raise AssetStorageError() from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def path_for(self, storage_key: str) -> Path:
        candidate = (self.root / storage_key).resolve()
        if candidate.parent != self.root:
            raise AssetStorageError()
        return candidate

    def remove(self, storage_key: str) -> None:
        try:
            self.path_for(storage_key).unlink(missing_ok=True)
        except OSError as error:
            raise AssetStorageError() from error
