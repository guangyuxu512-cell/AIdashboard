from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AssetOwnership:
    """素材归属由可信 Service 上游提供，不能直接来自公开 HTTP 输入。"""

    team_id: UUID
    created_by_user_id: UUID | None
