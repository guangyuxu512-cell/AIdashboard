import type {
  SchemaParameterField,
  SchemaParameterScalar,
} from '@/shared/types/schema-parameter'

export function createDefaultSchemaParameters(
  fields: SchemaParameterField[],
  existing: Record<string, unknown> = {},
): Record<string, unknown> {
  return Object.fromEntries(
    fields.flatMap((field) => {
      if (Object.hasOwn(existing, field.name)) {
        return [[field.name, existing[field.name]]]
      }
      return field.hasDefault ? [[field.name, field.defaultValue]] : []
    }),
  )
}

export function validateSchemaParameters(
  fields: SchemaParameterField[],
  values: Record<string, unknown>,
): string | null {
  for (const field of fields) {
    const value = values[field.name]
    const missing =
      value === null ||
      value === undefined ||
      (field.valueType === 'string' && value === '')
    if (field.required && missing) return `请填写${field.label}`
    if (missing) continue

    if (!matchesValueType(field.valueType, value)) {
      return `${field.label}的参数类型不正确`
    }
    if (
      field.options?.length &&
      !field.options.some((option) => Object.is(option, value))
    ) {
      return `${field.label}不在允许的选项中`
    }
    if (typeof value === 'string') {
      if (field.minLength !== undefined && value.length < field.minLength) {
        return `${field.label}长度不能小于 ${field.minLength}`
      }
      if (field.maxLength !== undefined && value.length > field.maxLength) {
        return `${field.label}长度不能大于 ${field.maxLength}`
      }
      if (field.pattern && !new RegExp(field.pattern).test(value)) {
        return `${field.label}格式不正确`
      }
    }
    if (typeof value === 'number') {
      if (!Number.isFinite(value)) return `${field.label}必须是有限数字`
      if (field.min !== undefined && value < field.min) {
        return `${field.label}不能小于 ${field.min}`
      }
      if (field.max !== undefined && value > field.max) {
        return `${field.label}不能大于 ${field.max}`
      }
      if (field.exclusiveMin !== undefined && value <= field.exclusiveMin) {
        return `${field.label}必须大于 ${field.exclusiveMin}`
      }
      if (field.exclusiveMax !== undefined && value >= field.exclusiveMax) {
        return `${field.label}必须小于 ${field.exclusiveMax}`
      }
      if (field.step !== undefined && field.step > 0) {
        const quotient = value / field.step
        if (Math.abs(quotient - Math.round(quotient)) > 1e-9) {
          return `${field.label}不符合步进约束`
        }
      }
    }
  }
  return null
}

export function encodeSchemaOption(value: unknown): string | null {
  if (!isSchemaParameterScalar(value)) return null
  return JSON.stringify({ value })
}

export function decodeSchemaOption(value: string | number | null): unknown {
  if (typeof value !== 'string') return value
  try {
    const parsed = JSON.parse(value) as { value?: unknown }
    return parsed.value
  } catch {
    return value
  }
}

export function isSchemaParameterScalar(
  value: unknown,
): value is SchemaParameterScalar {
  return (
    typeof value === 'string' ||
    typeof value === 'boolean' ||
    (typeof value === 'number' && Number.isFinite(value))
  )
}

function matchesValueType(
  type: SchemaParameterField['valueType'],
  value: unknown,
): boolean {
  if (type === 'string') return typeof value === 'string'
  if (type === 'integer') {
    return typeof value === 'number' && Number.isInteger(value)
  }
  if (type === 'number') {
    return typeof value === 'number' && Number.isFinite(value)
  }
  return typeof value === 'boolean'
}
