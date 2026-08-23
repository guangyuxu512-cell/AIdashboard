import { shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import type {
  DeviceListItemViewModel,
  DeviceSkillCapabilityViewModel,
  YingdaoInventoryViewModel,
} from '@/entities/device'

import DeviceCapabilityDrawer from './DeviceCapabilityDrawer.vue'
import YingdaoApplicationsTable from './YingdaoApplicationsTable.vue'

const device = {
  deviceId: 'device-11',
  deviceName: '11',
  enabled: true,
  enabledStatus: 'enabled',
  runtimeStatus: 'online',
} as DeviceListItemViewModel

const runSkill: DeviceSkillCapabilityViewModel = {
  deviceId: 'device-11',
  skillId: 'yingdao.app.run',
  displayName: '运行影刀应用',
  runtime: 'rpa',
  provider: 'yingdao',
  version: '1',
  updatedAtDisplay: '2026-08-23 12:00',
}

const inventory = {
  providerStatus: 'ready',
  executionAvailable: true,
  loggedIn: true,
  providerVersion: '6.3.6',
  accountDisplay: 'GY00999',
  applicationCount: 1,
  applications: [
    { appId: 'safe-app', appName: 'Safe App', versionId: '1' },
  ],
} as YingdaoInventoryViewModel

describe('DeviceCapabilityDrawer', () => {
  it('keeps registered Skills separate from Yingdao Applications', () => {
    const wrapper = shallowMount(DeviceCapabilityDrawer, {
      props: {
        show: true,
        device,
        skills: [runSkill],
        yingdaoInventory: inventory,
      },
      global: { renderStubDefaultSlot: true },
    })

    expect(wrapper.text()).toContain('已注册 Skill')
    expect(wrapper.text()).toContain('影刀应用')
    expect(wrapper.text()).toContain('不等同于 Skill')
    expect(
      wrapper.findComponent(YingdaoApplicationsTable).props('runDisabledReason'),
    ).toBeNull()
  })

  it('disables application execution when the Worker did not declare the Skill', () => {
    const wrapper = shallowMount(DeviceCapabilityDrawer, {
      props: {
        show: true,
        device,
        skills: [],
        yingdaoInventory: inventory,
      },
      global: { renderStubDefaultSlot: true },
    })

    expect(wrapper.text()).toContain('未声明 yingdao.app.run Skill')
    expect(
      wrapper.findComponent(YingdaoApplicationsTable).props('runDisabledReason'),
    ).toBe('当前 Worker 未声明 yingdao.app.run Skill')
  })

  it('does not expose applications when the Provider is not ready', () => {
    const wrapper = shallowMount(DeviceCapabilityDrawer, {
      props: {
        show: true,
        device,
        skills: [runSkill],
        yingdaoInventory: {
          ...inventory,
          providerStatus: 'need_login',
          executionAvailable: false,
        },
      },
      global: { renderStubDefaultSlot: true },
    })

    expect(wrapper.findComponent(YingdaoApplicationsTable).exists()).toBe(false)
    expect(wrapper.text()).toContain('影刀 6.3.6 当前需要登录')
  })

  it('renders an Empty State for a successful empty Skill snapshot', () => {
    const wrapper = shallowMount(DeviceCapabilityDrawer, {
      props: {
        show: true,
        device,
        skills: [],
        skillsLoading: false,
        skillsError: null,
        yingdaoInventory: inventory,
      },
      global: { renderStubDefaultSlot: true },
    })

    expect(
      wrapper.findComponent({ name: 'EmptyState' }).props('description'),
    ).toContain('暂无已注册 Skill')
    expect(wrapper.text()).not.toContain('加载失败')
  })

  it('keeps cached Skills visible during a background refresh failure', () => {
    const wrapper = shallowMount(DeviceCapabilityDrawer, {
      props: {
        show: true,
        device,
        skills: [runSkill],
        skillsError: null,
        yingdaoInventory: inventory,
      },
      global: { renderStubDefaultSlot: true },
    })

    expect(wrapper.findComponent(YingdaoApplicationsTable).exists()).toBe(true)
    expect(wrapper.text()).not.toContain('加载失败')
  })
})
