import { describe, expect, it } from 'vitest'

import {
  getPlatformCreateOptions,
  getPlatformDefinition,
  getPlatformNavigationItems,
  getPlatformOnboardingOptions,
  PLATFORM_CREATE_OPTIONS,
  PLATFORM_REGISTRY,
  type PlatformDefinition,
} from './registry'

describe('Platform Registry', () => {
  it('drives navigation and create support from one registry', () => {
    expect(getPlatformNavigationItems().map((item) => item.code)).toEqual([
      'douyin',
      'pdd',
      'taobao',
      'wechat_channels',
    ])
    expect(
      PLATFORM_CREATE_OPTIONS.filter((item) => item.disabled).map(
        (item) => item.value,
      ),
    ).toEqual(['taobao', 'wechat_channels'])
    expect(getPlatformOnboardingOptions().map((item) => item.value)).toEqual([
      'douyin',
      'pdd',
      'taobao',
      'wechat_channels',
    ])
    expect(getPlatformOnboardingOptions().every((item) => !item.disabled)).toBe(
      true,
    )
  })

  it('makes a newly registered platform visible to every derived data source', () => {
    const testPlatform: PlatformDefinition = {
      code: 'test-platform',
      label: '测试平台',
      icon: '/test-platform.svg',
      enabled: true,
      registered: true,
      capabilities: {
        legacyShopCreate: 'unavailable',
        credentialManagement: 'unavailable',
        shopOnboarding: 'planned',
        authentication: 'planned',
        sessionCapture: 'planned',
        dataFetch: 'planned',
        rpa: 'planned',
      },
    }
    const registry = [...PLATFORM_REGISTRY, testPlatform]

    expect(getPlatformNavigationItems(registry)).toContainEqual(testPlatform)
    expect(getPlatformCreateOptions(registry)).toContainEqual({
      label: '测试平台',
      value: 'test-platform',
      disabled: true,
    })
    expect(getPlatformOnboardingOptions(registry)).toContainEqual({
      label: '测试平台',
      value: 'test-platform',
      disabled: false,
    })
    expect(getPlatformDefinition('test-platform', registry)).toEqual(
      testPlatform,
    )
  })
})
