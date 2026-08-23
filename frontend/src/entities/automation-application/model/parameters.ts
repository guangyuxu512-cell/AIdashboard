import type { AutomationInputSchemaDto } from '../api/contracts'

export function validateAutomationParameters(
  schema: AutomationInputSchemaDto,
  values: Record<string, unknown>,
): string | null {
  for (const field of schema.fields) {
    const value = values[field.name]
    if (
      field.required &&
      (value === null || value === undefined || (field.type === 'text' && value === ''))
    ) {
      return `请填写${field.label}`
    }
    if (value === null || value === undefined) continue
    const valid =
      (field.type === 'text' && typeof value === 'string') ||
      (field.type === 'number' && typeof value === 'number' && Number.isFinite(value)) ||
      (field.type === 'boolean' && typeof value === 'boolean') ||
      (field.type === 'select' &&
        typeof value === 'string' &&
        field.options.includes(value))
    if (!valid) return `${field.label}的参数类型不正确`
  }
  return null
}
