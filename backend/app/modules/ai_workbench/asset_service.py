from collections.abc import Sequence
from typing import BinaryIO
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
from app.modules.access.module_access import ModuleCode
from app.modules.access.service import ModuleAccessService
from app.modules.ai_workbench.repository import AiAssetReferenceRepository
from app.modules.assets.enums import AssetMediaType, AssetSourceType
from app.modules.assets.exceptions import AssetNotFoundError
from app.modules.assets.models import Asset
from app.modules.assets.service import AssetService


class AiAssetService:
    """AI file-use boundary, not a second storage or general Asset permission."""

    def __init__(
        self,
        session: Session,
        *,
        asset_service: AssetService | None = None,
        references: AiAssetReferenceRepository | None = None,
        module_access: ModuleAccessService | None = None,
    ) -> None:
        self.session = session
        self.assets = asset_service or AssetService(session)
        self.references = references or AiAssetReferenceRepository(session)
        self.module_access = module_access or ModuleAccessService(session)

    @staticmethod
    def is_owned_upload(actor: ActorContext, asset: Asset) -> bool:
        # Deliberate owner-draft exception: includes earlier personal uploads.
        # source_type is provenance, not proof that an AI page created a file.
        return (
            actor.team_id is not None
            and asset.team_id == actor.team_id
            and asset.created_by_user_id == actor.user_id
            and asset.source_type == AssetSourceType.UPLOAD.value
            and asset.media_type == AssetMediaType.IMAGE.value
        )

    def require_eligible(self, actor: ActorContext, assets: Sequence[Asset]) -> None:
        if any(asset.media_type != AssetMediaType.IMAGE.value for asset in assets):
            raise AssetNotFoundError()
        remaining = {
            asset.asset_id for asset in assets if not self.is_owned_upload(actor, asset)
        }
        if not remaining:
            return
        # The original explicit ASSET grant retains its original scoped input
        # capability. This never grants ASSET to an AI-only account.
        if ModuleCode.ASSET in self.module_access.list_for_actor(actor):
            return
        if remaining - self.references.referenced_asset_ids(actor, list(remaining)):
            raise AssetNotFoundError()

    def upload(
        self,
        *,
        actor: ActorContext,
        original_filename: str | None,
        content_type: str | None,
        stream: BinaryIO,
    ) -> Asset:
        return self.assets.upload(
            actor=actor,
            original_filename=original_filename,
            content_type=content_type,
            stream=stream,
        )

    def _require_read(self, actor: ActorContext, asset_id: UUID) -> None:
        assets = self.assets.list_accessible_by_ids(actor, [asset_id])
        if len(assets) != 1:
            raise AssetNotFoundError()
        self.require_eligible(actor, assets)

    def get_content(self, actor: ActorContext, asset_id: UUID) -> tuple[Asset, BinaryIO]:
        self._require_read(actor, asset_id)
        return self.assets.get_content(actor, asset_id)

    def get_thumbnail(self, actor: ActorContext, asset_id: UUID) -> tuple[Asset, BinaryIO, int]:
        self._require_read(actor, asset_id)
        return self.assets.get_thumbnail(actor, asset_id)

    def cleanup(self, actor: ActorContext, asset_id: UUID) -> None:
        actor.require_team_id()
        asset = self.assets.repository.get_for_actor_for_update(actor=actor, asset_id=asset_id)
        if asset is None or not self.is_owned_upload(actor, asset):
            self.session.rollback()
            raise AssetNotFoundError()
        # Same Session/row lock: original delete enforces *all* Task/Material/
        # Generation references, storage readiness and ASSET_IN_USE atomically.
        self.assets.delete(actor, asset_id)
