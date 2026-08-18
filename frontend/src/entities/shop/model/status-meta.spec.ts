import { describe, expect, it } from 'vitest'

import {
  SHOP_AUTOMATION_STATUS_META,
  SHOP_CONFIGURATION_STATUS_META,
  SHOP_ENABLED_STATUS_META,
  SHOP_SESSION_STATUS_META,
} from './status-meta'

describe('shop status metadata', () => {
  it('keeps labels and tones in entity metadata', () => {
    expect(SHOP_ENABLED_STATUS_META.enabled).toEqual({
      label: '已启用',
      tone: 'success',
    })
    expect(SHOP_SESSION_STATUS_META.warning).toEqual({
      label: '异常',
      tone: 'error',
    })
    expect(SHOP_AUTOMATION_STATUS_META.running).toEqual({
      label: '运行中',
      tone: 'info',
    })
    expect(SHOP_CONFIGURATION_STATUS_META.not_configured.label).toBe('未配置')
    expect(SHOP_SESSION_STATUS_META.unavailable.label).toBe('未接入')
  })
})
