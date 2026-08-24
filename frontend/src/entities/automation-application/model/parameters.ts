import type { AutomationInputSchemaDto } from '../api/contracts'
import type { SchemaParameterField } from '@/shared/types/schema-parameter'
import {
  createDefaultSchemaParameters,
  validateSchemaParameters,
} from '@/shared/utils/schema-parameters'

export function mapAutomationParameterFields(
  schema: AutomationInputSchemaDto,
): SchemaParameterField[] {
  return schema.fields.map((field) => ({
    name: field.name,
    label: field.label,
    control:
      field.type === 'text'
        ? 'string'
        : field.type === 'select'
          ? 'select'
          : field.type,
    valueType:
      field.type === 'text' || field.type === 'select'
        ? 'string'
        : field.type,
    required: field.required,
    hasDefault: field.default_value !== null,
    ...(field.default_value !== null
      ? { defaultValue: field.default_value as string | number | boolean }
      : {}),
    ...(field.type === 'select' ? { options: field.options } : {}),
  }))
}

export function createDefaultAutomationParameters(
  schema: AutomationInputSchemaDto,
  existing: Record<string, unknown> = {},
): Record<string, unknown> {
  return createDefaultSchemaParameters(
    mapAutomationParameterFields(schema),
    existing,
  )
}

export function validateAutomationParameters(
  schema: AutomationInputSchemaDto,
  values: Record<string, unknown>,
): string | null {
  return validateSchemaParameters(mapAutomationParameterFields(schema), values)
}
