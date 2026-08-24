import { describe, expect, it } from 'vitest'

import {
  createDefaultAutomationParameters,
  validateAutomationParameters,
} from './parameters'

const schema = {
  fields: [
    {
      name: 'keyword',
      label: '关键词',
      type: 'text' as const,
      required: true,
      default_value: null,
      options: [],
    },
    {
      name: 'count',
      label: '数量',
      type: 'number' as const,
      required: false,
      default_value: 1,
      options: [],
    },
  ],
}

describe('validateAutomationParameters', () => {
  it('builds defaults while preserving existing schedule values', () => {
    expect(createDefaultAutomationParameters(schema)).toEqual({ count: 1 })
    expect(
      createDefaultAutomationParameters(schema, { keyword: '保留', count: 3 }),
    ).toEqual({ keyword: '保留', count: 3 })
  })

  it('accepts values matching the configured schema', () => {
    expect(
      validateAutomationParameters(schema, { keyword: '商品', count: 2 }),
    ).toBeNull()
  })

  it('reports missing required and invalid typed values', () => {
    expect(validateAutomationParameters(schema, {})).toBe('请填写关键词')
    expect(
      validateAutomationParameters(schema, { keyword: '商品', count: '2' }),
    ).toBe('数量的参数类型不正确')
  })
})
