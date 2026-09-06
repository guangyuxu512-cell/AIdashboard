from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.ai_workbench.enums import (
    AiModelCapability,
    AiModelResolution,
    GenerationSize,
)


class AiModelCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str = Field(min_length=1, max_length=100)
    model_code: str = Field(min_length=1, max_length=100)
    provider_code: str = Field(min_length=1, max_length=32)
    enabled: bool = True
    is_default: bool = False
    capabilities: list[AiModelCapability] = Field(min_length=1, max_length=2)
    max_input_images: int = Field(ge=0)
    supported_sizes: list[GenerationSize] = Field(min_length=1, max_length=4)
    supported_resolutions: list[AiModelResolution] = Field(
        min_length=1,
        max_length=3,
    )

    @field_validator(
        "capabilities",
        "supported_sizes",
        "supported_resolutions",
    )
    @classmethod
    def require_unique_values(cls, values: list[object]) -> list[object]:
        if len(values) != len(set(values)):
            raise ValueError("能力选项不能重复")
        return values

    @model_validator(mode="after")
    def default_must_be_enabled(self) -> "AiModelCreate":
        if self.is_default and not self.enabled:
            raise ValueError("默认模型必须启用")
        return self


class AiModelUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    enabled: bool | None = None
    is_default: bool | None = None
    capabilities: list[AiModelCapability] | None = Field(
        default=None,
        min_length=1,
        max_length=2,
    )
    max_input_images: int | None = Field(default=None, ge=0)
    supported_sizes: list[GenerationSize] | None = Field(
        default=None,
        min_length=1,
        max_length=4,
    )
    supported_resolutions: list[AiModelResolution] | None = Field(
        default=None,
        min_length=1,
        max_length=3,
    )

    @field_validator(
        "capabilities",
        "supported_sizes",
        "supported_resolutions",
    )
    @classmethod
    def require_unique_values(
        cls,
        values: list[object] | None,
    ) -> list[object] | None:
        if values is not None and len(values) != len(set(values)):
            raise ValueError("能力选项不能重复")
        return values

    @model_validator(mode="after")
    def require_change(self) -> "AiModelUpdate":
        if not self.model_fields_set:
            raise ValueError("至少提供一个要修改的字段")
        if any(getattr(self, field_name) is None for field_name in self.model_fields_set):
            raise ValueError("修改字段不能为 null")
        return self


class AiModelAdminRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model_id: UUID
    display_name: str
    model_code: str
    provider_code: str
    enabled: bool
    is_default: bool
    capabilities: list[AiModelCapability]
    max_input_images: int
    supported_sizes: list[GenerationSize]
    supported_resolutions: list[AiModelResolution]
    created_at: datetime
    updated_at: datetime


class AiModelCatalogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model_id: UUID
    model_code: str
    display_name: str
    capabilities: list[AiModelCapability]
    max_input_images: int
    supported_sizes: list[GenerationSize]
    supported_resolutions: list[AiModelResolution]
    is_default: bool
