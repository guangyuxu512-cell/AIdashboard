import type {
  SchemaParameterField,
  SchemaParameterScalar,
  SchemaParameterValueType,
} from '@/shared/types/schema-parameter'
import { isSchemaParameterScalar } from '@/shared/utils/schema-parameters'

export type BusinessSkillSchemaParseResult =
  | { supported: true; fields: SchemaParameterField[] }
  | { supported: false; reason: string }

export function parseBusinessSkillInputSchema(
  schema: Record<string, unknown>,
): BusinessSkillSchemaParseResult {
  if (schema.type !== 'object' || schema.additionalProperties !== false) {
    return unsupported('输入契约不是受支持的封闭对象')
  }
  if (!isRecord(schema.properties)) {
    return unsupported('输入契约缺少 properties')
  }
  const required = Array.isArray(schema.required) ? schema.required : []
  if (!required.every((name) => typeof name === 'string')) {
    return unsupported('required 定义无效')
  }
  const definitions = isRecord(schema.$defs) ? schema.$defs : {}
  const fields: SchemaParameterField[] = []

  for (const [name, rawProperty] of Object.entries(schema.properties)) {
    if (!isRecord(rawProperty)) return unsupported(`字段 ${name} 定义无效`)
    const resolved = resolveProperty(rawProperty, definitions)
    if (!resolved) return unsupported(`字段 ${name} 的引用暂不支持`)
    const valueType = resolved.type
    if (!isValueType(valueType)) {
      return unsupported(`字段 ${name} 的类型暂不支持`)
    }
    const enumValues = resolved.enum
    if (
      enumValues !== undefined &&
      (!Array.isArray(enumValues) ||
        !enumValues.length ||
        !enumValues.every(isSchemaParameterScalar))
    ) {
      return unsupported(`字段 ${name} 的选项定义无效`)
    }
    const pattern = optionalString(resolved.pattern)
    if (pattern) {
      try {
        new RegExp(pattern)
      } catch {
        return unsupported(`字段 ${name} 的格式规则暂不支持`)
      }
    }
    const hasDefault = Object.hasOwn(resolved, 'default')
    const defaultValue = resolved.default
    if (hasDefault && !isSchemaParameterScalar(defaultValue)) {
      return unsupported(`字段 ${name} 的默认值暂不支持`)
    }
    fields.push({
      name,
      label: optionalString(resolved.title) ?? name,
      ...(optionalString(resolved.description)
        ? { description: optionalString(resolved.description) }
        : {}),
      control: enumValues ? 'select' : valueType,
      valueType,
      required: required.includes(name),
      hasDefault,
      ...(hasDefault
        ? { defaultValue: defaultValue as SchemaParameterScalar }
        : {}),
      ...(enumValues
        ? { options: enumValues as SchemaParameterScalar[] }
        : {}),
      ...numberProperty('min', resolved.minimum),
      ...numberProperty('max', resolved.maximum),
      ...numberProperty('exclusiveMin', resolved.exclusiveMinimum),
      ...numberProperty('exclusiveMax', resolved.exclusiveMaximum),
      ...numberProperty('step', resolved.multipleOf),
      ...integerProperty('minLength', resolved.minLength),
      ...integerProperty('maxLength', resolved.maxLength),
      ...(pattern ? { pattern } : {}),
    })
  }
  return { supported: true, fields }
}

function resolveProperty(
  property: Record<string, unknown>,
  definitions: Record<string, unknown>,
): Record<string, unknown> | null {
  if (property.$ref === undefined) return property
  if (
    typeof property.$ref !== 'string' ||
    !property.$ref.startsWith('#/$defs/')
  ) {
    return null
  }
  const definition = definitions[property.$ref.slice('#/$defs/'.length)]
  if (!isRecord(definition) || definition.$ref !== undefined) return null
  const overrides = Object.fromEntries(
    Object.entries(property).filter(([key]) => key !== '$ref'),
  )
  return { ...definition, ...overrides }
}

function isValueType(value: unknown): value is SchemaParameterValueType {
  return ['string', 'integer', 'number', 'boolean'].includes(String(value))
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function optionalString(value: unknown): string | undefined {
  return typeof value === 'string' && value ? value : undefined
}

function numberProperty<Key extends string>(
  key: Key,
  value: unknown,
): Partial<Record<Key, number>> {
  return typeof value === 'number' && Number.isFinite(value)
    ? ({ [key]: value } as Partial<Record<Key, number>>)
    : {}
}

function integerProperty<Key extends string>(
  key: Key,
  value: unknown,
): Partial<Record<Key, number>> {
  return typeof value === 'number' && Number.isInteger(value)
    ? ({ [key]: value } as Partial<Record<Key, number>>)
    : {}
}

function unsupported(reason: string): BusinessSkillSchemaParseResult {
  return { supported: false, reason }
}
