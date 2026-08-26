from enum import StrEnum


class AssetMediaType(StrEnum):
    IMAGE = "image"
    VIDEO = "video"


class AssetSourceType(StrEnum):
    UPLOAD = "upload"
    AI_GENERATED = "ai_generated"
    IMPORTED = "imported"
