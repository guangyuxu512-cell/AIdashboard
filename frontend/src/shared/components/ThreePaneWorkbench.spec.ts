import { h } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ThreePaneWorkbench from './ThreePaneWorkbench.vue'
import threePaneWorkbenchSource from './ThreePaneWorkbench.vue?raw'

describe('ThreePaneWorkbench', () => {
  it('renders three independent slots without business data', () => {
    const wrapper = mount(ThreePaneWorkbench, {
      slots: {
        left: () => h('div', { 'data-slot': 'left' }, 'Left'),
        main: () => h('div', { 'data-slot': 'main' }, 'Main'),
        right: () => h('div', { 'data-slot': 'right' }, 'Right'),
      },
    })

    expect(wrapper.findAll('[data-slot]')).toHaveLength(3)
    expect(wrapper.text()).toContain('Left')
    expect(wrapper.text()).toContain('Main')
    expect(wrapper.text()).toContain('Right')
  })

  it('keeps shrink and overflow boundaries on the layout and panes', () => {
    const wrapper = mount(ThreePaneWorkbench)

    expect(wrapper.classes()).toContain('three-pane-workbench')
    expect(wrapper.findAll('.three-pane-workbench__pane')).toHaveLength(3)
    expect(threePaneWorkbenchSource).toMatch(
      /\.three-pane-workbench\s*{[^}]*min-height:\s*0;[^}]*overflow:\s*hidden;/s,
    )
    expect(threePaneWorkbenchSource).toMatch(
      /\.three-pane-workbench__pane\s*{[^}]*min-height:\s*0;[^}]*overflow:\s*hidden;/s,
    )
    expect(threePaneWorkbenchSource).toMatch(
      /\.three-pane-workbench__pane--right\s*{[^}]*overflow-y:\s*auto;/s,
    )
  })
})
