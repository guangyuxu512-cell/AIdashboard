import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Protocol

from app.contracts import TaskAsset, WorkerTask
from app.local_input import LocalInputPreparationError, ensure_images_directory


_MANIFEST_NAME = ".ecommerce-worker-images.json"
_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED_NAMES = {
    "aux",
    "con",
    "nul",
    "prn",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}


class TaskAssetDownloader(Protocol):
    async def download_task_asset(self, download_path: str) -> bytes: ...


class TaskImagePreparationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class TaskImagePreparer:
    """Replace only the image files managed by this Worker for each Task."""

    def __init__(self, images_dir: Path, downloader: TaskAssetDownloader) -> None:
        self.images_dir = images_dir.resolve()
        self.downloader = downloader
        self.manifest_path = self.images_dir / _MANIFEST_NAME

    async def prepare(self, task: WorkerTask) -> list[Path]:
        try:
            ensure_images_directory(self.images_dir)
            self._clear_managed_files()
        except LocalInputPreparationError as error:
            raise TaskImagePreparationError(error.code, error.message) from error
        except (OSError, ValueError) as error:
            raise TaskImagePreparationError(
                "TASK_IMAGES_CLEANUP_FAILED",
                "图片目录清理失败",
            ) from error

        prepared: list[Path] = []
        filenames = allocate_task_filenames(task.assets)
        try:
            for asset, filename in zip(
                sorted(task.assets, key=lambda item: item.position),
                filenames,
                strict=True,
            ):
                payload = await self.downloader.download_task_asset(
                    asset.download_path,
                )
                self._validate_payload(asset, payload)
                destination = self.images_dir / filename
                self._write_atomic(destination, payload)
                prepared.append(destination)
            self._write_manifest([path.name for path in prepared])
            return prepared
        except TaskImagePreparationError:
            self._remove_paths(prepared)
            self._write_manifest([])
            raise
        except Exception as error:
            self._remove_paths(prepared)
            self._write_manifest([])
            failed_name = (
                asset.filename if "asset" in locals() else "未知图片"
            )
            raise TaskImagePreparationError(
                "TASK_IMAGE_DOWNLOAD_FAILED",
                f"图片准备失败：{failed_name}",
            ) from error

    def _clear_managed_files(self) -> None:
        filenames: list[str] = []
        if self.manifest_path.is_file():
            try:
                payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
                raw_filenames = payload.get("files", [])
                if isinstance(raw_filenames, list):
                    filenames = [item for item in raw_filenames if isinstance(item, str)]
            except (OSError, ValueError, TypeError) as error:
                raise OSError("managed image manifest is invalid") from error
        for filename in filenames:
            candidate = (self.images_dir / filename).resolve()
            if candidate.parent == self.images_dir and candidate.name != _MANIFEST_NAME:
                candidate.unlink(missing_ok=True)
        self.manifest_path.unlink(missing_ok=True)

    @staticmethod
    def _validate_payload(asset: TaskAsset, payload: bytes) -> None:
        if len(payload) != asset.size_bytes:
            raise TaskImagePreparationError(
                "TASK_IMAGE_SIZE_MISMATCH",
                f"图片准备失败：{asset.filename}",
            )
        if hashlib.sha256(payload).hexdigest().lower() != asset.sha256.lower():
            raise TaskImagePreparationError(
                "TASK_IMAGE_HASH_MISMATCH",
                f"图片准备失败：{asset.filename}",
            )

    def _write_atomic(self, destination: Path, payload: bytes) -> None:
        descriptor = -1
        temporary_path: Path | None = None
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{destination.name}-",
                suffix=".part",
                dir=self.images_dir,
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(descriptor, "wb") as output:
                descriptor = -1
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            temporary_path.replace(destination)
        except OSError as error:
            raise TaskImagePreparationError(
                "TASK_IMAGE_WRITE_FAILED",
                f"图片准备失败：{destination.name}",
            ) from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def _write_manifest(self, filenames: list[str]) -> None:
        descriptor = -1
        temporary_path: Path | None = None
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=".ecommerce-worker-images-",
                suffix=".tmp",
                dir=self.images_dir,
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                descriptor = -1
                json.dump({"files": filenames}, output, ensure_ascii=False)
                output.flush()
                os.fsync(output.fileno())
            temporary_path.replace(self.manifest_path)
        except OSError as error:
            raise TaskImagePreparationError(
                "TASK_IMAGES_MANIFEST_WRITE_FAILED",
                "图片目录状态写入失败",
            ) from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _remove_paths(paths: list[Path]) -> None:
        for path in paths:
            path.unlink(missing_ok=True)


def allocate_task_filenames(assets: list[TaskAsset]) -> list[str]:
    allocated: list[str] = []
    used: set[str] = set()
    for asset in sorted(assets, key=lambda item: item.position):
        sanitized = sanitize_filename(asset.filename)
        stem = Path(sanitized).stem
        suffix = Path(sanitized).suffix
        candidate = sanitized
        duplicate = 2
        while candidate.casefold() in used:
            candidate = f"{stem}__{duplicate}{suffix}"
            duplicate += 1
        used.add(candidate.casefold())
        allocated.append(candidate)
    return allocated


def sanitize_filename(value: str) -> str:
    normalized = value.replace("\\", "/").rsplit("/", 1)[-1]
    normalized = _INVALID_FILENAME.sub("_", normalized).strip(" .")
    suffix = Path(normalized).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".img"
    stem = Path(normalized).stem.strip(" .") or "image"
    if stem.casefold() in _WINDOWS_RESERVED_NAMES:
        stem = f"_{stem}"
    max_stem_length = max(1, 180 - len(suffix))
    return f"{stem[:max_stem_length]}{suffix}"
