import { describe, expect, it } from 'vitest'

import { SHOP_SESSION_STATUS_META } from './status-meta'

describe('ShopSession UI metadata', () => {
  it('maps the four product-facing login states without exposing payload details', () => {
    expect(SHOP_SESSION_STATUS_META.not_configured.label).toBe('未登录')
    expect(SHOP_SESSION_STATUS_META.captured.label).toBe('待验证')
    expect(SHOP_SESSION_STATUS_META.valid.label).toBe('有效')
    expect(SHOP_SESSION_STATUS_META.invalid.label).toBe('已失效')
  })
})
