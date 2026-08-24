import { describe, expect, it } from 'vitest'

import { parseBusinessSkillInputSchema } from './schema-parser'

describe('parseBusinessSkillInputSchema', () => {
  it('maps Pydantic scalar fields, defaults, descriptions and enum refs', () => {
    const result = parseBusinessSkillInputSchema({
      $defs: {
        Mode: {
          enum: ['safe', 'fast'],
          title: 'Mode',
          type: 'string',
        },
      },
      additionalProperties: false,
      properties: {
        keyword: {
          description: '检索关键词',
          title: '关键词',
          type: 'string',
        },
        count: { default: 2, title: '数量', type: 'integer' },
        ratio: { default: 0.5, title: '比例', type: 'number' },
        dry_run: { default: true, title: '仅验证', type: 'boolean' },
        mode: { $ref: '#/$defs/Mode', default: 'safe' },
      },
      required: ['keyword'],
      title: 'CatalogInput',
      type: 'object',
    })

    expect(result.supported).toBe(true)
    if (!result.supported) return
    expect(result.fields.map((field) => field.control)).toEqual([
      'string',
      'integer',
      'number',
      'boolean',
      'select',
    ])
    expect(result.fields[0]).toMatchObject({
      label: '关键词',
      description: '检索关键词',
      required: true,
    })
    expect(result.fields[4]).toMatchObject({
      defaultValue: 'safe',
      options: ['safe', 'fast'],
    })
  })

  it('explicitly rejects complex fields', () => {
    expect(
      parseBusinessSkillInputSchema({
        additionalProperties: false,
        properties: { items: { type: 'array' } },
        type: 'object',
      }),
    ).toEqual({ supported: false, reason: '字段 items 的类型暂不支持' })
  })
})
