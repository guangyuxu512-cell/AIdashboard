import { shallowMount } from '@vue/test-utils'
import { NDatePicker } from 'naive-ui'
import { describe, expect, it } from 'vitest'

import AppDatePicker from './AppDatePicker.vue'

describe('AppDatePicker', () => {
  it('uses the fixed single-date control class at the shared medium size', () => {
    const wrapper = shallowMount(AppDatePicker)

    expect(wrapper.findComponent(NDatePicker).props()).toMatchObject({
      size: 'medium',
      type: 'date',
    })
    expect(wrapper.findComponent(NDatePicker).classes()).toContain(
      'app-date-picker',
    )
    expect(wrapper.findComponent(NDatePicker).classes()).not.toContain(
      'app-date-picker--range',
    )
  })

  it('uses the shared range-width class without changing the date contract', () => {
    const value: [number, number] = [1, 2]
    const wrapper = shallowMount(AppDatePicker, {
      props: { modelValue: value, type: 'daterange' },
    })

    expect(wrapper.findComponent(NDatePicker).props()).toMatchObject({
      value,
      type: 'daterange',
    })
    expect(wrapper.findComponent(NDatePicker).classes()).toContain(
      'app-date-picker--range',
    )

    wrapper.findComponent(NDatePicker).vm.$emit('update:value', value)
    expect(wrapper.emitted('update:modelValue')).toEqual([[value]])
  })
})
