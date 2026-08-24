from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
import math
import re
from typing import Any, Literal


BUSINESS_SKILL_INPUT_SCHEMA_MAX_BYTES = 32 * 1024

BusinessSkillSchemaStatus = Literal[
    "available",
    "schema_unavailable",
    "schema_unsupported",
]


class BusinessSkillSchemaUnavailableError(ValueError):
    pass


class BusinessSkillSchemaUnsupportedError(ValueError):
    pass


class BusinessSkillInputValidationError(ValueError):
    pass


@dataclass(frozen=True)
class BusinessSkillFieldContract:
    name: str
    value_type: Literal["string", "integer", "number", "boolean"]
    required: bool
    has_default: bool
    default: Any
    enum: tuple[Any, ...] | None
    schema: dict[str, Any]


@dataclass(frozen=True)
class BusinessSkillSchemaAnalysis:
    status: BusinessSkillSchemaStatus
    reason: str | None
    fields: tuple[BusinessSkillFieldContract, ...] = ()


_TOP_LEVEL_KEYS = {
    "$defs",
    "additionalProperties",
    "description",
    "properties",
    "required",
    "title",
    "type",
}
_FIELD_KEYS = {
    "$ref",
    "default",
    "description",
    "enum",
    "exclusiveMaximum",
    "exclusiveMinimum",
    "maximum",
    "maxLength",
    "minimum",
    "minLength",
    "multipleOf",
    "pattern",
    "title",
    "type",
}
_SUPPORTED_TYPES = {"string", "integer", "number", "boolean"}


