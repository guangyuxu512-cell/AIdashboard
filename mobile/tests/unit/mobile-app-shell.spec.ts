import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { Tabbar as VanTabbar, TabbarItem as VanTabbarItem } from 'vant'
import { afterEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import App from '@/App.vue'
import { MOBILE_ROUTE_NAMES } from '@/app/router/routes'
import {
  MobileAppShell,
  MobileDetailHeader,
  MobileGlobalHeader,
} from '@/shared/ui'

const mountedWrappers: VueWrapper[] = []
const pageStub = { template: '<div>页面内容</div>' }

function createShellRouter() {
  const mainMeta = (title: string) => ({
    title,
    layout: 'main' as const,
    requiresAuth: false,
    permission: null,
  })
  const detailMeta = (title: string) => ({
    title,
    layout: 'detail' as const,
    requiresAuth: false,
    permission: null,
  })

  return createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/',
        name: MOBILE_ROUTE_NAMES.home,
        component: pageStub,
        meta: mainMeta('移动端'),
      },
      {
        path: '/devices',
        name: MOBILE_ROUTE_NAMES.devices,
        component: pageStub,
        meta: mainMeta('设备中心'),
      },
      {
        path: '/tasks',
        name: MOBILE_ROUTE_NAMES.tasks,
        component: pageStub,
        meta: mainMeta('任务中心'),
      },
      {
        path: '/schedules',
        name: MOBILE_ROUTE_NAMES.schedules,
        component: pageStub,
        meta: mainMeta('定时计划'),
      },
      {
        path: '/shops',
        name: MOBILE_ROUTE_NAMES.shops,
        component: pageStub,
        meta: mainMeta('店铺'),
      },
      {
        path: '/me',
        name: MOBILE_ROUTE_NAMES.profile,
        component: pageStub,
        meta: mainMeta('我的'),
      },
      {
        path: '/devices/:deviceId',
        name: MOBILE_ROUTE_NAMES.deviceDetail,
        component: pageStub,
        meta: detailMeta('设备详情'),
      },
      {
        path: '/tasks/:taskId',
        name: MOBILE_ROUTE_NAMES.taskDetail,
        component: pageStub,
        meta: detailMeta('任务详情'),
      },
      {
        path: '/__foundation',
        name: MOBILE_ROUTE_NAMES.foundation,
        component: pageStub,
        meta: detailMeta('移动端基础设施'),
      },
    ],
  })
}

async function mountAppAt(path: string) {
  const router = createShellRouter()
  await router.push(path)
  await router.isReady()
  const wrapper = mount(App, {
    global: { plugins: [createPinia(), router] },
  })
  mountedWrappers.push(wrapper)
  return { router, wrapper }
}

afterEach(async () => {
  for (const wrapper of mountedWrappers.splice(0)) wrapper.unmount()
  // Vant safe-area placeholders schedule post-mount measurements.
  // Let them settle before Vitest tears down jsdom's window.
  await new Promise((resolve) => setTimeout(resolve, 350))
  document.body.innerHTML = ''
})

