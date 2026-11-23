import { flushPromises, shallowMount } from '@vue/test-utils'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { BusinessSkillCatalogItemViewModel } from '@/entities/business-skill'
import { ShopMultiSelector } from '@/entities/shop'
import FormDialog from '@/shared/components/FormDialog.vue'
import SchemaParameterFields from '@/shared/components/SchemaParameterFields.vue'
import AppInput from '@/shared/ui/AppInput.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'
import ScheduleFormDialog from './ScheduleFormDialog.vue'

const mocks = vi.hoisted(() => ({ skills: null as unknown, shops: null as unknown }))
vi.mock('@/entities/business-skill', async (original) => ({
  ...(await original<typeof import('@/entities/business-skill')>()),
  useBusinessSkillCatalogQuery: () => mocks.skills,
}))
vi.mock('@/entities/device', async (original) => ({
  ...(await original<typeof import('@/entities/device')>()),
  useDeviceLocalShopsQuery: () => mocks.shops,
}))
const skill = { deviceId: 'device-1', skillId: 'catalog.fixture.run', displayName: '测试技能',
  version: '1', availability: 'available', unavailableReason: null, configurable: true,
  inputSchema: { type: 'object', properties: { keyword: { type: 'string' } }, required: ['keyword'] },
  parameterFields: [{ name: 'keyword', label: '关键词', control: 'string', valueType: 'string', required: true, hasDefault: false }],
} as BusinessSkillCatalogItemViewModel
beforeEach(() => {
  mocks.skills = { data: ref([skill]), isPending: ref(false), error: ref(null) }
  mocks.shops = { data: ref({ available: true, shops: [
    { shop_name: '本机店铺一', local_shop_id: 'local-1' },
    { shop_name: '本机店铺二', local_shop_id: 'local-2' },
  ] }), isPending: ref(false), error: ref(null) }
})
function mountDialog() {
  return shallowMount(ScheduleFormDialog, { props: { show: true, mode: 'create', schedule: null,
    deviceOptions: [{ label: '设备一', value: 'device-1' }] }, global: { renderStubDefaultSlot: true } })
}
describe('Worker schedule form', () => {
  it('shows the readable skill name while retaining its scheduling ID', async () => {
    mocks.skills = { data: ref([{ ...skill, skillId: 'douyin.compass_selection', displayName: '罗盘选品' }]),
      isPending: ref(false), error: ref(null) }
    const wrapper = mountDialog()
    wrapper.findAllComponents(AppSelect)[0]!.vm.$emit('update:modelValue', 'device-1')
    await flushPromises()
    expect(wrapper.findAllComponents(AppSelect)[1]!.props('options')).toEqual([
      { label: '罗盘选品', value: 'douyin.compass_selection', disabled: false },
    ])
    wrapper.findAllComponents(AppSelect)[1]!.vm.$emit('update:modelValue', 'douyin.compass_selection')
    await flushPromises()
    expect(wrapper.findAllComponents(AppSelect)[1]!.props('modelValue')).toBe('douyin.compass_selection')
  })

  it('selects device inventory and submits local ids with schedule disabled by default', async () => {
    const wrapper = mountDialog()
    wrapper.findComponent(AppInput).vm.$emit('update:modelValue', '测试计划')
    wrapper.findAllComponents(AppSelect)[0]!.vm.$emit('update:modelValue', 'device-1')
    await flushPromises()
    expect(wrapper.findComponent(ShopMultiSelector).props('options')).toEqual([
      { label: '本机店铺一', value: 'local-1', disabled: false },
      { label: '本机店铺二', value: 'local-2', disabled: false },
    ])
    wrapper.findComponent(ShopMultiSelector).vm.$emit('update:modelValue', ['local-1'])
    wrapper.findAllComponents(AppSelect)[1]!.vm.$emit('update:modelValue', 'catalog.fixture.run')
    await flushPromises()
    wrapper.findComponent(SchemaParameterFields).vm.$emit('update:modelValue', { keyword: 'test' })
    await flushPromises()
    wrapper.findComponent(FormDialog).vm.$emit('submit')
    expect(wrapper.emitted('submit')?.[0]?.[0]).toMatchObject({ deviceId: 'device-1',
      shopIds: ['local-1'], skillId: 'catalog.fixture.run', enabled: false })
  })
  it('clears selected local shops when switching devices', async () => {
    const wrapper = mountDialog()
    wrapper.findAllComponents(AppSelect)[0]!.vm.$emit('update:modelValue', 'device-1')
    await flushPromises()
    wrapper.findComponent(ShopMultiSelector).vm.$emit('update:modelValue', ['local-1'])
    wrapper.findAllComponents(AppSelect)[0]!.vm.$emit('update:modelValue', 'device-2')
    await flushPromises()
    expect(wrapper.findComponent(ShopMultiSelector).props('modelValue')).toEqual([])
  })
})
