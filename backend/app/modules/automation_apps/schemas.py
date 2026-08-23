import re
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AutomationInputType(StrEnum):
    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    SELECT = "select"


class AutomationInputField(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=100)
    type: AutomationInputType
    required: bool = False
    default_value: Any = None
    options: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", value) is None:
            raise ValueError("参数名只能包含字母、数字、下划线、点和连字符")
        return value

    @model_validator(mode="after")
    def validate_type_contract(self) -> "AutomationInputField":
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

    @model_validator(mode="after")
    def unique_names(self) -> "AutomationInputSchema":
        names = [field.name for field in self.fields]
        if len(names) != len(set(names)):
            raise ValueError("参数名不能重复")
        return self


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


def _validate_value(field: AutomationInputField, value: Any) -> None:
    valid = {
        AutomationInputType.TEXT: isinstance(value, str),
        AutomationInputType.NUMBER: isinstance(value, (int, float)) and not isinstance(value, bool),
        AutomationInputType.BOOLEAN: isinstance(value, bool),
        AutomationInputType.SELECT: isinstance(value, str) and value in field.options,
    }[field.type]
    if not valid:
        raise ValueError(f"参数 {field.label} 的值不符合 {field.type.value} 类型")
