import { describe, expect, it } from 'vitest'

import type { BusinessSkillCatalogItemReadDto } from './contracts'
import { mapBusinessSkillCatalogItem } from './business-skill-mapper'

function catalogItem(
  overrides: Partial<BusinessSkillCatalogItemReadDto> = {},
): BusinessSkillCatalogItemReadDto {
  return {
    device_id: 'device-1',
    skill_id: 'catalog.fixture.run',
    display_name: '目录测试能力',
    runtime: 'python',
    provider: null,
    version: '1.0.0',
    classification: 'business',
    input_schema: null,
    availability: 'schema_unavailable',
    unavailable_reason: '当前 Worker 未上报业务 Skill 输入契约',
    updated_at: '2026-08-25T00:00:00Z',
    ...overrides,
  }
}

describe('mapBusinessSkillCatalogItem', () => {
  it('keeps an old Worker item visible but not configurable without a schema', () => {
    expect(mapBusinessSkillCatalogItem(catalogItem())).toMatchObject({
      availability: 'schema_unavailable',
      configurable: false,
      parameterFields: [],
      unavailableReason: '当前 Worker 未上报业务 Skill 输入契约',
    })
  })

  it('refuses a complex schema even if a stale server marks it available', () => {
    expect(
      mapBusinessSkillCatalogItem(
        catalogItem({
          availability: 'available',
          unavailable_reason: null,
          input_schema: {
            type: 'object',
            properties: { items: { type: 'array' } },
            additionalProperties: false,
          },
        }),
      ),
    ).toMatchObject({
      availability: 'schema_unsupported',
      configurable: false,
      unavailableReason: '字段 items 的类型暂不支持',
    })
  })
})
