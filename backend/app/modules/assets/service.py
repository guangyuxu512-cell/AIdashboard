from pathlib import Path
from typing import BinaryIO
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.modules.assets.exceptions import (
    AssetInUseError,
    AssetNotFoundError,
    AssetStorageError,
)
from app.modules.assets.models import Asset
from app.modules.assets.repository import AssetRepository
from app.modules.assets.storage import AssetStorage, normalize_original_filename
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
        self.storage = storage or AssetStorage(
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
        filename, _ = normalize_original_filename(original_filename)
        asset_id = generate_id()
        storage_key, detected_type, size_bytes, sha256 = self.storage.save(
            asset_id=asset_id,
            original_filename=filename,
            declared_content_type=content_type,
            stream=stream,
        )
        asset = Asset(
            asset_id=asset_id,
            original_filename=filename,
            storage_key=storage_key,
            content_type=detected_type,
            size_bytes=size_bytes,
            sha256=sha256,
        )
        try:
            self.repository.add(asset)
            self.session.commit()
            self.session.refresh(asset)
        except Exception:
            self.session.rollback()
            self.storage.remove(storage_key)
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

    def get_content(self, asset_id: UUID) -> tuple[Asset, Path]:
        asset = self.repository.get(asset_id)
        if asset is None:
            raise AssetNotFoundError()
        path = self.storage.path_for(asset.storage_key)
        if not path.is_file():
            raise AssetStorageError()
        return asset, path

    def get_worker_content(
        self,
        principal: WorkerPrincipal,
        *,
        task_id: UUID,
        asset_id: UUID,
    ) -> tuple[Asset, Path]:
        asset = self.repository.get_for_worker_task(
            task_id=task_id,
            device_id=principal.device_id,
            asset_id=asset_id,
        )
        if asset is None:
            raise AssetNotFoundError()
        path = self.storage.path_for(asset.storage_key)
        if not path.is_file():
            raise AssetStorageError()
        return asset, path

    def delete(self, asset_id: UUID) -> None:
        asset = self.repository.get_for_update(asset_id)
        if asset is None:
            raise AssetNotFoundError()
        if self.repository.is_referenced(asset_id):
            self.session.rollback()
            raise AssetInUseError()
        self.repository.delete(asset)
        self.session.commit()
        self.storage.remove(asset.storage_key)
