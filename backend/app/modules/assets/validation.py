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
    header: bytes,
) -> tuple[str, str]:
    # Browsers commonly derive Content-Type from the filename, including a wrong
    # extension. The actual supported image signature is authoritative.
    content_type = detect_image_content_type(header)
    if content_type is None:
        raise AssetTypeUnsupportedError()
    if ALLOWED_IMAGE_TYPES[filename_suffix] != content_type:
        filename_suffix = next(
            suffix for suffix, mime in ALLOWED_IMAGE_TYPES.items() if mime == content_type
        )
    return content_type, filename_suffix


def detect_image_content_type(header: bytes) -> str | None:
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp"
    return None
