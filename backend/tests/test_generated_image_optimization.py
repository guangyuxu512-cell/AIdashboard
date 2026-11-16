from __future__ import annotations

from io import BytesIO
from random import Random

import pytest
from PIL import Image

from app.modules.assets.generated_image_optimization import (
    GeneratedImageOptimizationError,
    MAX_GENERATED_OUTPUT_BYTES,
    MIN_GENERATED_OUTPUT_SHORT_EDGE,
    prepare_generated_image_output,
)


def _noise_image(
    *,
    width: int,
    height: int,
    image_format: str,
    transparent: bool = False,
    orientation: int | None = None,
) -> bytes:
    random = Random(width * 10_000 + height * 10 + (4 if transparent else 3))
    image = Image.frombytes(
        "RGB",
        (width, height),
        random.randbytes(width * height * 3),
    )
    if transparent:
        alpha = Image.new("L", (width, height), color=255)
        alpha.putpixel((0, 0), 0)
        image.putalpha(alpha)
    output = BytesIO()
    save_options: dict[str, object] = {"format": image_format}
    if image_format == "JPEG":
        image = image.convert("RGB")
        save_options["quality"] = 100
        if orientation is not None:
            exif = image.getexif()
            exif[274] = orientation
            save_options["exif"] = exif
    image.save(output, **save_options)
    return output.getvalue()


def test_large_opaque_output_is_oriented_compressed_and_bounded() -> None:
    source = _noise_image(
        width=1_200,
        height=1_800,
        image_format="JPEG",
        orientation=6,
    )
    assert len(source) > MAX_GENERATED_OUTPUT_BYTES

    with prepare_generated_image_output(
        stream=BytesIO(source),
        original_filename="provider-result.jpeg",
        content_type="image/jpeg",
    ) as output:
        payload = output.stream.read()
        assert output.original_filename == "provider-result.jpg"
        assert output.content_type == "image/jpeg"
        assert output.size_bytes == len(payload)
        assert len(payload) < MAX_GENERATED_OUTPUT_BYTES
        with Image.open(BytesIO(payload)) as image:
            image.load()
            assert image.format == "JPEG"
            assert image.size == (output.width, output.height)
            assert image.width > image.height
            assert min(image.size) >= MIN_GENERATED_OUTPUT_SHORT_EDGE


def test_large_transparent_output_keeps_alpha_in_a_supported_final_format() -> None:
    source = _noise_image(
        width=1_600,
        height=1_300,
        image_format="PNG",
        transparent=True,
    )
    assert len(source) > MAX_GENERATED_OUTPUT_BYTES

    with prepare_generated_image_output(
        stream=BytesIO(source),
        original_filename="transparent-result.png",
        content_type="image/png",
    ) as output:
        payload = output.stream.read()
        assert output.original_filename.endswith(".webp")
        assert output.content_type == "image/webp"
        assert len(payload) < MAX_GENERATED_OUTPUT_BYTES
        with Image.open(BytesIO(payload)) as image:
            image.load()
            assert image.format == "WEBP"
            assert "A" in image.getbands()
            assert image.getchannel("A").getextrema()[0] < 255


def test_already_small_output_stays_byte_identical_and_stream_is_cleaned_up() -> None:
    source = _noise_image(width=160, height=120, image_format="PNG")
    stream = None

    with prepare_generated_image_output(
        stream=BytesIO(source),
        original_filename="small.png",
        content_type="image/png",
    ) as output:
        stream = output.stream
        assert output.stream.read() == source
        assert output.original_filename == "small.png"
        assert output.content_type == "image/png"
        assert output.size_bytes == len(source)

    assert stream is not None
    assert stream.closed


def test_final_metadata_comes_from_small_image_bytes_not_provider_claims() -> None:
    source = _noise_image(width=160, height=120, image_format="PNG")

    with prepare_generated_image_output(
        stream=BytesIO(source),
        original_filename="provider-result.jpeg",
        content_type="image/jpeg",
    ) as output:
        assert output.stream.read() == source
        assert output.original_filename == "provider-result.png"
        assert output.content_type == "image/png"


def test_invalid_or_uncompressible_output_fails_without_persisting_raw_bytes() -> None:
    with pytest.raises(GeneratedImageOptimizationError):
        with prepare_generated_image_output(
            stream=BytesIO(b"not-an-image" * 100),
            original_filename="invalid.png",
            content_type="image/png",
            max_bytes=100,
        ):
            pass

    source = _noise_image(width=1_024, height=1_024, image_format="PNG")
    with pytest.raises(GeneratedImageOptimizationError):
        with prepare_generated_image_output(
            stream=BytesIO(source),
            original_filename="too-small-budget.png",
            content_type="image/png",
            max_bytes=100,
        ):
            pass
