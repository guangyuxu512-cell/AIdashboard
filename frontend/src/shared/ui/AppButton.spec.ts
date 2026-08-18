import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AppButton from './AppButton.vue'

describe('AppButton', () => {
  it('uses the project default size and forwards clicks', async () => {
    const wrapper = mount(AppButton, {
      props: { tone: 'primary' },
      slots: { default: '保存' },
    })

    expect(wrapper.findComponent({ name: 'Button' }).props('size')).toBe('medium')
    await wrapper.trigger('click')
    expect(wrapper.emitted('click')).toHaveLength(1)
  })
})
