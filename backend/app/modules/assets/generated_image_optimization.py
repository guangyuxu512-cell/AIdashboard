from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from math import floor
from pathlib import Path
from tempfile import SpooledTemporaryFile
from threading import BoundedSemaphore
from typing import BinaryIO

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_GENERATED_OUTPUT_BYTES = 1_000_000
MIN_GENERATED_OUTPUT_SHORT_EDGE = 768
_IMAGE_QUALITY_STEPS = (90, 82, 74)
_OPTIMIZATION_CONCURRENCY = 2
_STREAM_COPY_CHUNK_SIZE = 64 * 1024
_optimization_slots = BoundedSemaphore(_OPTIMIZATION_CONCURRENCY)


class GeneratedImageOptimizationError(RuntimeError):
    """Raised when a generated image cannot safely meet the output policy."""


@dataclass(frozen=True, slots=True)
class GeneratedImageOutput:
    stream: BinaryIO
    original_filename: str
    content_type: str
    size_bytes: int
    width: int
    height: int


@contextmanager
def prepare_generated_image_output(
    *,
    stream: BinaryIO,
    original_filename: str | None,
    content_type: str | None,
    max_bytes: int = MAX_GENERATED_OUTPUT_BYTES,
) -> Iterator[GeneratedImageOutput]:
    """Return one decoded final image stream without retaining a raw output copy.

    The provider response is buffered only in a spooled temporary stream. Smaller
    valid images keep their original bytes; larger opaque images become JPEG and
    larger transparent images become WebP so alpha is never flattened.
    """

    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")

    with _optimization_slots:
        with SpooledTemporaryFile(max_size=max_bytes, mode="w+b") as source:
            source_size = _copy_to_spooled_stream(stream, source)
            source.seek(0)
            width, height, source_format = _decoded_image_metadata(source)
            source.seek(0)

            if source_size < max_bytes:
                source_suffix, source_content_type = _format_metadata(source_format)
                yield GeneratedImageOutput(
                    stream=source,
                    original_filename=_filename_with_suffix(
                        original_filename,
                        source_suffix,
                    ),
                    content_type=source_content_type,
                    size_bytes=source_size,
                    width=width,
                    height=height,
                )
                return

            try:
                with Image.open(source) as image:
                    image.load()
                    has_alpha = _has_transparency(image)
                    normalized = ImageOps.exif_transpose(image)
                    color_profile = normalized.info.get("icc_profile")
                    if has_alpha:
                        normalized = normalized.convert("RGBA")
                        image_format = "WEBP"
                        output_suffix = ".webp"
                        output_content_type = "image/webp"
                    else:
                        normalized = normalized.convert("RGB")
                        image_format = "JPEG"
                        output_suffix = ".jpg"
                        output_content_type = "image/jpeg"
                    payload, final_width, final_height = _compress_image(
                        normalized,
                        image_format=image_format,
                        color_profile=color_profile,
                        max_bytes=max_bytes,
                    )
            except (UnidentifiedImageError, OSError, ValueError) as error:
                raise GeneratedImageOptimizationError() from error

            with SpooledTemporaryFile(max_size=max_bytes, mode="w+b") as output:
                output.write(payload)
                output.seek(0)
                yield GeneratedImageOutput(
                    stream=output,
                    original_filename=_filename_with_suffix(
                        original_filename,
                        output_suffix,
                    ),
                    content_type=output_content_type,
                    size_bytes=len(payload),
                    width=final_width,
                    height=final_height,
                )


def _copy_to_spooled_stream(stream: BinaryIO, target: BinaryIO) -> int:
    size = 0
    try:
        while chunk := stream.read(_STREAM_COPY_CHUNK_SIZE):
            target.write(chunk)
            size += len(chunk)
    except OSError as error:
        raise GeneratedImageOptimizationError() from error
    return size


def _decoded_image_metadata(source: BinaryIO) -> tuple[int, int, str]:
    try:
        with Image.open(source) as image:
            image.load()
            if image.format is None:
                raise ValueError("Image format is unavailable")
            return image.width, image.height, image.format
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise GeneratedImageOptimizationError() from error


def _has_transparency(image: Image.Image) -> bool:
    return "A" in image.getbands() or "transparency" in image.info


def _compress_image(
    image: Image.Image,
    *,
    image_format: str,
    color_profile: bytes | None,
    max_bytes: int,
) -> tuple[bytes, int, int]:
    current = image
    while True:
        for quality in _IMAGE_QUALITY_STEPS:
            payload = _encode_image(
                current,
                image_format=image_format,
                quality=quality,
                color_profile=color_profile,
            )
            if len(payload) < max_bytes:
                return payload, current.width, current.height

        next_size = _next_dimensions(current.width, current.height)
        if next_size is None:
            raise GeneratedImageOptimizationError()
        current = current.resize(next_size, Image.Resampling.LANCZOS)


def _encode_image(
    image: Image.Image,
    *,
    image_format: str,
    quality: int,
    color_profile: bytes | None,
) -> bytes:
    with SpooledTemporaryFile(max_size=MAX_GENERATED_OUTPUT_BYTES, mode="w+b") as output:
        save_options: dict[str, object] = {
            "format": image_format,
            "quality": quality,
        }
        if color_profile:
            save_options["icc_profile"] = color_profile
        if image_format == "JPEG":
            save_options["optimize"] = True
        else:
            save_options["method"] = 4
        image.save(output, **save_options)
        output.seek(0)
        return output.read()


def _next_dimensions(width: int, height: int) -> tuple[int, int] | None:
    short_edge = min(width, height)
    if short_edge <= MIN_GENERATED_OUTPUT_SHORT_EDGE:
        return None
    next_short_edge = max(
        MIN_GENERATED_OUTPUT_SHORT_EDGE,
        floor(short_edge * 0.85),
    )
    if next_short_edge >= short_edge:
        return None
    scale = next_short_edge / short_edge
    return max(1, floor(width * scale)), max(1, floor(height * scale))


def _source_filename(value: str | None) -> str:
    filename = (value or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    return filename or "generated.png"


def _format_metadata(image_format: str) -> tuple[str, str]:
    metadata = {
        "JPEG": (".jpg", "image/jpeg"),
        "PNG": (".png", "image/png"),
        "WEBP": (".webp", "image/webp"),
    }.get(image_format.upper())
    if metadata is None:
        raise GeneratedImageOptimizationError()
    return metadata


def _filename_with_suffix(value: str | None, suffix: str) -> str:
    filename = _source_filename(value)
    stem = Path(filename).stem.strip() or "generated"
    return f"{stem[: 255 - len(suffix)]}{suffix}"
