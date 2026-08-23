import { describe, expect, it } from 'vitest'

import {
  DEVICE_CAPABILITY_AVAILABILITY_META,
  DEVICE_CAPABILITY_META,
  DEVICE_ENABLED_STATUS_META,
  DEVICE_STATUS_META,
  YINGDAO_PROVIDER_STATUS_META,
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

  it('maps every ShadowBot Provider lifecycle state', () => {
    expect(YINGDAO_PROVIDER_STATUS_META.not_installed.label).toBe('未安装')
    expect(YINGDAO_PROVIDER_STATUS_META.version_unsupported.label).toBe(
      '版本不支持',
    )
    expect(YINGDAO_PROVIDER_STATUS_META.starting.label).toBe('正在启动')
    expect(YINGDAO_PROVIDER_STATUS_META.need_login.label).toBe('需要登录')
    expect(YINGDAO_PROVIDER_STATUS_META.interface_unreachable.label).toBe(
      '接口不可达',
    )
    expect(YINGDAO_PROVIDER_STATUS_META.ready.label).toBe('已就绪')
  })
})
