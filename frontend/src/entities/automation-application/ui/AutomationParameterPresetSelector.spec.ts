import { flushPromises, shallowMount } from '@vue/test-utils'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AppButton from '@/shared/ui/AppButton.vue'

import AutomationParameterPresetSelector from './AutomationParameterPresetSelector.vue'

const mocks = vi.hoisted(() => ({
  presets: null as unknown,
}))

vi.mock('../api/queries', () => ({
  useAutomationParameterPresetsQuery: () => mocks.presets,
}))

const preset = {
  preset_id: 'preset-1',
  app_id: 'daily-collection',
  name: '抖店日常采集',
  common_parameters: { 页码: 1, 每页数量: 20 },
  shop_overrides: { 'shop-b': { 页码: 2 } },
  version: 1,
}

beforeEach(() => {
  mocks.presets = { data: ref([preset]), isPending: ref(false) }
})

describe('AutomationParameterPresetSelector', () => {
  it('clearly identifies manual parameter mode when no preset is selected', async () => {
    const wrapper = shallowMount(AutomationParameterPresetSelector, {
      props: {
        appId: preset.app_id,
        modelValue: null,
        schema: {
          fields: [
            {
              name: '页码',
              label: '页码',
              type: 'number',
              required: false,
              default_value: 1,
              options: [],
            },
            {
              name: '每页数量',
              label: '每页数量',
              type: 'number',
              required: false,
              default_value: 20,
              options: [],
            },
          ],
        },
        shopIds: [],
        shopOptions: [],
      },
      global: { renderStubDefaultSlot: true },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('当前使用手动参数')
  })

  it('summarizes shop overrides without rendering raw parameter strings', async () => {
    const wrapper = shallowMount(AutomationParameterPresetSelector, {
      props: {
        appId: preset.app_id,
        modelValue: preset.preset_id,
        schema: { fields: [] },
        shopIds: ['shop-a', 'shop-b'],
        shopOptions: [
          { label: '甲店', value: 'shop-a' },
          { label: '乙店', value: 'shop-b' },
        ],
      },
      global: { renderStubDefaultSlot: true },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('2 家店铺，1 家有单独设置')
    expect(wrapper.text()).not.toContain('页码=1')

    wrapper
      .findAllComponents(AppButton)
      .find((button) => button.text() === '查看本次参数')!
      .vm.$emit('click')
    await flushPromises()

    expect(wrapper.text()).toContain('甲店')
    expect(wrapper.text()).toContain('使用公共参数')
    expect(wrapper.text()).toContain('乙店')
    expect(wrapper.text()).toContain('已单独设置：页码')
    expect(wrapper.text()).toContain('每页数量')
    expect(wrapper.text()).not.toContain('每页数量=20')
  })
})
