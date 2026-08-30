import { shallowMount } from '@vue/test-utils'
import { NCheckbox } from 'naive-ui'
import { describe, expect, it } from 'vitest'

import AppCheckbox from './AppCheckbox.vue'

describe('AppCheckbox', () => {
  it('forwards the controlled indeterminate state', () => {
    const wrapper = shallowMount(AppCheckbox, {
      props: { modelValue: false, indeterminate: true },
    })

    expect(wrapper.findComponent(NCheckbox).props()).toMatchObject({
      checked: false,
      indeterminate: true,
    })
  })
})
