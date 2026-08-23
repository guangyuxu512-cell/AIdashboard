import { describe, expect, it } from 'vitest'

import type {
  DeviceListItemViewModel,
  DeviceSkillCapabilityViewModel,
  YingdaoInventoryViewModel,
} from '@/entities/device'

import {
  isInitialQueryError,
  isInitialQueryLoading,
  resolveYingdaoApplicationRunAvailability,
} from './device-capability-state'

const device = {
  enabled: true,
  runtimeStatus: 'online',
} as DeviceListItemViewModel
const runSkill = {
  skillId: 'yingdao.app.run',
} as DeviceSkillCapabilityViewModel
const inventory = {
  providerStatus: 'ready',
  providerVersion: '6.3.6',
  loggedIn: true,
  executionAvailable: true,
} as YingdaoInventoryViewModel

describe('Device capability query presentation', () => {
  it('distinguishes initial loading, empty success, initial error, and cached background error', () => {
    expect(isInitialQueryLoading(true, undefined)).toBe(true)
    expect(isInitialQueryLoading(false, [])).toBe(false)
    expect(isInitialQueryError(new Error('request failed'), undefined)).toBe(
      true,
    )
    expect(isInitialQueryError(new Error('background failed'), [])).toBe(false)
    expect(isInitialQueryError(null, [runSkill])).toBe(false)
  })
})

describe('Yingdao application run availability', () => {
  type AvailabilityInput = Parameters<
    typeof resolveYingdaoApplicationRunAvailability
  >[0]

  function resolve(
    overrides: Partial<
      Parameters<typeof resolveYingdaoApplicationRunAvailability>[0]
    > = {},
  ) {
    return resolveYingdaoApplicationRunAvailability({
      device,
      skills: [runSkill],
      inventory,
      ...overrides,
    })
  }

  it('enables a valid application when device, Skill and Provider are ready', () => {
    expect(
      resolve({
        application: { appId: 'app-1', appName: '应用 1', versionId: '1' },
      }),
    ).toEqual({ enabled: true, disabledReason: null })
  })

  const disabledCases: Array<[Partial<AvailabilityInput>, string]> = [
    [{ device: { ...device, runtimeStatus: 'offline' } }, '设备当前离线'],
    [{ device: { ...device, enabled: false } }, '设备已停用'],
    [{ skills: [] }, '当前 Worker 未声明 yingdao.app.run Skill'],
    [
      {
        inventory: {
          ...inventory,
          providerStatus: 'not_installed',
          providerVersion: '',
          loggedIn: false,
          executionAvailable: false,
        },
      },
      '未检测到影刀 6.3.6',
    ],
    [
      {
        inventory: {
          ...inventory,
          providerStatus: 'interface_unreachable',
          loggedIn: false,
          executionAvailable: false,
        },
      },
      '影刀本地接口当前不可用',
    ],
    [
      {
        inventory: {
          ...inventory,
          providerStatus: 'need_login',
          loggedIn: false,
          executionAvailable: false,
        },
      },
      '影刀 6.3.6 当前需要登录',
    ],
    [
      {
        inventory: {
          ...inventory,
          providerStatus: 'version_unsupported',
          providerVersion: '6.3.9',
          executionAvailable: false,
        },
      },
      '影刀版本不受支持，当前仅支持 6.3.6',
    ],
    [
      {
        application: { appId: '', appName: '不可用应用', versionId: null },
      },
      '当前 Application 不可用',
    ],
  ]

  it.each(disabledCases)(
    'returns the first actionable disabled reason',
    (overrides, reason) => {
      expect(resolve(overrides).disabledReason).toBe(reason)
    },
  )
})
