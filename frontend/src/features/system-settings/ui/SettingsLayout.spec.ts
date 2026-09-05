import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SettingsLayout from './SettingsLayout.vue'

describe('SettingsLayout', () => {
  it('renders one settings surface with internal navigation and content', () => {
    const wrapper = mount(SettingsLayout, {
      slots: { default: '<div data-test="settings-content">内容区</div>' },
      global: {
        stubs: {
          SettingsSideNav: {
            template: '<nav aria-label="系统设置">设置导航</nav>',
          },
        },
      },
    })

    expect(wrapper.get('.settings-layout__surface')).toBeTruthy()
    expect(wrapper.get('.settings-layout__navigation nav').text()).toBe(
      '设置导航',
    )
    expect(wrapper.get('[data-test="settings-content"]').text()).toBe('内容区')
  })
})
