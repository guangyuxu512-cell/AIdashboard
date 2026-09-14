import { shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import AppCheckbox from '@/shared/ui/AppCheckbox.vue'
import AppInput from '@/shared/ui/AppInput.vue'

import ShopMultiSelector from './ShopMultiSelector.vue'

const options = [
  { label: 'HuanYu', value: 'shop-1' },
  { label: '店铺02', value: 'shop-2' },
  { label: '已停用店铺', value: 'shop-disabled', disabled: true },
]

describe('ShopMultiSelector', () => {
  it('selects and clears all available shops without selecting disabled rows', async () => {
    const wrapper = shallowMount(ShopMultiSelector, {
      props: { modelValue: [], options },
      global: { renderStubDefaultSlot: true },
    })

    wrapper.findAllComponents(AppCheckbox)[0]!.vm.$emit('update:modelValue', true)
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([
      ['shop-1', 'shop-2'],
    ])

    await wrapper.setProps({ modelValue: ['shop-1', 'shop-2'] })
    wrapper.findAllComponents(AppCheckbox)[0]!.vm.$emit('update:modelValue', false)
    expect(wrapper.emitted('update:modelValue')?.[1]).toEqual([[]])
  })

  it('filters the visible shop list and reports the selected count', async () => {
    vi.useFakeTimers()
    const wrapper = shallowMount(ShopMultiSelector, {
      props: { modelValue: ['shop-2'], options },
      global: { renderStubDefaultSlot: true },
    })

    expect(wrapper.text()).toContain('已选择 1 个店铺')
    wrapper.findComponent(AppInput).vm.$emit('update:modelValue', 'Huan')
    await vi.advanceTimersByTimeAsync(300)
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('HuanYu')
    expect(wrapper.text()).not.toContain('店铺02')
    vi.useRealTimers()
  })

  it('lets schedule editors remove a saved shop that is no longer bound', async () => {
    const wrapper = shallowMount(ShopMultiSelector, {
      props: {
        modelValue: ['shop-unbound', 'shop-1'],
        options,
      },
      global: { renderStubDefaultSlot: true },
    })

    expect(wrapper.text()).toContain('已保存店铺 · shop-unbound')
    wrapper.findAllComponents(AppCheckbox)[1]!.vm.$emit(
      'update:modelValue',
      false,
    )
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([['shop-1']])

    wrapper.findAllComponents(AppCheckbox)[0]!.vm.$emit(
      'update:modelValue',
      false,
    )
    expect(wrapper.emitted('update:modelValue')?.[1]).toEqual([[]])
  })
})
