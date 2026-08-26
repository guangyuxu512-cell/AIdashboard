from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.assets.enums import AssetMediaType, AssetSourceType


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asset_id: UUID
    original_filename: str
    media_type: AssetMediaType
    source_type: AssetSourceType
    content_type: str
    size_bytes: int
    sha256: str
    created_at: datetime
