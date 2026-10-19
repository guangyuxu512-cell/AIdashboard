from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.modules.access.contracts import ActorContext
from app.modules.assets.contracts import AssetOwnership
from app.modules.assets.enums import AssetMediaType, AssetSourceType
from app.modules.assets.exceptions import (
    AssetInUseError,
    AssetNotFoundError,
    AssetStorageError,
    AssetThumbnailUnavailableError,
    AssetTypeUnsupportedError,
)
from app.modules.assets.models import Asset
from app.modules.assets.repository import AssetRepository
from app.modules.assets.storage import AssetStorage, create_asset_storage
from app.modules.assets.thumbnails import (
    THUMBNAIL_SUFFIX,
    render_image_thumbnail,
    thumbnail_storage_key,
)
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
        self.storage: AssetStorage = storage or create_asset_storage(resolved_settings)

    def upload(
        self,
        *,
        actor: ActorContext,
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
            ownership=AssetOwnership(
                team_id=actor.require_team_id(),
                created_by_user_id=actor.user_id,
            ),
        )

    def create(
        self,
        *,
        original_filename: str | None,
        content_type: str | None,
        stream: BinaryIO,
        media_type: AssetMediaType,
        source_type: AssetSourceType,
        ownership: AssetOwnership,
    ) -> Asset:
        with self.stage_for_transaction(
            original_filename=original_filename,
            content_type=content_type,
            stream=stream,
            media_type=media_type,
            source_type=source_type,
            ownership=ownership,
        ) as asset:
            self.session.commit()
        return asset

    @contextmanager
    def stage_for_transaction(
        self,
        *,
        original_filename: str | None,
        content_type: str | None,
        stream: BinaryIO,
        media_type: AssetMediaType,
        source_type: AssetSourceType,
        ownership: AssetOwnership,
    ) -> Iterator[Asset]:
        """Stage an Asset inside a trusted caller-owned database transaction.

        The caller must commit before leaving the context. Any exception rolls the
        shared transaction back and removes the newly stored file.
        """

        if media_type is not AssetMediaType.IMAGE:
            raise AssetTypeUnsupportedError()
        filename, suffix = normalize_original_filename(original_filename)
        try:
            header = stream.read(16)
        except OSError as error:
            raise AssetStorageError() from error
        detected_type, detected_suffix = validate_image_content(
            filename_suffix=suffix,
            header=header,
        )
        if detected_suffix != suffix:
            stem = Path(filename).stem
            filename = f"{stem[:255 - len(detected_suffix)]}{detected_suffix}"
            suffix = detected_suffix
        asset_id = generate_id()
        stored = self.storage.store(
            asset_id=asset_id,
            suffix=suffix,
            chunks=_stream_chunks(stream, header),
        )
        thumbnail_key = thumbnail_storage_key(stored.storage_key)
        try:
            self._create_thumbnail(
                asset_id=asset_id,
                original_storage_key=stored.storage_key,
            )
        except (AssetStorageError, AssetThumbnailUnavailableError):
            # The original file is the Asset fact. A thumbnail can be retried on
            # its first authorized read without changing a successful upload or
            # AI generation into a permanently running task.
            pass
        asset = Asset(
            asset_id=asset_id,
            team_id=ownership.team_id,
            created_by_user_id=ownership.created_by_user_id,
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
            yield asset
        except Exception:
            self.session.rollback()
            self.storage.delete(stored.storage_key)
            self.storage.delete(thumbnail_key)
            raise

    def list(
        self,
        *,
        actor: ActorContext,
        page: int,
        page_size: int,
        search: str | None,
    ) -> tuple[list[Asset], int]:
        normalized_search = search.strip() if search else None
        return (
            self.repository.list(
                actor=actor,
                offset=(page - 1) * page_size,
                limit=page_size,
                search=normalized_search or None,
            ),
            self.repository.count(
                actor=actor,
                search=normalized_search or None,
            ),
        )

    def get_for_actor(self, actor: ActorContext, asset_id: UUID) -> Asset:
        asset = self.repository.get_for_actor(actor=actor, asset_id=asset_id)
        if asset is None:
            raise AssetNotFoundError()
        return asset

    def list_accessible_by_ids(
        self,
        actor: ActorContext,
        asset_ids: Sequence[UUID],
    ) -> Sequence[Asset]:
        """供未来可信业务 Service 校验 Reference Asset，Scope 始终落在 SQL。"""

        return self.repository.list_by_ids_for_actor(
            actor=actor,
            asset_ids=asset_ids,
        )

    def list_accessible_by_ids_for_update(
        self,
        actor: ActorContext,
        asset_ids: Sequence[UUID],
    ) -> Sequence[Asset]:
        """Scoped lookup with row locks for relationship-creating transactions."""

        return self.repository.list_by_ids_for_actor_for_update(
            actor=actor,
            asset_ids=asset_ids,
        )

    def get_content(
        self,
        actor: ActorContext,
        asset_id: UUID,
    ) -> tuple[Asset, BinaryIO]:
        asset = self.get_for_actor(actor, asset_id)
        if not self.storage.exists(asset.storage_key):
            raise AssetStorageError()
        return asset, self.storage.open(asset.storage_key)

    def get_thumbnail(
        self,
        actor: ActorContext,
        asset_id: UUID,
    ) -> tuple[Asset, BinaryIO, int]:
        asset = self.get_for_actor(actor, asset_id)
        key = thumbnail_storage_key(asset.storage_key)
        if not self.storage.exists(key):
            self._create_thumbnail(
                asset_id=asset.asset_id,
                original_storage_key=asset.storage_key,
            )
        if not self.storage.exists(key):
            raise AssetThumbnailUnavailableError()

        content = self.storage.open(key)
        try:
            size = content.seek(0, 2)
            content.seek(0)
        except OSError as error:
            content.close()
            raise AssetStorageError() from error
        return asset, content, size

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

    def delete(self, actor: ActorContext, asset_id: UUID) -> None:
        asset = self.repository.get_for_actor_for_update(
            actor=actor,
            asset_id=asset_id,
        )
        if asset is None:
            raise AssetNotFoundError()
        if self.repository.is_referenced(asset_id):
            self.session.rollback()
            raise AssetInUseError()
        try:
            self.storage.verify_ready()
        except Exception:
            self.session.rollback()
            raise
        try:
            self.repository.delete(asset)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        self.storage.delete(asset.storage_key)
        self.storage.delete(thumbnail_storage_key(asset.storage_key))

    def _create_thumbnail(
        self,
        *,
        asset_id: UUID,
        original_storage_key: str,
    ) -> None:
        with self.storage.open(original_storage_key) as source:
            thumbnail = render_image_thumbnail(source)
        self.storage.store(
            asset_id=asset_id,
            suffix=THUMBNAIL_SUFFIX,
            chunks=[thumbnail],
            storage_key=thumbnail_storage_key(original_storage_key),
        )


def _stream_chunks(stream: BinaryIO, header: bytes) -> Iterator[bytes]:
    yield header
    while chunk := stream.read(64 * 1024):
        yield chunk
