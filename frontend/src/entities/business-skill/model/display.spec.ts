import { describe, expect, it } from 'vitest'

import { formatSkillName } from './display'

describe('skill display names', () => {
  it.each([
    ['douyin.compass_selection', '罗盘选品'],
    ['douyin.category_schema', '商品类目与预检'],
    ['system.rpa_inventory_diagnostic', 'RPA 店铺连接诊断'],
  ])('names the existing skill %s', (id, expected) => {
    expect(formatSkillName(id, id)).toBe(expected)
  })

  it('handles built-in English names and keeps server-provided names and unknown skills', () => {
    expect(formatSkillName('system.echo', 'Echo')).toBe('消息回显（测试）')
    expect(formatSkillName('system.sleep', 'Sleep')).toBe('等待（测试）')
    expect(formatSkillName('douyin.compass_selection', '专用选品')).toBe('专用选品')
    expect(formatSkillName('custom.new_skill', '新技能')).toBe('新技能')
    expect(formatSkillName('custom.new_skill', '')).toBe('custom.new_skill')
  })
})
