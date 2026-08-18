import { describe, expect, it } from 'vitest'

import {
  SHOP_ENABLED_STATUS_META,
  SHOP_PLATFORM_META,
  SHOP_PLATFORM_NAV_ITEMS,
} from './status-meta'

describe('shop status metadata', () => {
  it('keeps labels and tones in entity metadata', () => {
    expect(SHOP_ENABLED_STATUS_META.enabled).toEqual({
      label: '已启用',
      tone: 'success',
    })
    expect(SHOP_PLATFORM_META.douyin.label).toBe('抖店')
    expect(SHOP_PLATFORM_META.pdd.icon).toMatch(/^(data:image|\/src\/)/)
    expect(SHOP_PLATFORM_NAV_ITEMS.map((item) => item.value)).toEqual([
      'all',
      'douyin',
      'pdd',
      'taobao',
      'wechat_channels',
    ])
  })
})
