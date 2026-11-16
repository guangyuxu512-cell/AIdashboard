import { shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { DeviceListItemViewModel, DeviceSkillCapabilityViewModel } from '@/entities/device'
import DataTable from '@/shared/components/DataTable.vue'
import DeviceCapabilityDrawer from './DeviceCapabilityDrawer.vue'

const device = { deviceId: 'device-1', deviceName: 'Worker 1', enabled: true,
  enabledStatus: 'enabled', runtimeStatus: 'online' } as DeviceListItemViewModel
const skill = { deviceId: 'device-1', skillId: 'refund.sync', displayName: '退款同步',
  runtime: 'python', provider: null, version: '1', classification: 'business',
  inputSchema: null, updatedAtDisplay: '' } as DeviceSkillCapabilityViewModel

describe('Worker capabilities', () => {
  it('shows business skills and filters retired Yingdao capabilities', () => {
    const wrapper = shallowMount(DeviceCapabilityDrawer, {
      props: { show: true, device, skills: [skill, { ...skill, skillId: 'yingdao.app.run' }] },
      global: { renderStubDefaultSlot: true },
    })
    expect(wrapper.findComponent(DataTable).props('data')).toEqual([skill])
    expect(wrapper.text()).not.toContain('影刀')
  })
  it('exposes retry when capability loading fails', () => {
    const wrapper = shallowMount(DeviceCapabilityDrawer, {
      props: { show: true, device, skills: [], skillsError: '读取失败' },
      global: { renderStubDefaultSlot: true },
    })
    expect(wrapper.findComponent({ name: 'ErrorState' }).exists()).toBe(true)
  })
})
