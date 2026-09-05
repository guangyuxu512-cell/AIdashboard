from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO, Protocol
from uuid import UUID

from app.modules.ai_workbench.enums import (
    GenerationMode,
    GenerationSize,
    OutputFormat,
    OutputRole,
)


@dataclass(frozen=True, slots=True)
class GenerationProviderInput:
    asset_id: UUID
    original_filename: str
    content_type: str
    stream: BinaryIO


@dataclass(frozen=True, slots=True)
class GenerationProviderRequest:
    generation_item_id: UUID
    mode: GenerationMode
    final_prompt: str
    output_role: OutputRole
    output_format: OutputFormat
    size: GenerationSize
    input_images: tuple[GenerationProviderInput, ...]


@dataclass(frozen=True, slots=True)
class GeneratedProviderImage:
    original_filename: str
    content_type: str | None
    stream: BinaryIO


class ImageProviderFailure(RuntimeError):
    def __init__(
        self,
        failure_code: str,
        safe_message: str,
        *,
        retryable: bool,
    ) -> None:
        super().__init__(safe_message)
        self.failure_code = failure_code
        self.safe_message = safe_message
        self.retryable = retryable


class ImageGenerationProvider(Protocol):
    provider_code: str

    def create_task(self, request: GenerationProviderRequest) -> str: ...

    def wait_for_image(self, external_task_id: str) -> GeneratedProviderImage: ...
