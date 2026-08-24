import type { AutomationInputSchemaDto } from '../api/contracts'

export function createDefaultAutomationParameters(
  schema: AutomationInputSchemaDto,
  existing: Record<string, unknown> = {},
): Record<string, unknown> {
  return Object.fromEntries(
    schema.fields.flatMap((field) => {
      if (Object.hasOwn(existing, field.name)) {
        return [[field.name, existing[field.name]]]
      }
      return field.default_value === null
        ? []
        : [[field.name, field.default_value]]
    }),
  )
}

export function validateAutomationParameters(
  schema: AutomationInputSchemaDto,
  values: Record<string, unknown>,
): string | null {
  for (const field of schema.fields) {
    const value = values[field.name]
    if (
      field.required &&
      (value === null ||
        value === undefined ||
        (field.type === 'text' && value === ''))
    ) {
      return `请填写${field.label}`
    }
    if (value === null || value === undefined) continue
    const valid =
      (field.type === 'text' && typeof value === 'string') ||
      (field.type === 'number' &&
        typeof value === 'number' &&
        Number.isFinite(value)) ||
      (field.type === 'boolean' && typeof value === 'boolean') ||
      (field.type === 'select' &&
        typeof value === 'string' &&
        field.options.includes(value))
    if (!valid) return `${field.label}的参数类型不正确`
  }
  return null
}
