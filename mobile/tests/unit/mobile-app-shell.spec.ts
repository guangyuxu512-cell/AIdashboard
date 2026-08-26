import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { MobileAppShell } from '@/shared/ui'

describe('MobileAppShell', () => {
  it('renders the header, default content and bottom slots', () => {
    const wrapper = mount(MobileAppShell, {
      slots: {
        header: '<div>顶部</div>',
        default: '<div>内容</div>',
        bottom: '<div>底部</div>',
      },
    })

    expect(wrapper.get('header').text()).toBe('顶部')
    expect(wrapper.get('main').text()).toBe('内容')
    expect(wrapper.get('footer').text()).toBe('底部')
    expect(wrapper.get('main').classes()).not.toContain(
      'mobile-app-shell__main--without-header',
    )
    expect(wrapper.get('main').classes()).not.toContain(
      'mobile-app-shell__main--without-bottom',
    )
  })

  it('omits empty chrome and activates safe-area fallback classes', () => {
    const wrapper = mount(MobileAppShell, {
      slots: { default: '<div>内容</div>' },
    })

    expect(wrapper.find('header').exists()).toBe(false)
    expect(wrapper.find('footer').exists()).toBe(false)
    expect(wrapper.get('main').classes()).toContain(
      'mobile-app-shell__main--without-header',
    )
    expect(wrapper.get('main').classes()).toContain(
      'mobile-app-shell__main--without-bottom',
    )
  })
})
