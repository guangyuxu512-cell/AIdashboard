import { flushPromises, shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import FormDialog from '@/shared/components/FormDialog.vue'
import AppButton from '@/shared/ui/AppButton.vue'

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

    expect(wrapper.text()).toContain('公共值：1')
    expect(wrapper.text()).toContain('恢复公共值 · 页码')
    wrapper
      .findAllComponents(AppButton)
      .find((button) => button.text() === '恢复公共值 · 页码')!
      .vm.$emit('click')
    wrapper.findComponent(FormDialog).vm.$emit('submit')
    await flushPromises()

    expect(wrapper.emitted('confirm')).toEqual([[{}]])
  })
})