def serialized_schema_size(schema: dict[str, Any]) -> int:
    return len(
        json.dumps(
            schema,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8"),
    )


def analyze_business_skill_input_schema(
    schema: dict[str, Any] | None,
) -> BusinessSkillSchemaAnalysis:
    if schema is None:
        return BusinessSkillSchemaAnalysis(
            status="schema_unavailable",
            reason="当前 Worker 未上报业务 Skill 输入契约",
        )
    try:
        fields = _parse_schema(schema)
    except BusinessSkillSchemaUnsupportedError as error:
        return BusinessSkillSchemaAnalysis(
            status="schema_unsupported",
            reason=str(error),
        )
    return BusinessSkillSchemaAnalysis(
        status="available",
        reason=None,
        fields=fields,
    )


def normalize_business_skill_input(
    schema: dict[str, Any] | None,
    values: dict[str, Any],
) -> dict[str, Any]:
    analysis = analyze_business_skill_input_schema(schema)
    if analysis.status == "schema_unavailable":
        raise BusinessSkillSchemaUnavailableError(analysis.reason)
    if analysis.status == "schema_unsupported":
        raise BusinessSkillSchemaUnsupportedError(analysis.reason)

    known_names = {field.name for field in analysis.fields}
    unknown_names = sorted(set(values) - known_names)
    if unknown_names:
        raise BusinessSkillInputValidationError(
            f"包含未声明参数：{', '.join(unknown_names)}",
        )

    normalized: dict[str, Any] = {}
    for field in analysis.fields:
        if field.name in values:
            value = values[field.name]
        elif field.has_default:
            value = deepcopy(field.default)
        elif field.required:
            raise BusinessSkillInputValidationError(
                f"缺少必填参数：{field.name}",
            )
        else:
            continue
        normalized[field.name] = _normalize_scalar(field, value)
    return normalized


def _parse_schema(
    schema: dict[str, Any],
) -> tuple[BusinessSkillFieldContract, ...]:
    if serialized_schema_size(schema) > BUSINESS_SKILL_INPUT_SCHEMA_MAX_BYTES:
        raise BusinessSkillSchemaUnsupportedError("业务 Skill 输入契约超过 32 KiB")
    if set(schema) - _TOP_LEVEL_KEYS:
        raise BusinessSkillSchemaUnsupportedError("输入契约包含暂不支持的顶层规则")
    if schema.get("type") != "object":
        raise BusinessSkillSchemaUnsupportedError("输入契约必须是对象类型")
    if schema.get("additionalProperties") is not False:
        raise BusinessSkillSchemaUnsupportedError("输入契约必须禁止未声明参数")

    properties = schema.get("properties")
    required = schema.get("required", [])
    definitions = schema.get("$defs", {})
    if not isinstance(properties, dict):
        raise BusinessSkillSchemaUnsupportedError("输入契约缺少 properties")
    if not isinstance(required, list) or not all(
        isinstance(name, str) for name in required
    ):
        raise BusinessSkillSchemaUnsupportedError("required 必须是字段名数组")
    if not isinstance(definitions, dict):
        raise BusinessSkillSchemaUnsupportedError("$defs 必须是对象")
    unknown_required = set(required) - set(properties)
    if unknown_required:
        raise BusinessSkillSchemaUnsupportedError("required 包含未知字段")

    fields: list[BusinessSkillFieldContract] = []
    required_names = set(required)
    for name, raw_property in properties.items():
        if not isinstance(name, str) or not name:
            raise BusinessSkillSchemaUnsupportedError("字段名不能为空")
        if not isinstance(raw_property, dict):
            raise BusinessSkillSchemaUnsupportedError(f"字段 {name} 定义无效")
        property_schema = _resolve_property(raw_property, definitions, name)
        if set(property_schema) - _FIELD_KEYS:
            raise BusinessSkillSchemaUnsupportedError(
                f"字段 {name} 使用了暂不支持的复杂规则",
            )
        value_type = property_schema.get("type")
        if value_type not in _SUPPORTED_TYPES:
            raise BusinessSkillSchemaUnsupportedError(
                f"字段 {name} 的类型暂不支持",
            )
        enum_values = property_schema.get("enum")
        if enum_values is not None and (
            not isinstance(enum_values, list) or not enum_values
        ):
            raise BusinessSkillSchemaUnsupportedError(
                f"字段 {name} 的 enum 定义无效",
            )
        field = BusinessSkillFieldContract(
            name=name,
            value_type=value_type,
            required=name in required_names,
            has_default="default" in property_schema,
            default=property_schema.get("default"),
            enum=tuple(enum_values) if enum_values is not None else None,
            schema=property_schema,
        )
        if field.has_default:
            _normalize_scalar(field, field.default)
        if field.enum is not None:
            for enum_value in field.enum:
                _normalize_scalar(field, enum_value, validate_enum=False)
        fields.append(field)
    return tuple(fields)


def _resolve_property(
    property_schema: dict[str, Any],
    definitions: dict[str, Any],
    field_name: str,
) -> dict[str, Any]:
    reference = property_schema.get("$ref")
    if reference is None:
        return dict(property_schema)
    prefix = "#/$defs/"
    if not isinstance(reference, str) or not reference.startswith(prefix):
        raise BusinessSkillSchemaUnsupportedError(
            f"字段 {field_name} 使用了不支持的 Schema 引用",
        )
    definition = definitions.get(reference.removeprefix(prefix))
    if not isinstance(definition, dict) or "$ref" in definition:
        raise BusinessSkillSchemaUnsupportedError(
            f"字段 {field_name} 的 Schema 引用无效",
        )
    return {**definition, **{key: value for key, value in property_schema.items() if key != "$ref"}}


def _normalize_scalar(
    field: BusinessSkillFieldContract,
    value: Any,
    *,
    validate_enum: bool = True,
) -> Any:
    if field.value_type == "string":
        if not isinstance(value, str):
            raise BusinessSkillInputValidationError(
                f"参数 {field.name} 必须是字符串",
            )
        normalized: Any = value
        min_length = field.schema.get("minLength")
        max_length = field.schema.get("maxLength")
        if isinstance(min_length, int) and len(value) < min_length:
            raise BusinessSkillInputValidationError(
                f"参数 {field.name} 长度不能小于 {min_length}",
            )
        if isinstance(max_length, int) and len(value) > max_length:
            raise BusinessSkillInputValidationError(
                f"参数 {field.name} 长度不能大于 {max_length}",
            )
        pattern = field.schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            raise BusinessSkillInputValidationError(
                f"参数 {field.name} 格式不正确",
            )
    elif field.value_type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise BusinessSkillInputValidationError(
                f"参数 {field.name} 必须是整数",
            )
        normalized = value
    elif field.value_type == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise BusinessSkillInputValidationError(
                f"参数 {field.name} 必须是数字",
            )
        normalized = float(value)
        if not math.isfinite(normalized):
            raise BusinessSkillInputValidationError(
                f"参数 {field.name} 必须是有限数字",
            )
    else:
        if not isinstance(value, bool):
            raise BusinessSkillInputValidationError(
                f"参数 {field.name} 必须是布尔值",
            )
        normalized = value

    if field.value_type in {"integer", "number"}:
        _validate_number_constraints(field, normalized)
    if validate_enum and field.enum is not None and normalized not in field.enum:
        raise BusinessSkillInputValidationError(
            f"参数 {field.name} 不在允许的选项中",
        )
    return normalized


def _validate_number_constraints(
    field: BusinessSkillFieldContract,
    value: int | float,
) -> None:
    constraints = (
        ("minimum", lambda candidate, limit: candidate >= limit),
        ("maximum", lambda candidate, limit: candidate <= limit),
        ("exclusiveMinimum", lambda candidate, limit: candidate > limit),
        ("exclusiveMaximum", lambda candidate, limit: candidate < limit),
    )
    for key, predicate in constraints:
        limit = field.schema.get(key)
        if isinstance(limit, (int, float)) and not predicate(value, limit):
            raise BusinessSkillInputValidationError(
                f"参数 {field.name} 超出允许范围",
            )
    multiple_of = field.schema.get("multipleOf")
    if isinstance(multiple_of, (int, float)) and multiple_of > 0:
        quotient = value / multiple_of
        if not math.isclose(quotient, round(quotient), rel_tol=1e-9, abs_tol=1e-9):
            raise BusinessSkillInputValidationError(
                f"参数 {field.name} 不符合步进约束",
            )
