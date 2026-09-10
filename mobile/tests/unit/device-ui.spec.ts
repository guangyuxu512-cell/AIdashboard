import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import {
  DeviceConnectionTag,
  DEVICE_ARTWORK_STATES,
  DeviceEnabledTag,
  DeviceStatusArtwork,
  type Device,
  type DeviceProviderInventoryReadDto,
  type DeviceSkillCapabilityReadDto,
  type YingdaoProviderStatusDto,
} from '@/entities/device'
import type { ActiveTaskSummaryReadDto } from '@/entities/task'
import {
  DeviceCapabilityPanel,
  DeviceDetailHero,
  DeviceInfiniteList,
  DeviceListCard,
  DeviceMoreSheet,
  DeviceProviderDetails,
  DeviceRuntimeSummary,
  DeviceSkillDetails,
  getDeviceRuntimeDisplayLabel,
  getDeviceVisualState,
  mapDeviceActiveTaskToTaskListItem,
  type DeviceActiveTaskState,
} from '@/features/device-center'

const wrappers: VueWrapper[] = []

const baseDevice: Device = {
  deviceId: 'device-1',
  displayName: '仓库设备',
  enabled: true,
  location: null,
  note: null,
  deletedAt: null,
  workerRuntime: {
    deviceId: 'device-1',
    workerVersion: '1.2.3',
    connectionStatus: 'online',
    lastSeenAt: '2026-08-26T08:59:00.000Z',
    startedAt: '2026-08-26T08:00:00.000Z',
    updatedAt: '2026-08-26T08:59:00.000Z',
  },
  createdAt: '2026-08-01T00:00:00.000Z',
  updatedAt: '2026-08-26T08:59:00.000Z',
}

const runningTask: ActiveTaskSummaryReadDto = {
  task_id: 'task-running',
  target_device_id: 'device-1',
  skill_id: 'sync-orders',
  execution_display_name: '同步订单',
  status: 'running',
  started_at: '2026-08-26T08:00:00.000Z',
  created_at: '2026-08-26T07:59:00.000Z',
  latest_event: {
    event_id: 'event-1',
    task_id: 'task-running',
    seq: 1,
    event_type: 'status',
    level: 'info',
    message: '正在执行',
    event_at: '2026-08-26T08:01:00.000Z',
    metadata: {},
    created_at: '2026-08-26T08:01:00.000Z',
  },
}

const listProps = {
  devices: [] as Device[],
  activeTaskStates: {} as Record<string, DeviceActiveTaskState>,
  initialLoading: false,
  initialError: false,
  nextPageError: false,
  refreshing: false,
  loadingMore: false,
  hasMore: false,
}

const idleActiveTaskState: DeviceActiveTaskState = {
  task: null,
  hasSuccessfulData: true,
  initialLoading: false,
  initialError: false,
  backgroundError: false,
  retry: () => undefined,
}

function providerInventory(
  status: YingdaoProviderStatusDto,
): DeviceProviderInventoryReadDto {
  const ready = status === 'ready'
  return {
    device_id: 'device-1',
    provider_code: 'yingdao',
    available: true,
    provider_version: ready ? '6.3.6' : '3.4.5',
    account_display: '测试账号',
    account_type: 'enterprise',
    enterprise_account: true,
    last_discovered_at: '2026-08-26T08:00:00.000Z',
    inventory: {
      provider: 'yingdao',
      available: ready,
      status,
      status_reason_code: 'REASON',
      status_reason: '状态说明',
      provider_version: ready ? '6.3.6' : '3.4.5',
      execution_available: ready,
      execution_version: ready ? '6.3.6' : null,
      execution_unavailable_reason: null,
      logged_in: ready,
      account_display: '测试账号',
      account_type: 'enterprise',
      enterprise_account: true,
      user_id: 'provider-user-1',
      applications: [
        {
          app_id: 'app-1',
          app_name: '订单应用',
          version_id: 'version-1',
          updated_at: 'external-value',
          app_type: 'rpa',
          group_id: null,
        },
      ],
      discovered_at: '2026-08-26T08:00:00.000Z',
    },
    updated_at: '2026-08-26T08:00:00.000Z',
  }
}

