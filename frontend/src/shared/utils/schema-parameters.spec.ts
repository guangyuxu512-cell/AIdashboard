import { describe, expect, it } from 'vitest'

import type { SchemaParameterField } from '@/shared/types/schema-parameter'

import {
  createDefaultSchemaParameters,
  decodeSchemaOption,
  encodeSchemaOption,
  validateSchemaParameters,
} from './schema-parameters'

const fields: SchemaParameterField[] = [
  {
    name: 'keyword',
    label: '关键词',
    control: 'string',
    valueType: 'string',
    required: true,
    hasDefault: false,
  },
  {
    name: 'count',
    label: '数量',
    control: 'integer',
    valueType: 'integer',
    required: false,
    hasDefault: true,
    defaultValue: 2,
    min: 1,
  },
  {
    name: 'mode',
    label: '模式',
    control: 'select',
    valueType: 'string',
    required: false,
    hasDefault: true,
    defaultValue: 'safe',
    options: ['safe', 'fast'],
  },
]

describe('schema parameters', () => {
  it('applies defaults and preserves explicit values', () => {
    expect(createDefaultSchemaParameters(fields)).toEqual({
      count: 2,
      mode: 'safe',
    })
    expect(
      createDefaultSchemaParameters(fields, {
        keyword: '退款',
        count: 5,
      }),
    ).toEqual({ keyword: '退款', count: 5, mode: 'safe' })
  })

  it('validates required, integer, range and enum rules', () => {
    expect(validateSchemaParameters(fields, {})).toBe('请填写关键词')
    expect(
      validateSchemaParameters(fields, { keyword: '退款', count: 1.5 }),
    ).toBe('数量的参数类型不正确')
    expect(
      validateSchemaParameters(fields, {
        keyword: '退款',
        count: 2,
        mode: 'unknown',
      }),
    ).toBe('模式不在允许的选项中')
    expect(
      validateSchemaParameters(fields, {
        keyword: '退款',
        count: 2,
        mode: 'safe',
      }),
    ).toBeNull()
  })

  it('round-trips boolean and number select values', () => {
    expect(decodeSchemaOption(encodeSchemaOption(true))).toBe(true)
    expect(decodeSchemaOption(encodeSchemaOption(2))).toBe(2)
  })
})
