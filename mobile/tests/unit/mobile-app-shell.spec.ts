import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import {
  NavBar as VanNavBar,
  Tabbar as VanTabbar,
  TabbarItem as VanTabbarItem,
} from 'vant'
import { afterEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import App from '@/App.vue'
import { MOBILE_ROUTE_NAMES } from '@/app/router/routes'
import { MobileAppShell } from '@/shared/ui'

const mountedWrappers: VueWrapper[] = []

afterEach(async () => {
  for (const wrapper of mountedWrappers.splice(0)) wrapper.unmount()
  // Vant safe-area placeholders schedule post-mount measurements.
  // Let them settle before Vitest tears down jsdom's window.
  await new Promise((resolve) => setTimeout(resolve, 350))
  document.body.innerHTML = ''
})

describe('MobileAppShell', () => {
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
        {
          path: '/devices',
          name: MOBILE_ROUTE_NAMES.devices,
          component: { template: '<div>设备内容</div>' },
          meta: {
            title: '设备中心',
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
    mountedWrappers.push(wrapper)
    const tabbar = wrapper.getComponent(VanTabbar)

    expect(tabbar.props('fixed')).toBe(false)
    expect(tabbar.props('safeAreaInsetBottom')).toBe(false)
    expect(wrapper.get('footer').find('.van-tabbar').exists()).toBe(true)
    expect(
      wrapper.findAllComponents(VanTabbarItem).map((item) => item.text()),
    ).toEqual(['任务', '设备'])
  })

  it('returns a device detail to the device list through the global header', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/devices',
          name: MOBILE_ROUTE_NAMES.devices,
          component: { template: '<div>设备内容</div>' },
          meta: {
            title: '设备中心',
            requiresAuth: false,
            permission: null,
          },
        },
        {
          path: '/devices/:deviceId',
          name: MOBILE_ROUTE_NAMES.deviceDetail,
          component: { template: '<div>设备详情</div>' },
          meta: {
            title: '设备详情',
            requiresAuth: false,
            permission: null,
          },
        },
      ],
    })
    await router.push('/devices/device-1')
    await router.isReady()

    const wrapper = mount(App, {
      global: { plugins: [createPinia(), router] },
    })
    mountedWrappers.push(wrapper)

    expect(wrapper.find('footer').exists()).toBe(false)
    wrapper.getComponent(VanNavBar).vm.$emit('clickLeft')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe(MOBILE_ROUTE_NAMES.devices)
  })

  it('returns an existing task detail to its source device detail', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/tasks',
          name: MOBILE_ROUTE_NAMES.tasks,
          component: { template: '<div>任务列表</div>' },
          meta: {
            title: '任务中心',
            requiresAuth: false,
            permission: null,
          },
        },
        {
          path: '/tasks/:taskId',
          name: MOBILE_ROUTE_NAMES.taskDetail,
          component: { template: '<div>任务详情</div>' },
          meta: {
            title: '任务详情',
            requiresAuth: false,
            permission: null,
          },
        },
        {
          path: '/devices/:deviceId',
          name: MOBILE_ROUTE_NAMES.deviceDetail,
          component: { template: '<div>设备详情</div>' },
          meta: {
            title: '设备详情',
            requiresAuth: false,
            permission: null,
          },
        },
      ],
    })
    await router.push({
      name: MOBILE_ROUTE_NAMES.taskDetail,
      params: { taskId: 'task-1' },
      query: { fromDeviceId: 'device-1' },
    })
    await router.isReady()

    const wrapper = mount(App, {
      global: { plugins: [createPinia(), router] },
    })
    mountedWrappers.push(wrapper)

    wrapper.getComponent(VanNavBar).vm.$emit('clickLeft')
    await flushPromises()

    expect(router.currentRoute.value).toEqual(
      expect.objectContaining({
        name: MOBILE_ROUTE_NAMES.deviceDetail,
        params: { deviceId: 'device-1' },
      }),
    )
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