describe('MobileAppShell V2', () => {
  it('renders the header, default content and bottom slots', () => {
    const wrapper = mount(MobileAppShell, {
      slots: {
        header: '<div>顶部</div>',
        default: '<div>内容</div>',
        bottom: '<div>底部</div>',
      },
    })
    mountedWrappers.push(wrapper)

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

  it('orders the theme action before an empty notification badge', async () => {
    const wrapper = mount(MobileGlobalHeader)
    mountedWrappers.push(wrapper)

    expect(wrapper.text()).toContain('思余AI中控台')
    const buttons = wrapper.findAll('button')
    expect(buttons.map((button) => button.attributes('aria-label'))).toEqual([
      '切换到深色主题',
      '通知',
    ])
    expect(
      buttons.every((button) => button.classes('mobile-icon-button')),
    ).toBe(true)
    expect(wrapper.findAll('.mobile-header-icon')).toHaveLength(2)
    expect(
      wrapper
        .findAll('.mobile-header-icon')
        .every((icon) => icon.element.tagName === 'IMG'),
    ).toBe(true)
    expect(wrapper.find('.van-badge--dot').exists()).toBe(false)

    await buttons[0]!.trigger('click')
    expect(wrapper.emitted('themeToggle')).toHaveLength(1)
    await wrapper.get('button[aria-label="通知"]').trigger('click')
    expect(wrapper.emitted('notificationClick')).toHaveLength(1)

    await wrapper.setProps({ resolvedTheme: 'dark' })
    expect(
      wrapper.get('[data-testid="theme-toggle"]').attributes('aria-label'),
    ).toBe('切换到浅色主题')
    await wrapper.setProps({ notificationDot: true })
    expect(wrapper.find('.van-badge--dot').exists()).toBe(true)
  })

  it('keeps the fixed five-entry order in one non-fixed shell tabbar', async () => {
    const { wrapper } = await mountAppAt('/tasks')
    const tabbar = wrapper.getComponent(VanTabbar)
    const items = wrapper.findAllComponents(VanTabbarItem)

    expect(wrapper.getComponent(MobileGlobalHeader).text()).toContain(
      '思余AI中控台',
    )
    expect(wrapper.findComponent(MobileDetailHeader).exists()).toBe(false)
    expect(tabbar.props('fixed')).toBe(false)
    expect(tabbar.props('safeAreaInsetBottom')).toBe(false)
    expect(wrapper.get('footer').find('.van-tabbar').exists()).toBe(true)
    expect(items.map((item) => item.text())).toEqual([
      '设备',
      '任务',
      '计划',
      '店铺',
      '我的',
    ])
    expect(
      items.map((item) => (item.props('to') as { name: string | symbol }).name),
    ).toEqual([
      MOBILE_ROUTE_NAMES.devices,
      MOBILE_ROUTE_NAMES.tasks,
      MOBILE_ROUTE_NAMES.schedules,
      MOBILE_ROUTE_NAMES.shops,
      MOBILE_ROUTE_NAMES.profile,
    ])
  })

  it('uses one detail header and hides bottom navigation on device detail', async () => {
    const { router, wrapper } = await mountAppAt('/devices/device-1')

    expect(wrapper.find('footer').exists()).toBe(false)
    expect(wrapper.findComponent(MobileGlobalHeader).exists()).toBe(false)
    expect(wrapper.getComponent(MobileDetailHeader).props('title')).toBe(
      '设备详情',
    )
    const backButton = wrapper.get('button[aria-label="返回"]')
    expect(backButton.attributes('type')).toBe('button')

    await backButton.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe(MOBILE_ROUTE_NAMES.devices)
  })

  it('returns a task detail to its source device through the shared detail header', async () => {
    const { router, wrapper } = await mountAppAt(
      '/tasks/task-1?fromDeviceId=device-1',
    )

    expect(wrapper.find('footer').exists()).toBe(false)
    expect(wrapper.getComponent(MobileDetailHeader).props('title')).toBe(
      '任务详情',
    )
    wrapper.getComponent(MobileDetailHeader).vm.$emit('back')
    await flushPromises()

    expect(router.currentRoute.value).toEqual(
      expect.objectContaining({
        name: MOBILE_ROUTE_NAMES.deviceDetail,
        params: { deviceId: 'device-1' },
      }),
    )
  })

  it('returns the development foundation detail shell to home', async () => {
    const { router, wrapper } = await mountAppAt('/__foundation')

    wrapper.getComponent(MobileDetailHeader).vm.$emit('back')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe(MOBILE_ROUTE_NAMES.home)
  })

  it('omits empty chrome and activates safe-area fallback classes', () => {
    const wrapper = mount(MobileAppShell, {
      slots: { default: '<div>内容</div>' },
    })
    mountedWrappers.push(wrapper)

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
