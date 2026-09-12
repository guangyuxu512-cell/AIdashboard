import { flushPromises, shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import FormDialog from '@/shared/components/FormDialog.vue'
import AutomationParameterFields from './AutomationParameterFields.vue'

import AutomationParameterPresetShopOverrideDialog from './AutomationParameterPresetShopOverrideDialog.vue'

const schema = {
  fields: [
    {
      name: '页码',
      label: '页码',
      type: 'number' as const,
      required: false,
      default_value: 1,
      options: [],
    },
  ],
}

describe('AutomationParameterPresetShopOverrideDialog', () => {
  it('does not change the parent draft when cancelled', async () => {
    const wrapper = shallowMount(AutomationParameterPresetShopOverrideDialog, {
      props: {
        show: true,
        shopId: 'shop-a',
        shopName: '甲店',
        schema,
        commonParameters: { 页码: 1 },
        shopOverrides: { 页码: 2 },
      },
      global: { renderStubDefaultSlot: true },
    })
    await flushPromises()

    wrapper.findComponent(FormDialog).vm.$emit('cancel')
    await flushPromises()

    expect(wrapper.emitted('confirm')).toBeUndefined()
  })

  it('preserves zero and can restore the public value before confirming', async () => {
    const wrapper = shallowMount(AutomationParameterPresetShopOverrideDialog, {
      props: {
        show: true,
        shopId: 'shop-a',
        shopName: '甲店',
        schema,
        commonParameters: { 页码: 1 },
        shopOverrides: { 页码: 0 },
      },
      global: { renderStubDefaultSlot: true },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('字段')
    expect(wrapper.text()).toContain('公共值')
    expect(wrapper.text()).toContain('本店值')
    expect(wrapper.text()).toContain('恢复')
    const fields = wrapper.findComponent(AutomationParameterFields)
    expect(fields.props('layout')).toBe('comparison')
    expect(fields.props('referenceValues')).toEqual({ 页码: 1 })
    fields.vm.$emit('restore', '页码')
    wrapper.findComponent(FormDialog).vm.$emit('submit')
    await flushPromises()

    expect(wrapper.emitted('confirm')).toEqual([[{}]])
  })
})
