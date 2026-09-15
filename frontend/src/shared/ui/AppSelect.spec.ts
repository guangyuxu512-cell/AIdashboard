import { shallowMount } from '@vue/test-utils'
import { NSelect } from 'naive-ui'
import { describe, expect, it } from 'vitest'

import AppSelect from './AppSelect.vue'

describe('AppSelect', () => {
  it('forwards multiple selection and collapsed tag settings', () => {
    const wrapper = shallowMount(AppSelect, {
      props: {
        modelValue: ['one', 'two'],
        options: [
          { label: 'One', value: 'one' },
          { label: 'Two', value: 'two' },
        ],
        multiple: true,
        maxTagCount: 1,
      },
    })

    expect(wrapper.findComponent(NSelect).props()).toMatchObject({
      value: ['one', 'two'],
      multiple: true,
      maxTagCount: 1,
    })

    wrapper.findComponent(NSelect).vm.$emit('update:value', ['one'])
    expect(wrapper.emitted('update:values')).toEqual([[['one']]])
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })

  it('preserves the scalar model update contract', () => {
    const wrapper = shallowMount(AppSelect, {
      props: {
        modelValue: 'one',
        options: [{ label: 'One', value: 'one' }],
      },
    })

    wrapper.findComponent(NSelect).vm.$emit('update:value', 'one')
    expect(wrapper.emitted('update:modelValue')).toEqual([['one']])
    expect(wrapper.emitted('update:values')).toBeUndefined()
  })

  it('can keep a popup inside an existing overlay host', () => {
    const wrapper = shallowMount(AppSelect, {
      props: {
        options: [{ label: 'One', value: 'one' }],
        to: '#app-overlay-host',
      },
    })

    expect(wrapper.findComponent(NSelect).props('to')).toBe(
      '#app-overlay-host',
    )
  })
})
