import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { MOBILE_ROUTE_NAMES } from '@/app/router/routes'
import { mapDeviceRead } from '@/entities/device'
import { TaskListCard, type ActiveTaskSummaryReadDto } from '@/entities/task'

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

const activeTask = {
  task_id: 'task-running',
  target_device_id: 'device-1',
  skill_id: 'sync-orders',
  execution_display_name: '同步订单',
  status: 'running',
  started_at: '2026-08-27T07:30:00.000Z',
  created_at: '2026-08-27T07:29:00.000Z',
  latest_event: null,
} satisfies ActiveTaskSummaryReadDto

function createDeviceDetailMock(options: {
  activeTask: ActiveTaskSummaryReadDto | null | undefined
  activeTaskLoading?: boolean
  activeTaskError?: boolean
  providerLoading?: boolean
  capabilityError?: boolean
}) {
  return {
    device: ref(device),
    deviceQuery: { refetch: vi.fn() },
    isDeviceInitialLoading: ref(false),
    isDeviceInitialError: ref(false),
    isDeviceBackgroundError: ref(false),
    activeTask: {
      query: { data: ref(options.activeTask), refetch: vi.fn() },
      isInitialLoading: ref(options.activeTaskLoading ?? false),
      isInitialError: ref(options.activeTaskError ?? false),
      isBackgroundError: ref(false),
    },
    provider: {
      query: {
        data: ref(options.providerLoading ? undefined : []),
        refetch: vi.fn(),
      },
      isInitialLoading: ref(options.providerLoading ?? false),
      isInitialError: ref(false),
      isBackgroundError: ref(false),
    },
    capability: {
      query: {
        data: ref(options.capabilityError ? undefined : []),
        refetch: vi.fn(),
      },
      isInitialLoading: ref(false),
      isInitialError: ref(options.capabilityError ?? false),
      isBackgroundError: ref(false),
    },
  }
}

function createRouterFor(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/devices', component: { template: '<div />' } },
      { path: '/devices/:deviceId', component: { template: '<div />' } },
      {
        path: '/tasks/:taskId',
        name: MOBILE_ROUTE_NAMES.taskDetail,
        component: { template: '<div />' },
      },
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
      filteredDevices: ref([]),
      activeTaskStates: ref({}),
      overview: ref({
        dataState: 'loading',
        totalCount: null,
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
      filter: ref('all'),
      searchQuery: ref(''),
      searchAvailable: ref(false),
      filterLabel: ref('全部'),
      filterAvailability: ref({
        all: true,
        online: false,
        running: false,
        offline: false,
      }),
      total: ref(undefined),
      visibleTotal: ref(undefined),
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
      setFilter: vi.fn(),
      toggleMetricFilter: vi.fn(),
      loadMore: vi.fn(),
      retryLoadMore: vi.fn(),
    }
    const router = await createRouterFor('/devices')
    const wrapper = mount(DeviceCenterPage, {
      global: { plugins: [router] },
    })
    await flushPromises()

    expect(wrapper.find('[aria-label="设备总览"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="mobile-list-toolbar"]').exists()).toBe(
      false,
    )
    expect(
      wrapper.get('[data-testid="device-search"]').attributes(),
    ).toHaveProperty('disabled')
    expect(wrapper.find('[data-testid="device-loading"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="device-list-scroll"]').exists()).toBe(
      true,
    )
    wrapper.unmount()
  })

  it('renders a successful Device List while Active Task is still loading', async () => {
    featureMocks.center = {
      devices: ref([device]),
      filteredDevices: ref([device]),
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
        totalCount: 1,
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
      filter: ref('all'),
      searchQuery: ref(''),
      searchAvailable: ref(true),
      filterLabel: ref('全部'),
      filterAvailability: ref({
        all: true,
        online: true,
        running: false,
        offline: true,
      }),
      total: ref(1),
      visibleTotal: ref(1),
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
      setFilter: vi.fn(),
      toggleMetricFilter: vi.fn(),
      loadMore: vi.fn(),
      retryLoadMore: vi.fn(),
    }
    const router = await createRouterFor('/devices')
    const wrapper = mount(DeviceCenterPage, {
      global: { plugins: [router] },
    })
    await flushPromises()

    expect(wrapper.get('[data-testid="device-list"]').text()).toContain('运营')
    expect(wrapper.get('[data-testid="device-card-runtime"]').text()).toBe(
      '在线',
    )
    expect(wrapper.find('[data-testid="device-loading"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('技术错误不得展示')
    wrapper.unmount()
  })

  it('keeps the Device Detail visible while Provider loads and Capability fails', async () => {
    featureMocks.detail = createDeviceDetailMock({
      activeTask: undefined,
      activeTaskLoading: true,
      providerLoading: true,
      capabilityError: true,
    })
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
    expect(
      wrapper.get('[data-testid="device-summary-device"]').text(),
    ).toContain('Worker 0.4.6')
    expect(
      wrapper.find('[data-testid="device-capability-panel"]').exists(),
    ).toBe(true)
    expect(wrapper.get('[data-testid="device-current-task"]').text()).toContain(
      '当前任务',
    )
    const summary = wrapper.get('[data-testid="device-detail"]').element
    const capability = wrapper.get(
      '[data-testid="device-capability-panel"]',
    ).element
    const currentTask = wrapper.get(
      '[data-testid="device-current-task"]',
    ).element
    expect(
      summary.compareDocumentPosition(capability) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
    expect(
      capability.compareDocumentPosition(currentTask) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
    expect(wrapper.text()).toContain('加载中')
    await wrapper.get('.van-tab:nth-child(2)').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('加载失败')
    expect(wrapper.text()).not.toMatch(/Provider 技术错误|Capability 技术错误/)
    wrapper.unmount()
  })

  it('renders the frozen Task Card for Device Current Task and keeps route context', async () => {
    featureMocks.detail = createDeviceDetailMock({ activeTask })
    const router = await createRouterFor('/devices/device-1')
    const wrapper = mount(DeviceDetailPage, {
      global: { plugins: [router] },
    })
    await flushPromises()

    const currentTask = wrapper.get('[data-testid="device-current-task"]')
    expect(currentTask.findComponent(TaskListCard).exists()).toBe(true)
    expect(currentTask.find('[data-testid="task-card-chevron"]').exists()).toBe(
      true,
    )
    expect(currentTask.find('.van-progress').exists()).toBe(false)
    expect(currentTask.find('.active-task-summary').exists()).toBe(false)

    await currentTask
      .get('[data-testid="device-current-task-link"]')
      .trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe(MOBILE_ROUTE_NAMES.taskDetail)
    expect(router.currentRoute.value.params.taskId).toBe('task-running')
    expect(router.currentRoute.value.query.fromDeviceId).toBe('device-1')
    wrapper.unmount()
  })

  it('shows idle without rendering a fake Task Card', async () => {
    featureMocks.detail = createDeviceDetailMock({ activeTask: null })
    const router = await createRouterFor('/devices/device-1')
    const wrapper = mount(DeviceDetailPage, {
      global: { plugins: [router] },
    })
    await flushPromises()

    const currentTask = wrapper.get('[data-testid="device-current-task"]')
    expect(currentTask.text()).toContain('当前任务')
    expect(currentTask.text()).toContain('空闲')
    expect(currentTask.findComponent(TaskListCard).exists()).toBe(false)
    expect(
      currentTask.find('[data-testid="device-current-task-link"]').exists(),
    ).toBe(false)
    wrapper.unmount()
  })
})
