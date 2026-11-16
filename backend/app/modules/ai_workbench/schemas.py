from datetime import datetime
from typing import Annotated, Literal, TypeAlias
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from app.modules.ai_workbench.enums import (
    BatchProductScope,
    BatchTemplateSource,
    GenerationInputRole,
    GenerationItemStatus,
    GenerationJobStatus,
    GenerationMode,
    GenerationOutputRange,
    GenerationSize,
    GenerationWorkMode,
    MaterialRole,
    OutputFormat,
    OutputRole,
)
from app.modules.ai_workbench.limits import (
    MAX_GENERATION_ITEMS,
    MAX_GENERATION_SELECTION_IDS,
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


def _require_unique_ids(values: list[UUID], field_name: str) -> list[UUID]:
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} 不能重复")
    return values


class InstantGenerationSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    work_mode: Literal[GenerationWorkMode.INSTANT] = GenerationWorkMode.INSTANT
    submission_key: str = Field(min_length=1, max_length=128)
    model_id: UUID
    mode: GenerationMode
    product_asset_ids: list[UUID] = Field(
        min_length=1,
        max_length=MAX_GENERATION_SELECTION_IDS,
    )
    reference_asset_ids: list[UUID] = Field(
        default_factory=list,
        max_length=MAX_GENERATION_SELECTION_IDS,
    )
    prompt_template_id: UUID | None = None
    prompt: str = Field(min_length=1, max_length=5000)
    output_format: OutputFormat
    size: GenerationSize
    count: int = Field(ge=1, le=8)
    compress_output_under_1000kb: bool = False

    @field_validator("product_asset_ids", "reference_asset_ids")
    @classmethod
    def require_unique_asset_ids(
        cls,
        values: list[UUID],
        info: ValidationInfo,
    ) -> list[UUID]:
        return _require_unique_ids(values, info.field_name or "asset_ids")

    @model_validator(mode="after")
    def validate_mode_inputs(self) -> "InstantGenerationSubmit":
        if self.mode is GenerationMode.NORMAL_GENERATION and self.reference_asset_ids:
            raise ValueError("普通生图不接受 reference_asset_ids")
        if self.mode is GenerationMode.STYLE_REPLICATION and not (
            self.reference_asset_ids
        ):
            raise ValueError("风格复刻至少需要一个参考素材")
        return self


class BatchGenerationSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    work_mode: Literal[GenerationWorkMode.BATCH] = GenerationWorkMode.BATCH
    submission_key: str = Field(min_length=1, max_length=128)
    model_id: UUID
    mode: GenerationMode
    product_scope: BatchProductScope
    selected_product_ids: list[UUID] = Field(
        default_factory=list,
        max_length=MAX_GENERATION_SELECTION_IDS,
    )
    template_source: BatchTemplateSource
    selected_template_group_ids: list[UUID] = Field(
        default_factory=list,
        max_length=MAX_GENERATION_SELECTION_IDS,
    )
    output_range: GenerationOutputRange = GenerationOutputRange.ALL
    compress_output_under_1000kb: bool = False

    @field_validator("selected_product_ids", "selected_template_group_ids")
    @classmethod
    def require_unique_selection_ids(
        cls,
        values: list[UUID],
        info: ValidationInfo,
    ) -> list[UUID]:
        return _require_unique_ids(values, info.field_name or "selected_ids")

    @model_validator(mode="after")
    def validate_selections(self) -> "BatchGenerationSubmit":
        if self.product_scope is BatchProductScope.SELECTED:
            if not self.selected_product_ids:
                raise ValueError("选择产品范围时至少提交一个商品素材组")
        elif self.selected_product_ids:
            raise ValueError("ALL_ENABLED 不接受 selected_product_ids")

        if self.template_source is BatchTemplateSource.CURRENT_SELECTION:
            if not self.selected_template_group_ids:
                raise ValueError("本次选择模板时至少提交一个模板组")
        elif self.selected_template_group_ids:
            raise ValueError(
                "PRODUCT_CONFIGURED 不接受 selected_template_group_ids",
            )
        return self


GenerationSubmit: TypeAlias = Annotated[
    InstantGenerationSubmit | BatchGenerationSubmit,
    Field(discriminator="work_mode"),
]


class GenerationRetryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: UUID
    expected_attempt_count: int = Field(ge=1)


class GenerationRetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GenerationRetryItem] = Field(
        min_length=1,
        max_length=MAX_GENERATION_ITEMS,
    )

    @field_validator("items")
    @classmethod
    def require_unique_item_ids(
        cls,
        values: list[GenerationRetryItem],
    ) -> list[GenerationRetryItem]:
        item_ids = [item.item_id for item in values]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("item_id 不能重复")
        return values


class GenerationItemArchiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_group_id: UUID


class GenerationCountsRead(BaseModel):
    total_count: int = Field(ge=0)
    pending_count: int = Field(ge=0)
    running_count: int = Field(ge=0)
    success_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)


class GenerationInputSummaryRead(BaseModel):
    count: int = Field(ge=0)
    primary_name: str | None


class GenerationItemAssetRead(BaseModel):
    input_role: GenerationInputRole
    position: int = Field(ge=0)
    asset: AssetRead


class GenerationItemRead(BaseModel):
    generation_item_id: UUID
    position: int = Field(ge=0)
    status: GenerationItemStatus
    final_prompt: str
    output_role: OutputRole
    output_format: OutputFormat
    size: GenerationSize
    source_product_position: int | None = Field(default=None, ge=0)
    source_template_group_position: int | None = Field(default=None, ge=0)
    source_prompt_template_position: int | None = Field(default=None, ge=0)
    output_ordinal: int = Field(ge=0)
    source_product_material_group_id: UUID | None
    source_template_group_id: UUID | None
    source_prompt_template_id: UUID | None
    product_name_snapshot: str | None
    template_group_name_snapshot: str | None
    prompt_template_name_snapshot: str | None
    attempt_count: int = Field(ge=1)
    last_failure_code: str | None
    last_failure_message: str | None
    last_failed_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    archived_material_group_id: UUID | None
    archived_material_group_name_snapshot: str | None
    archived_at: datetime | None
    input_assets: list[GenerationItemAssetRead]
    output_asset: AssetRead | None


class GenerationJobSummaryRead(GenerationCountsRead):
    generation_job_id: UUID
    model_id: UUID
    model_code: str
    model_display_name: str
    work_mode: GenerationWorkMode
    mode: GenerationMode
    compress_output_under_1000kb: bool
    status: GenerationJobStatus
    input_summary: GenerationInputSummaryRead
    created_by_display_name: str
    created_at: datetime
    updated_at: datetime


class GenerationJobRead(GenerationJobSummaryRead):
    submission_key: str
    started_at: datetime | None
    finished_at: datetime | None
    items: list[GenerationItemRead]
