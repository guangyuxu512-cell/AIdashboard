import { describe, expect, it } from 'vitest'

import {
  SHOP_ENABLED_STATUS_META,
} from './status-meta'

describe('shop status metadata', () => {
  it('keeps labels and tones in entity metadata', () => {
    expect(SHOP_ENABLED_STATUS_META.enabled).toEqual({
      label: '已启用',
      tone: 'success',
    })
  })
})
