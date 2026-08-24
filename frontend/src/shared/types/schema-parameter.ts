export type SchemaParameterScalar = string | number | boolean

export type SchemaParameterValueType =
  | 'string'
  | 'integer'
  | 'number'
  | 'boolean'

export type SchemaParameterControl =
  | SchemaParameterValueType
  | 'select'

export interface SchemaParameterField {
  name: string
  label: string
  description?: string
  control: SchemaParameterControl
  valueType: SchemaParameterValueType
  required: boolean
  hasDefault: boolean
  defaultValue?: SchemaParameterScalar
  options?: SchemaParameterScalar[]
  min?: number
  max?: number
  exclusiveMin?: number
  exclusiveMax?: number
  step?: number
  minLength?: number
  maxLength?: number
  pattern?: string
}
