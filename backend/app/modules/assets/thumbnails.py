from io import BytesIO
from pathlib import PurePosixPath
from typing import BinaryIO

from PIL import Image, ImageOps, UnidentifiedImageError

from app.modules.assets.exceptions import AssetThumbnailUnavailableError


THUMBNAIL_MAX_DIMENSION = 320
THUMBNAIL_SUFFIX = ".thumbnail.webp"
THUMBNAIL_CONTENT_TYPE = "image/webp"


def thumbnail_storage_key(original_storage_key: str) -> str:
    """Return the stable, non-public storage key for one Asset thumbnail."""

    path = PurePosixPath(original_storage_key)
    return str(path.with_name(f"{path.stem}{THUMBNAIL_SUFFIX}"))


def render_image_thumbnail(source: BinaryIO) -> bytes:
    """Render an image into the shared card-preview WebP specification."""

    try:
        with Image.open(source) as image:
            normalized = ImageOps.exif_transpose(image)
            normalized.thumbnail(
                (THUMBNAIL_MAX_DIMENSION, THUMBNAIL_MAX_DIMENSION),
                Image.Resampling.LANCZOS,
            )
            if normalized.mode in {"RGBA", "LA"} or "transparency" in normalized.info:
                normalized = normalized.convert("RGBA")
            else:
                normalized = normalized.convert("RGB")
            output = BytesIO()
            normalized.save(output, format="WEBP", quality=82, method=4)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise AssetThumbnailUnavailableError() from error
