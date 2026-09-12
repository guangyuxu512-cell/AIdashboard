import re
import unicodedata
from collections import Counter
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError


class AutomationInputType(StrEnum):
    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    SELECT = "select"


_PARAMETER_NAME_PATTERN = re.compile(r"[\w.-]+\Z")


class AutomationInputField(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    label: str = Field(default="", max_length=100)
    type: AutomationInputType
    required: bool = False
    default_value: Any = None
    options: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if any(unicodedata.category(character).startswith("C") for character in value):
            raise ValueError("参数名不能包含控制字符")
        if _PARAMETER_NAME_PATTERN.fullmatch(value) is None:
            raise ValueError("参数名只能包含 Unicode 字母、数字、下划线、点和连字符")
        return value

    @model_validator(mode="after")
    def validate_type_contract(self) -> "AutomationInputField":
        if not self.label:
            self.label = self.name
        if self.type is AutomationInputType.SELECT:
            if (
                not self.options
                or any(not option for option in self.options)
                or len(set(self.options)) != len(self.options)
            ):
                raise ValueError("选择参数必须提供不重复的选项")
        elif self.options:
            raise ValueError("只有选择参数可以提供选项")
        if self.default_value is not None:
            _validate_value(self, self.default_value)
        return self


class AutomationInputSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: list[AutomationInputField] = Field(default_factory=list, max_length=100)

    @field_validator("fields")
    @classmethod
    def unique_names(
        cls,
        fields: list[AutomationInputField],
    ) -> list[AutomationInputField]:
        duplicate_names = {
            name
            for name, count in Counter(field.name for field in fields).items()
            if count > 1
        }
        duplicate_errors = [
            {
                "type": PydanticCustomError("value_error", "参数名不能重复"),
                "loc": (index, "name"),
                "input": field.name,
            }
            for index, field in enumerate(fields)
            if field.name in duplicate_names
        ]
        if duplicate_errors:
            raise ValidationError.from_exception_data(cls.__name__, duplicate_errors)
        return fields


class AutomationApplicationConfigUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_schema: AutomationInputSchema


class AutomationApplicationConfigRead(BaseModel):
    config_id: UUID
    provider_code: str
    app_id: str
    schema_source: str
    input_schema: AutomationInputSchema
    default_values: dict[str, Any]
    version: int
    created_at: datetime
    updated_at: datetime


class YingdaoApplicationOptionRead(BaseModel):
    """A minimal human-facing option from an already visible Device inventory."""

    app_id: str
    app_name: str


class AutomationParameterPresetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    # Omitted only by legacy clients.  The service then takes one initial
    # template snapshot from the application configuration.
    input_schema: AutomationInputSchema | None = None
    common_parameters: dict[str, Any] = Field(default_factory=dict)
    shop_overrides: dict[UUID, dict[str, Any]] = Field(default_factory=dict)


class AutomationParameterPresetUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    input_schema: AutomationInputSchema | None = None
    common_parameters: dict[str, Any] | None = None
    shop_overrides: dict[UUID, dict[str, Any]] | None = None

    @model_validator(mode="after")
    def require_change(self) -> "AutomationParameterPresetUpdate":
        changed_fields = self.model_fields_set - {"expected_version"}
        if not changed_fields:
            raise ValueError("至少提供一个需要更新的字段")
        for name in changed_fields:
            if getattr(self, name) is None:
                raise ValueError(f"{name} 不能为 null")
        return self


class AutomationParameterPresetCopy(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)


class AutomationParameterPresetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    preset_id: UUID
    team_id: UUID
    created_by_user_id: UUID
    app_id: str
    name: str
    input_schema: AutomationInputSchema
    common_parameters: dict[str, Any]
    shop_overrides: dict[UUID, dict[str, Any]]
    invalid_parameter_names: list[str] = Field(default_factory=list)
    version: int
    created_at: datetime
    updated_at: datetime


def normalize_parameters(
    schema: AutomationInputSchema,
    values: dict[str, Any],
) -> dict[str, Any]:
    field_by_name = {field.name: field for field in schema.fields}
    unknown = sorted(set(values) - set(field_by_name))
    if unknown:
        raise ValueError(f"未知参数: {', '.join(unknown)}")
    normalized: dict[str, Any] = {}
    for field in schema.fields:
        value = values.get(field.name, field.default_value)
        if value is None or (
            field.required
            and field.type is AutomationInputType.TEXT
            and isinstance(value, str)
            and not value.strip()
        ):
            if field.required:
                raise ValueError(f"缺少必填参数: {field.label}")
            continue
        _validate_value(field, value)
        normalized[field.name] = value
    return normalized


def validate_parameter_subset(
    schema: AutomationInputSchema,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Validate a partial override without inventing a second field schema.

    Required-field completeness belongs to the final Task parameter snapshot;
    a shop override is deliberately allowed to contain only fields that differ
    from the preset's common parameters.
    """

    field_by_name = {field.name: field for field in schema.fields}
    unknown = sorted(set(values) - set(field_by_name))
    if unknown:
        raise ValueError(f"未知参数: {', '.join(unknown)}")
    normalized: dict[str, Any] = {}
    for name, value in values.items():
        if value is None:
            raise ValueError(f"参数 {field_by_name[name].label} 不能为 null")
        _validate_value(field_by_name[name], value)
        normalized[name] = value
    return normalized


def normalize_explicit_parameter_selection(
    schema: AutomationInputSchema,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Validate the field set explicitly enabled by one parameter preset.

    Unlike :func:`normalize_parameters`, this function must never turn an
    omitted optional schema field into a preset value.  The persisted keys are
    the preset's field selection: a default is included only when the user has
    explicitly added that field (and the client submitted its default value).
    Required fields still have to be explicitly present so a changed schema
    cannot silently alter a future Task or Schedule execution.
    """

    field_by_name = {field.name: field for field in schema.fields}
    unknown = sorted(set(values) - set(field_by_name))
    if unknown:
        raise ValueError(f"未知参数: {', '.join(unknown)}")

    normalized: dict[str, Any] = {}
    for field in schema.fields:
        if field.name not in values:
            if field.required:
                raise ValueError(f"缺少必填参数: {field.label}")
            continue
        value = values[field.name]
        if value is None:
            raise ValueError(f"参数 {field.label} 不能为 null")
        if (
            field.required
            and field.type is AutomationInputType.TEXT
            and isinstance(value, str)
            and not value.strip()
        ):
            raise ValueError(f"缺少必填参数: {field.label}")
        _validate_value(field, value)
        normalized[field.name] = value
    return normalized


def build_parameter_preset_snapshot(
    schema: AutomationInputSchema,
    *,
    common_parameters: dict[str, Any],
    shop_overrides: dict[str, dict[str, Any]],
    shop_ids: list[UUID],
) -> dict[str, Any]:
    """Materialize a versioned Worker payload for the selected Shop set.

    The Task stores only this completed snapshot.  It never asks the Worker to
    merge preset data, and a later preset edit cannot change an already-created
    Task.
    """

    # A preset's persisted keys are its explicit enabled field set.  Do not
    # reuse the manual-parameter normalizer here: it intentionally materializes
    # every schema default, which would make fields removed from one preset
    # reappear in new Task/Schedule snapshots.
    normalized_common = normalize_explicit_parameter_selection(
        schema,
        common_parameters,
    )
    normalized_overrides = {
        shop_id: validate_parameter_subset(schema, values)
        for shop_id, values in shop_overrides.items()
    }
    return {
        "格式版本": 1,
        "公共参数": normalized_common,
        "店铺参数": {
            str(shop_id): normalize_explicit_parameter_selection(
                schema,
                {**normalized_common, **normalized_overrides.get(str(shop_id), {})},
            )
            for shop_id in shop_ids
        },
    }


def _validate_value(field: AutomationInputField, value: Any) -> None:
    valid = {
        AutomationInputType.TEXT: isinstance(value, str),
        AutomationInputType.NUMBER: isinstance(value, (int, float)) and not isinstance(value, bool),
        AutomationInputType.BOOLEAN: isinstance(value, bool),
        AutomationInputType.SELECT: isinstance(value, str) and value in field.options,
    }[field.type]
    if not valid:
        raise ValueError(f"参数 {field.label} 的值不符合 {field.type.value} 类型")