function capability(
  skillId: string,
  classification: 'business' | 'internal' | null,
): DeviceSkillCapabilityReadDto {
  return {
    device_id: 'device-1',
    skill_id: skillId,
    display_name: skillId,
    runtime: classification === 'business' ? 'python' : 'rpa',
    provider: classification === 'business' ? null : 'yingdao',
    version: '1.0.0',
    classification,
    input_schema: null,
    updated_at: '2026-08-26T08:00:00.000Z',
  }
}

function track<T extends VueWrapper>(wrapper: T): T {
  wrappers.push(wrapper)
  return wrapper
}

function mountDeviceCard(
  device: Device,
  activeTaskState: DeviceActiveTaskState = idleActiveTaskState,
): VueWrapper {
  return track(
    mount(DeviceListCard, {
      props: { device, activeTaskState },
    }),
  )
}

describe('device center UI', () => {
  afterEach(async () => {
    for (const wrapper of wrappers.splice(0)) wrapper.unmount()
    await flushPromises()
  })

  it('renders enabled and connection facts as independent tags', () => {
    const enabled = track(mount(DeviceEnabledTag, { props: { enabled: true } }))
    const disabled = track(
      mount(DeviceEnabledTag, { props: { enabled: false } }),
    )
    const online = track(
      mount(DeviceConnectionTag, { props: { status: 'online' } }),
    )
    const offline = track(
      mount(DeviceConnectionTag, { props: { status: 'offline' } }),
    )
    const missingConnection = track(
      mount(DeviceConnectionTag, { props: { status: null } }),
    )

    expect(enabled.text()).toBe('已启用')
    expect(disabled.text()).toBe('已停用')
    expect(online.text()).toBe('在线')
    expect(offline.text()).toBe('离线')
    expect(missingConnection.text()).toBe('未连接')
  })

  it.each([
    {
      name: 'online idle',
      connectionStatus: 'online',
      enabled: true,
      activeTaskState: idleActiveTaskState,
      visualLabel: '在线',
      visualState: 'online',
      enabledLabel: '已启用',
    },
    {
      name: 'online running',
      connectionStatus: 'online',
      enabled: true,
      activeTaskState: { ...idleActiveTaskState, task: runningTask },
      visualLabel: '运行中',
      visualState: 'running',
      enabledLabel: '已启用',
    },
    {
      name: 'offline idle',
      connectionStatus: 'offline',
      enabled: true,
      activeTaskState: idleActiveTaskState,
      visualLabel: '离线',
      visualState: 'offline',
      enabledLabel: '已启用',
    },
    {
      name: 'disabled online',
      connectionStatus: 'online',
      enabled: false,
      activeTaskState: { ...idleActiveTaskState, task: runningTask },
      visualLabel: '运行中',
      visualState: 'running',
      enabledLabel: '已停用',
    },
  ] as const)(
    'renders the $name Device Card facts without merging their semantics',
    async ({
      connectionStatus,
      enabled,
      activeTaskState,
      visualLabel,
      visualState,
      enabledLabel,
    }) => {
      const wrapper = mountDeviceCard(
        {
          ...baseDevice,
          enabled,
          workerRuntime: {
            ...baseDevice.workerRuntime!,
            connectionStatus,
          },
        },
        activeTaskState,
      )
      await flushPromises()

      expect(wrapper.get('[data-testid="device-card-runtime"]').text()).toBe(
        visualLabel,
      )
      expect(wrapper.classes()).toEqual(
        expect.arrayContaining([
          'mobile-press-surface',
          `device-list-card--${visualState}`,
        ]),
      )
      expect(wrapper.get('.device-list-card__meta').text()).toContain(
        enabledLabel,
      )
      expect(wrapper.text()).not.toContain('Worker')
      expect(
        wrapper
          .get('[data-device-artwork-kind="desktop"]')
          .attributes('data-device-artwork-state'),
      ).toBe(visualState)
      expect(wrapper.find('[data-testid="device-card-leading"]').exists()).toBe(
        true,
      )
      expect(wrapper.find('[data-testid="device-card-chevron"]').exists()).toBe(
        true,
      )
    },
  )

  it('shows an explicit unreported connection label when Runtime is missing', async () => {
    const wrapper = mountDeviceCard({ ...baseDevice, workerRuntime: null })
    await flushPromises()

    expect(wrapper.get('[data-testid="device-card-runtime"]').text()).toBe(
      '未连接',
    )
    expect(wrapper.get('[data-testid="device-card-meta"]').text()).toContain(
      '心跳未上报·已启用',
    )
    expect(wrapper.find('.device-list-card__heartbeat').exists()).toBe(true)
  })

  it('keeps a long Device name in the fixed name slot', () => {
    const displayName = '客服自动化工作站（华东售后协同中心）'
    const wrapper = mountDeviceCard({ ...baseDevice, displayName })

    expect(wrapper.get('[data-testid="device-card-name"]').text()).toBe(
      displayName,
    )
    expect(wrapper.findAll('[data-testid^="device-card-"]')).not.toHaveLength(0)
  })

  it('makes the whole Device Card one Device Detail entry without a Task entry', async () => {
    const wrapper = track(
      mount(DeviceListCard, {
        props: {
          device: baseDevice,
          activeTaskState: {
            ...idleActiveTaskState,
            task: runningTask,
          },
        },
      }),
    )

    expect(wrapper.element.tagName).toBe('ARTICLE')
    expect(wrapper.findAll('button')).toHaveLength(1)
    expect(wrapper.get('button').attributes('aria-label')).toBe(
      '查看设备：仓库设备',
    )
    expect(wrapper.find('[aria-label^="查看任务："]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('同步订单')
    expect(wrapper.get('[data-testid="device-card-runtime"]').text()).toBe(
      '运行中',
    )
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('selectDevice')).toEqual([['device-1']])
    expect(wrapper.emitted('selectTask')).toBeUndefined()
  })

  it('renders every formal artwork kind and state without inferring kind from names', () => {
    expect(DEVICE_ARTWORK_STATES).toEqual(['online', 'running', 'offline'])
    for (const kind of ['desktop', 'laptop', 'server'] as const) {
      for (const state of DEVICE_ARTWORK_STATES) {
        const wrapper = track(
          mount(DeviceStatusArtwork, { props: { kind, state } }),
        )
        expect(wrapper.attributes('data-device-artwork-kind')).toBe(kind)
        expect(wrapper.attributes('data-device-artwork-state')).toBe(state)
      }
    }
  })

  it('adds a Hero presentation without changing the default List variant', () => {
    const list = track(
      mount(DeviceStatusArtwork, {
        props: { kind: 'desktop', state: 'online' },
      }),
    )
    const hero = track(
      mount(DeviceStatusArtwork, {
        props: { kind: 'desktop', state: 'running', variant: 'hero' },
      }),
    )

    expect(list.attributes('data-device-artwork-variant')).toBe('list')
    expect(list.classes()).toContain('device-status-artwork--list')
    expect(hero.attributes('data-device-artwork-variant')).toBe('hero')
    expect(hero.classes()).toContain('device-status-artwork--hero')
  })

  it('renders Device Hero from formal Device, Active Task, heartbeat and Provider facts', () => {
    const wrapper = track(
      mount(DeviceDetailHero, {
        props: {
          device: baseDevice,
          activeTaskState: { ...idleActiveTaskState, task: runningTask },
          inventories: [providerInventory('ready')],
        },
      }),
    )

    expect(wrapper.get('[data-testid="device-hero-name"]').text()).toBe(
      '仓库设备',
    )
    expect(wrapper.get('[data-testid="device-hero-status"]').text()).toBe(
      '运行中',
    )
    expect(wrapper.get('[data-testid="device-hero-heartbeat"]').text()).toMatch(
      /^最后心跳：/,
    )
    expect(wrapper.get('[data-testid="device-hero-meta"]').text()).toContain(
      'Worker 1.2.3',
    )
    expect(wrapper.get('[data-testid="device-hero-meta"]').text()).toContain(
      '影刀 6.3.6',
    )
    expect(
      wrapper
        .get('[data-testid="device-status-artwork"]')
        .attributes('data-device-artwork-state'),
    ).toBe('running')
    expect(
      wrapper
        .get('[data-testid="device-status-artwork"]')
        .attributes('data-device-artwork-variant'),
    ).toBe('hero')
    expect(wrapper.text()).not.toMatch(/GY00099|5\.36\.1/)
  })

  it('keeps Device Hero offline when the formal connection state is offline', () => {
    const wrapper = track(
      mount(DeviceDetailHero, {
        props: {
          device: {
            ...baseDevice,
            workerRuntime: {
              ...baseDevice.workerRuntime!,
              connectionStatus: 'offline',
            },
          },
          activeTaskState: { ...idleActiveTaskState, task: runningTask },
          inventories: [],
        },
      }),
    )

    expect(wrapper.get('[data-testid="device-hero-status"]').text()).toBe(
      '离线',
    )
    expect(
      wrapper
        .get('[data-testid="device-status-artwork"]')
        .attributes('data-device-artwork-state'),
    ).toBe('offline')
  })

  it('derives artwork state from formal connection and Active Task facts', () => {
    expect(getDeviceVisualState(baseDevice, idleActiveTaskState)).toBe('online')
    expect(
      getDeviceVisualState(baseDevice, {
        ...idleActiveTaskState,
        task: runningTask,
      }),
    ).toBe('running')
    expect(
      getDeviceVisualState(
        {
          ...baseDevice,
          workerRuntime: {
            ...baseDevice.workerRuntime!,
            connectionStatus: 'offline',
          },
        },
        { ...idleActiveTaskState, task: runningTask },
      ),
    ).toBe('offline')
    expect(
      getDeviceVisualState(
        { ...baseDevice, workerRuntime: null },
        idleActiveTaskState,
      ),
    ).toBe('offline')
    expect(
      getDeviceRuntimeDisplayLabel(
        { ...baseDevice, workerRuntime: null },
        idleActiveTaskState,
      ),
    ).toBe('未连接')
  })

  it('keeps heartbeat and enabled facts independent from the three-state visual model', async () => {
    const freshEnabled = mountDeviceCard(baseDevice)
    const missingDisabled = mountDeviceCard({
      ...baseDevice,
      enabled: false,
      workerRuntime: {
        ...baseDevice.workerRuntime!,
        lastSeenAt: 'not-a-date',
      },
    })
    await flushPromises()

    expect(
      freshEnabled
        .get('[data-testid="device-status-artwork"]')
        .attributes('data-device-artwork-state'),
    ).toBe('online')
    expect(
      missingDisabled
        .get('[data-testid="device-status-artwork"]')
        .attributes('data-device-artwork-state'),
    ).toBe('online')
    expect(
      freshEnabled.get('[data-testid="device-card-meta"]').text(),
    ).toContain('已启用')
    expect(
      missingDisabled.get('[data-testid="device-card-meta"]').text(),
    ).toContain('心跳未上报·已停用')
  })

  it('adapts the formal Active Task summary to the frozen Task Card model', () => {
    expect(
      mapDeviceActiveTaskToTaskListItem(runningTask, baseDevice.displayName),
    ).toEqual({
      taskId: 'task-running',
      targetDeviceId: 'device-1',
      deviceDisplayName: '仓库设备',
      skillId: 'sync-orders',
      skillDisplayName: null,
      executionName: '同步订单',
      status: 'running',
      progress: null,
      currentMessage: null,
      startedAt: '2026-08-26T08:00:00.000Z',
      finishedAt: null,
      createdAt: '2026-08-26T07:59:00.000Z',
    })
  })

  it('covers Device list loading, empty, initial retry and cached background errors', async () => {
    const loading = track(
      mount(DeviceInfiniteList, {
        props: { ...listProps, initialLoading: true },
      }),
    )
    const empty = track(mount(DeviceInfiniteList, { props: listProps }))
    const initialError = track(
      mount(DeviceInfiniteList, {
        props: { ...listProps, initialError: true },
      }),
    )
    const filterPreparing = track(
      mount(DeviceInfiniteList, {
        props: { ...listProps, filterPreparing: true },
      }),
    )
    const filterError = track(
      mount(DeviceInfiniteList, {
        props: { ...listProps, filterError: true },
      }),
    )
    const background = track(
      mount(DeviceInfiniteList, {
        props: {
          ...listProps,
          devices: [baseDevice],
        },
        global: {
          stubs: {
            DeviceListCard: {
              props: ['device'],
              template:
                '<article data-testid="cached-device-card">{{ device.displayName }}</article>',
            },
          },
        },
      }),
    )

    expect(loading.find('[data-testid="device-loading"]').exists()).toBe(true)
    expect(empty.find('[data-testid="device-empty"]').exists()).toBe(true)
    expect(initialError.find('[data-testid="device-error"]').exists()).toBe(
      true,
    )
    expect(initialError.text()).toContain('加载失败')
    expect(initialError.text()).not.toContain('技术错误')
    expect(filterPreparing.text()).toContain('正在筛选')
    expect(filterError.text()).toContain('筛选失败')
    await initialError
      .get('[data-testid="device-error"] button')
      .trigger('click')
    expect(initialError.emitted('retry')).toHaveLength(1)
    await filterError
      .get('[data-testid="device-filter-error"] button')
      .trigger('click')
    expect(filterError.emitted('retryFilter')).toHaveLength(1)
    expect(
      background.find('[data-testid="device-background-error"]').exists(),
    ).toBe(false)
    expect(background.get('[data-testid="cached-device-card"]').text()).toBe(
      '仓库设备',
    )
    expect(background.find('[data-testid="device-empty"]').exists()).toBe(false)
  })

  it('renders the next-page error at the list tail with an explicit retry', async () => {
    const wrapper = track(
      mount(DeviceInfiniteList, {
        props: {
          ...listProps,
          devices: [baseDevice],
          hasMore: true,
          nextPageError: true,
        },
        global: { stubs: { DeviceListCard: true } },
      }),
    )

    expect(
      wrapper.find('[data-testid="device-background-error"]').exists(),
    ).toBe(false)
    await wrapper
      .get('[data-testid="device-list-next-page-error"] button')
      .trigger('click')
    expect(wrapper.emitted('retryLoadMore')).toHaveLength(1)
  })

  it('renders one stacked Device Runtime and Yingdao Account summary card', () => {
    const wrapper = track(
      mount(DeviceRuntimeSummary, {
        props: {
          device: baseDevice,
          activeTask: null,
          activeTaskLoading: false,
          activeTaskError: false,
          inventories: [providerInventory('ready')],
          providerLoading: false,
          providerError: false,
        },
      }),
    )

    expect(wrapper.classes()).toContain('mobile-card')
    expect(wrapper.findAll('.device-runtime-summary__section')).toHaveLength(2)
    expect(
      wrapper.find('[data-testid="device-runtime-summary-separator"]').exists(),
    ).toBe(true)
    expect(wrapper.find('[data-testid="device-runtime-icon"]').exists()).toBe(
      true,
    )
    expect(wrapper.find('[data-testid="device-account-icon"]').exists()).toBe(
      true,
    )
    expect(
      wrapper.get('[data-testid="device-summary-device"]').text(),
    ).toContain('仓库设备在线空闲Worker 1.2.3')
    expect(
      wrapper.get('[data-testid="device-summary-yingdao"]').text(),
    ).toContain('影刀账号已登录测试账号 · 6.3.6')
    expect(wrapper.get('[data-testid="device-account-version"]').text()).toBe(
      '6.3.6',
    )
    expect(wrapper.text()).not.toContain('Provider 6.3.6')
    expect(wrapper.text()).not.toContain('provider-user-1')
  })

  it.each([
    { enabled: true, activeTask: null, label: '空闲' },
    { enabled: true, activeTask: runningTask, label: '执行中' },
    { enabled: false, activeTask: runningTask, label: '停用' },
  ] as const)(
    'maps formal facts to $label',
    ({ enabled, activeTask, label }) => {
      const wrapper = track(
        mount(DeviceRuntimeSummary, {
          props: {
            device: { ...baseDevice, enabled },
            activeTask,
            activeTaskLoading: false,
            activeTaskError: false,
            inventories: [providerInventory('ready')],
            providerLoading: false,
            providerError: false,
          },
        }),
      )

      expect(
        wrapper.get('[data-testid="device-runtime-states"]').text(),
      ).toContain(label)
    },
  )

  it('keeps long Device and Account names inside their stable content slots', () => {
    const inventory = providerInventory('ready')
    const accountName = 'HuanYu001华东售后自动化协同中心企业账号'
    inventory.account_display = accountName
    inventory.inventory.account_display = accountName
    const wrapper = track(
      mount(DeviceRuntimeSummary, {
        props: {
          device: {
            ...baseDevice,
            displayName: '客服自动化工作站（华东售后协同中心）',
          },
          activeTask: null,
          activeTaskLoading: false,
          activeTaskError: false,
          inventories: [inventory],
          providerLoading: false,
          providerError: false,
        },
      }),
    )

    expect(wrapper.get('[data-testid="device-runtime-name"]').text()).toContain(
      '客服自动化工作站',
    )
    expect(wrapper.get('[data-testid="device-account-name"]').text()).toBe(
      accountName,
    )
    expect(wrapper.get('[data-testid="device-account-version"]').text()).toBe(
      '6.3.6',
    )
  })

  it('renders Provider secondary facts only in the technical details component', () => {
    const wrapper = track(
      mount(DeviceProviderDetails, {
        props: { inventories: [providerInventory('ready')] },
      }),
    )

    expect(wrapper.text()).toContain('提供方代码yingdao')
    expect(wrapper.text()).toContain('提供方可用是')
    expect(wrapper.text()).toContain('执行接口可用是')
    expect(wrapper.text()).toContain('已登录是')
    expect(wrapper.text()).toContain('账号类型enterprise')
    expect(wrapper.text()).toContain('企业账号是')
    expect(wrapper.text()).toContain('执行接口版本6.3.6')
    expect(wrapper.text()).toContain('状态说明状态说明')
  })

  it('keeps Provider loading, error and empty states inside the Yingdao column', async () => {
    const loading = track(
      mount(DeviceRuntimeSummary, {
        props: {
          device: baseDevice,
          activeTask: null,
          activeTaskLoading: false,
          activeTaskError: false,
          inventories: undefined,
          providerLoading: true,
          providerError: false,
        },
      }),
    )
    const error = track(
      mount(DeviceRuntimeSummary, {
        props: {
          device: baseDevice,
          activeTask: null,
          activeTaskLoading: false,
          activeTaskError: false,
          inventories: undefined,
          providerLoading: false,
          providerError: true,
        },
      }),
    )
    const empty = track(
      mount(DeviceRuntimeSummary, {
        props: {
          device: baseDevice,
          activeTask: null,
          activeTaskLoading: false,
          activeTaskError: false,
          inventories: [],
          providerLoading: false,
          providerError: false,
        },
      }),
    )

    expect(loading.text()).toContain('加载中')
    expect(loading.text()).not.toContain('未上报')
    await error.get('button').trigger('click')
    expect(error.emitted('retryProvider')).toHaveLength(1)
    expect(error.text()).toContain('加载失败')
    expect(empty.text()).toContain('未上报')
  })

  it('renders Application names and row actions without exposing Application IDs', async () => {
    const inventory = providerInventory('ready')
    inventory.inventory.applications = [
      ...inventory.inventory.applications,
      {
        app_id: 'app-private-uuid',
        app_name: '拼多多自动处理售后工单',
        version_id: null,
        updated_at: null,
        app_type: 'rpa',
        group_id: null,
      },
      {
        app_id: 'app-3',
        app_name: '商品发布',
        version_id: null,
        updated_at: null,
        app_type: 'rpa',
        group_id: null,
      },
      {
        app_id: 'app-4',
        app_name: '订单同步',
        version_id: null,
        updated_at: null,
        app_type: 'rpa',
        group_id: null,
      },
      {
        app_id: 'app-5',
        app_name: '库存同步',
        version_id: null,
        updated_at: null,
        app_type: 'rpa',
        group_id: null,
      },
      {
        app_id: 'app-6',
        app_name: '物流跟踪',
        version_id: null,
        updated_at: null,
        app_type: 'rpa',
        group_id: null,
      },
    ]
    const wrapper = track(
      mount(DeviceCapabilityPanel, {
        props: {
          inventories: [inventory],
          capabilities: [],
          providerLoading: false,
          providerError: false,
          capabilityLoading: false,
          capabilityError: false,
        },
      }),
    )

    await flushPromises()
    expect(wrapper.findAll('[data-testid="application-row"]')).toHaveLength(6)
    expect(wrapper.get('h2').text()).toBe('能力面板')
    expect(
      wrapper.get('[data-testid="device-capability-tabs"]').classes(),
    ).toContain('device-capability-panel__tabs')
    expect(wrapper.findAll('.device-capability-panel__tab-label')).toHaveLength(
      2,
    )
    expect(wrapper.findAll('.device-capability-panel__tab-count')).toHaveLength(
      2,
    )
    expect(wrapper.text()).toContain('拼多多自动处理售后工单')
    expect(wrapper.text()).not.toContain('app-private-uuid')
    expect(wrapper.text()).not.toContain('version-1')
    expect(
      wrapper.findAll('[data-testid="capability-icon-slot"]'),
    ).toHaveLength(6)
    expect(
      wrapper
        .findAll('[data-testid="capability-icon-slot"]')
        .every(
          (slot) =>
            slot.attributes('data-capability-type') === 'application' &&
            slot.find('.van-icon').exists(),
        ),
    ).toBe(true)
    expect(wrapper.find('[data-testid="capability-version"]').exists()).toBe(
      false,
    )
    expect(
      wrapper.get('.device-capability-panel__name').attributes('class'),
    ).toContain('device-capability-panel__name')
    const firstRowChildren = wrapper.get('[data-testid="application-row"]')
      .element.children
    expect(firstRowChildren[0]?.classList).toContain(
      'device-capability-panel__icon-slot',
    )
    expect(firstRowChildren[1]?.classList).toContain(
      'device-capability-panel__main-content',
    )
    expect(firstRowChildren[2]?.classList).toContain(
      'device-capability-panel__actions',
    )
    expect(
      Array.from(firstRowChildren[2]!.querySelectorAll('button')).map(
        (button) => button.getAttribute('aria-label'),
      ),
    ).toEqual(['配置：订单应用', '运行：订单应用'])
    await wrapper.get('[aria-label="配置：订单应用"]').trigger('click')
    await wrapper.get('[aria-label="运行：订单应用"]').trigger('click')
    const refreshButton = wrapper.get(
      '[data-testid="device-capability-refresh"]',
    )
    expect(refreshButton.attributes('type')).toBe('button')
    expect(refreshButton.classes()).toContain('mobile-pressable')
    expect(refreshButton.text()).toBe('刷新')
    expect(refreshButton.find('.van-icon').exists()).toBe(true)
    await refreshButton.trigger('click')
    expect(wrapper.emitted('configureApplication')?.[0]?.[0]).toMatchObject({
      app_id: 'app-1',
    })
    expect(wrapper.emitted('runApplication')?.[0]?.[0]).toMatchObject({
      app_id: 'app-1',
    })
    expect(wrapper.emitted('refreshCapability')).toHaveLength(1)
    expect(wrapper.text()).not.toMatch(/成功|已启动|已刷新|已保存/)
  })

  it('shows only Business Skills and hides meaningless Configure actions', async () => {
    const capabilities = [
      {
        ...capability('business-private-uuid', 'business'),
        display_name: '订单同步',
        version: '1.3.0',
        input_schema: {},
      },
      {
        ...capability('business-no-schema-uuid', 'business'),
        display_name: '库存同步',
      },
      capability('internal-1', 'internal'),
      capability('unknown-1', null),
    ]
    const wrapper = track(
      mount(DeviceCapabilityPanel, {
        props: {
          inventories: [],
          capabilities,
          providerLoading: false,
          providerError: false,
          capabilityLoading: false,
          capabilityError: false,
        },
      }),
    )

    await flushPromises()
    await wrapper.get('.van-tab:nth-child(2)').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('[data-testid="skill-row"]')).toHaveLength(2)
    expect(wrapper.text()).toContain('订单同步')
    expect(wrapper.text()).toContain('库存同步')
    expect(wrapper.text()).toContain('v1.3.0')
    expect(wrapper.text()).not.toContain('business-private-uuid')
    expect(wrapper.text()).not.toContain('business-no-schema-uuid')
    expect(wrapper.text()).not.toContain('internal-1')
    expect(wrapper.text()).not.toContain('unknown-1')
    expect(
      wrapper.findAll('[data-testid="capability-icon-slot"]'),
    ).toHaveLength(2)
    expect(
      wrapper
        .findAll('[data-testid="capability-icon-slot"]')
        .every(
          (slot) =>
            slot.attributes('data-capability-type') === 'skill' &&
            slot.find('.van-icon').exists(),
        ),
    ).toBe(true)
    expect(wrapper.find('[aria-label="配置：订单同步"]').exists()).toBe(true)
    expect(wrapper.find('[aria-label="配置：库存同步"]').exists()).toBe(false)
    await wrapper.get('[aria-label="运行：库存同步"]').trigger('click')
    expect(wrapper.emitted('runSkill')?.[0]?.[0]).toMatchObject({
      skill_id: 'business-no-schema-uuid',
    })

    const technicalDetails = track(
      mount(DeviceSkillDetails, { props: { capabilities } }),
    )
    expect(technicalDetails.text()).toContain('能力总数4 个')
    expect(technicalDetails.text()).toContain('未分类能力1 个')
  })

  it('keeps the More Sheet read-only and exposes only real Device facts', async () => {
    const wrapper = track(
      mount(DeviceMoreSheet, {
        props: {
          show: true,
          device: { ...baseDevice, location: '上海', note: '主运行端' },
          inventories: [providerInventory('ready')],
          capabilities: [
            capability('business-1', 'business'),
            capability('internal-1', 'internal'),
          ],
        },
      }),
    )

    expect(wrapper.get('[data-testid="device-more-sheet"]').text()).toContain(
      '更多信息',
    )
    expect(wrapper.text()).toContain('device-1')
    expect(wrapper.text()).toContain('Worker版本1.2.3')
    expect(wrapper.text()).toContain('上海')
    expect(wrapper.text()).toContain('主运行端')
    expect(wrapper.text()).not.toMatch(/设备配置|更多设置|GY00099|5\.36\.1/)

    await wrapper.get('[aria-label="关闭更多信息"]').trigger('click')
    expect(wrapper.emitted('update:show')).toEqual([[false]])
  })
})
