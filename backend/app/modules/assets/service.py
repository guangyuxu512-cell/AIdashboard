from collections.abc import Iterator
from typing import BinaryIO
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.modules.assets.enums import AssetMediaType, AssetSourceType
from app.modules.assets.exceptions import (
    AssetInUseError,
    AssetNotFoundError,
    AssetStorageError,
    AssetTypeUnsupportedError,
)
from app.modules.assets.models import Asset
from app.modules.assets.repository import AssetRepository
from app.modules.assets.storage import AssetStorage, LocalAssetStorage
from app.modules.assets.validation import (
    normalize_original_filename,
    validate_image_content,
)
from app.modules.workers.service import WorkerPrincipal
from app.shared.identifiers import generate_id


class AssetService:
    def __init__(
        self,
        session: Session,
        repository: AssetRepository | None = None,
        storage: AssetStorage | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or AssetRepository(session)
        resolved_settings = settings or get_settings()
        self.storage: AssetStorage = storage or LocalAssetStorage(
            resolved_settings.asset_storage_dir,
            resolved_settings.asset_max_upload_bytes,
        )

    def upload(
        self,
        *,
        original_filename: str | None,
        content_type: str | None,
        stream: BinaryIO,
    ) -> Asset:
        return self.create(
            original_filename=original_filename,
            content_type=content_type,
            stream=stream,
            media_type=AssetMediaType.IMAGE,
            source_type=AssetSourceType.UPLOAD,
        )

    def create(
        self,
        *,
        original_filename: str | None,
        content_type: str | None,
        stream: BinaryIO,
        media_type: AssetMediaType,
        source_type: AssetSourceType,
    ) -> Asset:
        if media_type is not AssetMediaType.IMAGE:
            raise AssetTypeUnsupportedError()
        filename, suffix = normalize_original_filename(original_filename)
        try:
            header = stream.read(16)
        except OSError as error:
            raise AssetStorageError() from error
        detected_type = validate_image_content(
            filename_suffix=suffix,
            declared_content_type=content_type,
            header=header,
        )
        asset_id = generate_id()
        stored = self.storage.store(
            asset_id=asset_id,
            suffix=suffix,
            chunks=_stream_chunks(stream, header),
        )
        asset = Asset(
            asset_id=asset_id,
            original_filename=filename,
            storage_key=stored.storage_key,
            media_type=media_type.value,
            source_type=source_type.value,
            content_type=detected_type,
            size_bytes=stored.size_bytes,
            sha256=stored.sha256,
        )
        try:
            self.repository.add(asset)
            self.session.flush()
            self.session.refresh(asset)
            self.session.commit()
        except Exception:
            self.session.rollback()
            self.storage.delete(stored.storage_key)
            raise
        return asset

    def list(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
    ) -> tuple[list[Asset], int]:
        normalized_search = search.strip() if search else None
        return (
            self.repository.list(
                offset=(page - 1) * page_size,
                limit=page_size,
                search=normalized_search or None,
            ),
            self.repository.count(search=normalized_search or None),
        )

    def get_content(self, asset_id: UUID) -> tuple[Asset, BinaryIO]:
        asset = self.repository.get(asset_id)
        if asset is None:
            raise AssetNotFoundError()
        if not self.storage.exists(asset.storage_key):
            raise AssetStorageError()
        return asset, self.storage.open(asset.storage_key)

    def get_worker_content(
        self,
        principal: WorkerPrincipal,
        *,
        task_id: UUID,
        asset_id: UUID,
    ) -> tuple[Asset, BinaryIO]:
        asset = self.repository.get_for_worker_task(
            task_id=task_id,
            device_id=principal.device_id,
            asset_id=asset_id,
        )
        if asset is None:
            raise AssetNotFoundError()
        if not self.storage.exists(asset.storage_key):
            raise AssetStorageError()
        return asset, self.storage.open(asset.storage_key)

    def delete(self, asset_id: UUID) -> None:
        asset = self.repository.get_for_update(asset_id)
        if asset is None:
            raise AssetNotFoundError()
        if self.repository.is_referenced(asset_id):
            self.session.rollback()
            raise AssetInUseError()
        self.repository.delete(asset)
        self.session.commit()
        self.storage.delete(asset.storage_key)


def _stream_chunks(stream: BinaryIO, header: bytes) -> Iterator[bytes]:
    yield header
    while chunk := stream.read(64 * 1024):
        yield chunk
