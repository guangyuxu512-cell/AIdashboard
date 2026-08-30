import { h } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ContextSwitchBar from './ContextSwitchBar.vue'

describe('ContextSwitchBar', () => {
  it('renders items, active state, icon slot and disabled behavior', async () => {
    const wrapper = mount(ContextSwitchBar, {
      props: {
        label: '上下文切换',
        activeKey: 'first',
        items: [
          { key: 'first', label: '第一项' },
          { key: 'second', label: '第二项' },
          { key: 'disabled', label: '不可用', disabled: true },
        ],
      },
      slots: {
        icon: ({ item }) =>
          h('span', { 'data-icon-key': item.key }, `图标-${item.key}`),
      },
    })

    expect(wrapper.get('nav').attributes('aria-label')).toBe('上下文切换')
    expect(wrapper.findAll('[data-icon-key]')).toHaveLength(3)

    const buttons = wrapper.findAll('button')
    expect(buttons[0]?.attributes('aria-pressed')).toBe('true')
    expect(buttons[1]?.attributes('aria-pressed')).toBe('false')
    expect(buttons[2]?.attributes('disabled')).toBeDefined()

    await buttons[1]?.trigger('click')
    await buttons[2]?.trigger('click')

    expect(wrapper.emitted('select')).toEqual([['second']])
  })
})
