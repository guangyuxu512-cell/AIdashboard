from pathlib import Path

from app.modules.assets.exceptions import AssetTypeUnsupportedError


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


def validate_image_content(
    *,
    filename_suffix: str,
    declared_content_type: str | None,
    header: bytes,
) -> str:
    expected_content_type = ALLOWED_IMAGE_TYPES[filename_suffix]
    if declared_content_type and declared_content_type.lower() != expected_content_type:
        raise AssetTypeUnsupportedError()
    if detect_image_content_type(header) != expected_content_type:
        raise AssetTypeUnsupportedError()
    return expected_content_type


def detect_image_content_type(header: bytes) -> str | None:
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp"
    return None
