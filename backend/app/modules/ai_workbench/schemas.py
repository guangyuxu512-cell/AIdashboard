from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.ai_workbench.enums import (
    GenerationMode,
    GenerationSize,
    MaterialRole,
    OutputFormat,
    OutputRole,
)
from app.modules.assets.schemas import AssetRead


class TemplateGroupCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    mode: GenerationMode
    enabled: bool = True


class TemplateGroupUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=100)
    enabled: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> "TemplateGroupUpdate":
        if not self.model_fields_set:
            raise ValueError("至少提供一个需要更新的字段")
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} 不能为 null")
        return self


def _normalize_variables(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        candidate = value.strip()
        if not candidate:
            raise ValueError("variables 不能包含空变量名")
        if candidate not in seen:
            normalized.append(candidate)
            seen.add(candidate)
    if len(normalized) > 20:
        raise ValueError("variables 最多包含 20 个变量名")
    return normalized


class PromptTemplateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    enabled: bool = True
    output_role: OutputRole
    output_format: OutputFormat
    size: GenerationSize
    count: int = Field(ge=1, le=8)
    variables: list[str]
    prompt: str = Field(min_length=1, max_length=5000)

    @field_validator("variables")
    @classmethod
    def normalize_variables(cls, values: list[str]) -> list[str]:
        return _normalize_variables(values)


class PromptTemplateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=100)
    enabled: bool | None = None
    output_format: OutputFormat | None = None
    size: GenerationSize | None = None
    count: int | None = Field(default=None, ge=1, le=8)
    variables: list[str] | None = None
    prompt: str | None = Field(default=None, min_length=1, max_length=5000)

    @field_validator("variables")
    @classmethod
    def normalize_variables(cls, values: list[str] | None) -> list[str] | None:
        return None if values is None else _normalize_variables(values)

    @model_validator(mode="after")
    def require_change(self) -> "PromptTemplateUpdate":
        if not self.model_fields_set:
            raise ValueError("至少提供一个需要更新的字段")
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} 不能为 null")
        return self


class PromptTemplateReorder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_role: OutputRole
    prompt_template_ids: list[UUID]

    @field_validator("prompt_template_ids")
    @classmethod
    def require_unique_ids(cls, values: list[UUID]) -> list[UUID]:
        if len(values) != len(set(values)):
            raise ValueError("prompt_template_ids 不能重复")
        return values


class PromptTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    prompt_template_id: UUID
    template_group_id: UUID
    name: str
    enabled: bool
    output_role: OutputRole
    output_format: OutputFormat
    size: GenerationSize
    count: int
    variables: list[str]
    prompt: str
    sort_order: int
    created_at: datetime
    updated_at: datetime


class TemplateGroupSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    template_group_id: UUID
    name: str
    mode: GenerationMode
    enabled: bool
    created_at: datetime
    updated_at: datetime


class TemplateGroupRead(TemplateGroupSummaryRead):
    prompt_templates: list[PromptTemplateRead]


class ProductMaterialGroupCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    enabled: bool = True
    normal_generation_enabled: bool = True
    style_replication_enabled: bool = False


class ProductMaterialGroupUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=100)
    enabled: bool | None = None
    normal_generation_enabled: bool | None = None
    style_replication_enabled: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> "ProductMaterialGroupUpdate":
        if not self.model_fields_set:
            raise ValueError("至少提供一个需要更新的字段")
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} 不能为 null")
        return self


class MaterialGroupAssetAttach(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: UUID
    role: MaterialRole

    @field_validator("role")
    @classmethod
    def reject_ai_output(cls, value: MaterialRole) -> MaterialRole:
        if value is MaterialRole.AI_OUTPUT:
            raise ValueError("AI_OUTPUT 只能由后续生成归档流程建立")
        return value


class MaterialGroupAssetRead(BaseModel):
    role: MaterialRole
    created_at: datetime
    asset: AssetRead


class TemplateBindingReplace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_group_ids: list[UUID]


class MaterialGroupTemplateBindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    material_group_id: UUID
    template_group_id: UUID
    generation_mode: GenerationMode
    position: int
    created_at: datetime


class ProductMaterialGroupSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    material_group_id: UUID
    name: str
    enabled: bool
    normal_generation_enabled: bool
    style_replication_enabled: bool
    created_at: datetime
    updated_at: datetime


class ProductMaterialGroupRead(ProductMaterialGroupSummaryRead):
    assets: list[MaterialGroupAssetRead]
    template_bindings: list[MaterialGroupTemplateBindingRead]
