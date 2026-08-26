import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { Tabbar as VanTabbar } from 'vant'
import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import App from '@/App.vue'
import { MOBILE_ROUTE_NAMES } from '@/app/router/routes'
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

  it('keeps the Vant tabbar in the Shell grid without a second safe area', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/tasks',
          name: MOBILE_ROUTE_NAMES.tasks,
          component: { template: '<div>任务内容</div>' },
          meta: {
            title: '任务中心',
            requiresAuth: false,
            permission: null,
          },
        },
      ],
    })
    await router.push('/tasks')
    await router.isReady()

    const wrapper = mount(App, {
      global: { plugins: [createPinia(), router] },
    })
    const tabbar = wrapper.getComponent(VanTabbar)

    expect(tabbar.props('fixed')).toBe(false)
    expect(tabbar.props('safeAreaInsetBottom')).toBe(false)
    expect(wrapper.get('footer').find('.van-tabbar').exists()).toBe(true)
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
