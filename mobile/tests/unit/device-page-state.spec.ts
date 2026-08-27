import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { mapDeviceRead } from '@/entities/device'

const featureMocks = vi.hoisted(() => ({
  center: null as unknown,
  detail: null as unknown,
}))

vi.mock('@/features/device-center', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('@/features/device-center')>()
  return {
    ...actual,
    useDeviceCenter: () => featureMocks.center,
    useDeviceDetail: () => featureMocks.detail,
  }
})

import DeviceCenterPage from '@/pages/devices/DeviceCenterPage.vue'
import DeviceDetailPage from '@/pages/devices/DeviceDetailPage.vue'

const device = mapDeviceRead({
  device_id: 'device-1',
  display_name: '运营',
  enabled: true,
  location: null,
  note: null,
  deleted_at: null,
  worker_runtime: {
    device_id: 'device-1',
    worker_version: '0.4.6',
    connection_status: 'online',
    last_seen_at: '2026-08-27T08:00:00.000Z',
    started_at: '2026-08-27T07:00:00.000Z',
    updated_at: '2026-08-27T08:00:00.000Z',
  },
  created_at: '2026-08-01T00:00:00.000Z',
  updated_at: '2026-08-27T08:00:00.000Z',
})

function createRouterFor(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/devices', component: { template: '<div />' } },
      { path: '/devices/:deviceId', component: { template: '<div />' } },
    ],
  })
  return router.push(path).then(() => router)
}

afterEach(() => {
  vi.clearAllMocks()
})

describe('Device page loading boundaries', () => {
  it('keeps the Summary and Toolbar mounted while the Device List loads', async () => {
    featureMocks.center = {
      devices: ref([]),
      activeTaskStates: ref({}),
      overview: ref({
        dataState: 'loading',
        loadedCount: 0,
        onlineCount: null,
        offlineCount: null,
        unreportedCount: 0,
        runningCount: null,
        activeConfirmedCount: 0,
        activeUnknownCount: 0,
        activeBackgroundErrorCount: 0,
        activeInitialErrorCount: 0,
        activeState: 'loading',
      }),
      total: ref(undefined),
      isInitialLoading: ref(true),
      isInitialError: ref(false),
      isBackgroundError: ref(false),
      isNextPageError: ref(false),
      refreshing: ref(false),
      query: {
        isFetchingNextPage: ref(false),
        hasNextPage: ref(false),
        refetch: vi.fn(),
      },
      refresh: vi.fn(),
      loadMore: vi.fn(),
      retryLoadMore: vi.fn(),
    }
    const router = await createRouterFor('/devices')
    const wrapper = mount(DeviceCenterPage, {
      global: { plugins: [router] },
    })
    await flushPromises()

    expect(wrapper.find('[aria-label="设备总览"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="mobile-list-toolbar"]').text()).toBe(
      '设备—',
    )
    expect(wrapper.find('[data-testid="device-loading"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="device-list-scroll"]').exists()).toBe(
      true,
    )
    wrapper.unmount()
  })

  it('renders a successful Device List while Active Task is still loading', async () => {
    featureMocks.center = {
      devices: ref([device]),
      activeTaskStates: ref({
        'device-1': {
          task: undefined,
          hasSuccessfulData: false,
          initialLoading: true,
          initialError: false,
          backgroundError: false,
          retry: vi.fn(),
        },
      }),
      overview: ref({
        dataState: 'ready',
        loadedCount: 1,
        onlineCount: 1,
        offlineCount: 0,
        unreportedCount: 0,
        runningCount: null,
        activeConfirmedCount: 0,
        activeUnknownCount: 1,
        activeBackgroundErrorCount: 0,
        activeInitialErrorCount: 0,
        activeState: 'loading',
      }),
      total: ref(1),
      isInitialLoading: ref(false),
      isInitialError: ref(false),
      isBackgroundError: ref(false),
      isNextPageError: ref(false),
      refreshing: ref(false),
      query: {
        isFetchingNextPage: ref(false),
        hasNextPage: ref(false),
        refetch: vi.fn(),
      },
      refresh: vi.fn(),
      loadMore: vi.fn(),
      retryLoadMore: vi.fn(),
    }
    const router = await createRouterFor('/devices')
    const wrapper = mount(DeviceCenterPage, {
      global: { plugins: [router] },
    })
    await flushPromises()

    expect(wrapper.get('[data-testid="device-list"]').text()).toContain('运营')
    expect(wrapper.text()).toContain('加载中')
    expect(wrapper.find('[data-testid="device-loading"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('技术错误不得展示')
    wrapper.unmount()
  })

  it('keeps the Device Detail visible while Provider loads and Capability fails', async () => {
    featureMocks.detail = {
      device: ref(device),
      deviceQuery: { refetch: vi.fn() },
      isDeviceInitialLoading: ref(false),
      isDeviceInitialError: ref(false),
      isDeviceBackgroundError: ref(false),
      activeTask: {
        query: { data: ref(undefined), refetch: vi.fn() },
        isInitialLoading: ref(true),
        isInitialError: ref(false),
        isBackgroundError: ref(false),
      },
      provider: {
        query: { data: ref(undefined), refetch: vi.fn() },
        isInitialLoading: ref(true),
        isInitialError: ref(false),
        isBackgroundError: ref(false),
      },
      capability: {
        query: { data: ref(undefined), refetch: vi.fn() },
        isInitialLoading: ref(false),
        isInitialError: ref(true),
        isBackgroundError: ref(false),
      },
    }
    const router = await createRouterFor('/devices/device-1')
    const wrapper = mount(DeviceDetailPage, {
      global: { plugins: [router] },
    })
    await flushPromises()

    expect(wrapper.get('[data-testid="device-detail"]').text()).toContain(
      '运营',
    )
    expect(wrapper.find('[data-testid="device-detail-loading"]').exists()).toBe(
      false,
    )
    expect(wrapper.find('[data-testid="device-detail-error"]').exists()).toBe(
      false,
    )
    expect(wrapper.text()).toContain('加载中')
    expect(wrapper.text()).toContain('加载失败')
    expect(wrapper.text()).not.toMatch(/Provider 技术错误|Capability 技术错误/)
    wrapper.unmount()
  })
})
