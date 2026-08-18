import { describe, expect, it } from 'vitest'

import {
  SHOP_AUTOMATION_STATUS_META,
  SHOP_CONFIGURATION_STATUS_META,
  SHOP_OPERATIONAL_STATUS_META,
  SHOP_SESSION_STATUS_META,
} from './status-meta'

describe('shop status metadata', () => {
  it('keeps labels and tones in entity metadata', () => {
    expect(SHOP_OPERATIONAL_STATUS_META.normal).toEqual({
      label: '正常',
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
  })
})
