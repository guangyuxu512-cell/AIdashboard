import { describe, expect, it } from 'vitest'

import {
  DEVICE_CAPABILITY_AVAILABILITY_META,
  DEVICE_CAPABILITY_META,
  DEVICE_ENABLED_STATUS_META,
  DEVICE_STATUS_META,
} from './status-meta'

describe('device metadata', () => {
  it('keeps device status labels and tones in the entity layer', () => {
    expect(DEVICE_STATUS_META.online).toEqual({
      label: '在线',
      tone: 'success',
    })
    expect(DEVICE_STATUS_META.error).toEqual({ label: '异常', tone: 'error' })
    expect(DEVICE_STATUS_META.unavailable.label).toBe('未接入')
    expect(DEVICE_ENABLED_STATUS_META.enabled.label).toBe('已启用')
    expect(DEVICE_CAPABILITY_META.browser.label).toBe('Browser')
    expect(DEVICE_CAPABILITY_AVAILABILITY_META.unavailable.tone).toBe('neutral')
  })
})
