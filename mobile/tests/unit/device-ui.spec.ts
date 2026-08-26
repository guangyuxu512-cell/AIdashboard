import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import {
  DeviceConnectionTag,
  DeviceEnabledTag,
  type Device,
  type DeviceProviderInventoryReadDto,
  type DeviceSkillCapabilityReadDto,
  type YingdaoProviderStatusDto,
} from '@/entities/device'
import type { ActiveTaskSummaryReadDto } from '@/entities/task'
import {
  ActiveTaskSummary,
  DeviceInfiniteList,
  DeviceListCard,
  DeviceProviderDetails,
  DeviceProviderSection,
  DeviceSkillDetails,
  DeviceSkillSummary,
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
  backgroundError: false,
  nextPageError: false,
  errorMessage: '设备请求失败',
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
  errorMessage: '当前任务失败',
  retry: () => undefined,
}

function providerInventory(
  status: YingdaoProviderStatusDto,
): DeviceProviderInventoryReadDto {
  return {
    device_id: 'device-1',
    provider_code: 'yingdao',
    available: true,
    provider_version: '3.4.5',
    account_display: '测试账号',
    account_type: 'enterprise',
    enterprise_account: true,
    last_discovered_at: '2026-08-26T08:00:00.000Z',
    inventory: {
      provider: 'yingdao',
      available: false,
      status,
      status_reason_code: 'REASON',
      status_reason: '状态说明',
      provider_version: '3.4.5',
      execution_available: true,
      execution_version: '2.0.0',
      execution_unavailable_reason: null,
      logged_in: false,
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
    runtime: 'rpa',
    provider: 'yingdao',
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

function mountDeviceCard(device: Device): VueWrapper {
  return track(
    mount(DeviceListCard, {
      props: { device, activeTaskState: idleActiveTaskState },
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
    const unreported = track(
      mount(DeviceConnectionTag, { props: { status: null } }),
    )

    expect(enabled.text()).toBe('已启用')
    expect(disabled.text()).toBe('已停用')
    expect(online.text()).toBe('在线')
    expect(offline.text()).toBe('离线')
    expect(unreported.text()).toBe('未上报')
  })

  it.each([
    ['online', true, '在线', '已启用'],
    ['offline', false, '离线', '已停用'],
  ] as const)(
    'shows %s runtime while preserving enabled=%s',
    async (connectionStatus, enabled, connectionLabel, enabledLabel) => {
      const wrapper = mountDeviceCard({
        ...baseDevice,
        enabled,
        workerRuntime: {
          ...baseDevice.workerRuntime!,
          connectionStatus,
        },
      })
      await flushPromises()

      expect(wrapper.text()).toContain(connectionLabel)
      expect(wrapper.text()).toContain(enabledLabel)
      expect(wrapper.text()).toContain('1.2.3')
      expect(wrapper.text()).toContain('空闲')
    },
  )

  it('renders a null Runtime as unreported instead of offline', async () => {
    const wrapper = mountDeviceCard({ ...baseDevice, workerRuntime: null })
    await flushPromises()

    expect(wrapper.text()).toContain('未上报')
    expect(wrapper.text()).not.toContain('离线')
    expect(wrapper.text()).toContain('版本 —')
  })

  it.each([
    ['pending', '待执行'],
    ['running', '执行中'],
  ] as const)('renders a selectable %s Active Task', async (status, label) => {
    const wrapper = track(
      mount(ActiveTaskSummary, {
        props: {
          task: { ...runningTask, status },
          initialLoading: false,
          initialError: false,
          backgroundError: false,
          errorMessage: '当前任务失败',
        },
      }),
    )

    expect(wrapper.text()).toContain('同步订单')
    expect(wrapper.text()).toContain(label)
    expect(wrapper.text()).toContain('正在执行')
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('select')).toEqual([['task-running']])
  })

  it('uses a compact list summary without rendering latest_event', () => {
    const wrapper = track(
      mount(ActiveTaskSummary, {
        props: {
          task: runningTask,
          initialLoading: false,
          initialError: false,
          backgroundError: false,
          errorMessage: '当前任务失败',
          compact: true,
        },
      }),
    )

    expect(wrapper.text()).toContain('同步订单')
    expect(wrapper.text()).toContain('执行中')
    expect(wrapper.text()).not.toContain('正在执行')
    expect(wrapper.text()).not.toContain('当前任务')
  })

  it('only claims idle after a successful null Active Task response', () => {
    const loading = track(
      mount(ActiveTaskSummary, {
        props: {
          task: undefined,
          initialLoading: true,
          initialError: false,
          backgroundError: false,
          errorMessage: '当前任务失败',
        },
      }),
    )
    const idle = track(
      mount(ActiveTaskSummary, {
        props: {
          task: null,
          initialLoading: false,
          initialError: false,
          backgroundError: false,
          errorMessage: '当前任务失败',
        },
      }),
    )

    expect(loading.text()).not.toContain('空闲')
    expect(idle.text()).toContain('空闲')
  })

  it('keeps a cached Active Task during a background error and offers initial retry', async () => {
    const background = track(
      mount(ActiveTaskSummary, {
        props: {
          task: runningTask,
          initialLoading: false,
          initialError: false,
          backgroundError: true,
          errorMessage: '当前任务后台失败',
        },
      }),
    )
    expect(background.text()).toContain('当前任务后台失败')
    expect(background.text()).toContain('同步订单')

    const initial = track(
      mount(ActiveTaskSummary, {
        props: {
          task: undefined,
          initialLoading: false,
          initialError: true,
          backgroundError: false,
          errorMessage: '当前任务初始失败',
        },
      }),
    )
    await initial.get('button').trigger('click')
    expect(initial.emitted('retry')).toHaveLength(1)
    expect(initial.text()).not.toContain('空闲')
  })

  it('covers Device list loading, empty, initial and cached background errors', () => {
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
    const background = track(
      mount(DeviceInfiniteList, {
        props: {
          ...listProps,
          devices: [baseDevice],
          backgroundError: true,
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
    expect(
      background.find('[data-testid="device-background-error"]').exists(),
    ).toBe(true)
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

  it.each([
    ['not_installed', '未安装'],
    ['version_unsupported', '版本不支持'],
    ['starting', '启动中'],
    ['need_login', '需要登录'],
    ['interface_unreachable', '接口不可达'],
    ['ready', '就绪'],
  ] as const)('renders Provider status %s', (status, label) => {
    const wrapper = track(
      mount(DeviceProviderSection, {
        props: {
          inventories: [providerInventory(status)],
          initialLoading: false,
          initialError: false,
          backgroundError: false,
          errorMessage: 'Provider 请求失败',
        },
      }),
    )

    expect(wrapper.text()).toContain(label)
    expect(wrapper.text()).toContain('账号测试账号')
    expect(wrapper.text()).toContain('提供方版本3.4.5')
    expect(wrapper.text()).toContain('影刀应用数1 个')
    expect(wrapper.text()).not.toContain('提供方可用')
  })

  it('renders Provider secondary facts only in the technical details component', () => {
    const wrapper = track(
      mount(DeviceProviderDetails, {
        props: { inventories: [providerInventory('ready')] },
      }),
    )

    expect(wrapper.text()).toContain('提供方代码yingdao')
    expect(wrapper.text()).toContain('提供方可用否')
    expect(wrapper.text()).toContain('执行接口可用是')
    expect(wrapper.text()).toContain('已登录否')
    expect(wrapper.text()).toContain('账号类型enterprise')
    expect(wrapper.text()).toContain('企业账号是')
    expect(wrapper.text()).toContain('执行接口版本2.0.0')
    expect(wrapper.text()).toContain('状态说明状态说明')
  })

  it('distinguishes an empty Provider snapshot and preserves cached data on error', async () => {
    const empty = track(
      mount(DeviceProviderSection, {
        props: {
          inventories: [],
          initialLoading: false,
          initialError: false,
          backgroundError: false,
          errorMessage: 'Provider 请求失败',
        },
      }),
    )
    const background = track(
      mount(DeviceProviderSection, {
        props: {
          inventories: [providerInventory('ready')],
          initialLoading: false,
          initialError: false,
          backgroundError: true,
          errorMessage: 'Provider 后台失败',
        },
      }),
    )

    expect(empty.text()).toContain('尚未上报影刀快照')
    expect(background.text()).toContain('Provider 后台失败')
    expect(background.text()).toContain('就绪')
    await background.get('button').trigger('click')
    expect(background.emitted('retry')).toHaveLength(1)
  })

  it('keeps Provider loading and initial error distinct from an empty snapshot', async () => {
    const loading = track(
      mount(DeviceProviderSection, {
        props: {
          inventories: undefined,
          initialLoading: true,
          initialError: false,
          backgroundError: false,
          errorMessage: '影刀快照加载失败',
        },
      }),
    )
    expect(loading.text()).toContain('加载影刀快照中')
    expect(loading.text()).not.toContain('尚未上报影刀快照')

    const initialError = track(
      mount(DeviceProviderSection, {
        props: {
          inventories: undefined,
          initialLoading: false,
          initialError: true,
          backgroundError: false,
          errorMessage: '影刀快照加载失败',
        },
      }),
    )
    await initialError.get('button').trigger('click')
    expect(initialError.emitted('retry')).toHaveLength(1)
    expect(initialError.text()).not.toContain('尚未上报影刀快照')
  })

  it('counts all three Skill classifications and keeps empty/error states explicit', async () => {
    const capabilities = [
      capability('business-1', 'business'),
      capability('business-2', 'business'),
      capability('internal-1', 'internal'),
      capability('unknown-1', null),
    ]
    const summary = track(
      mount(DeviceSkillSummary, {
        props: {
          capabilities,
          initialLoading: false,
          initialError: false,
          backgroundError: false,
          errorMessage: 'Skill 请求失败',
        },
      }),
    )
    expect(summary.text()).toContain('业务能力2 个')
    expect(summary.text()).toContain('内部能力1 个')
    expect(summary.text()).not.toContain('未分类能力')

    const technicalDetails = track(
      mount(DeviceSkillDetails, { props: { capabilities } }),
    )
    expect(technicalDetails.text()).toContain('能力总数4 个')
    expect(technicalDetails.text()).toContain('未分类能力1 个')

    const empty = track(
      mount(DeviceSkillSummary, {
        props: {
          capabilities: [],
          initialLoading: false,
          initialError: false,
          backgroundError: false,
          errorMessage: 'Skill 请求失败',
        },
      }),
    )
    expect(empty.text()).toContain('暂无技能能力记录')

    const initialError = track(
      mount(DeviceSkillSummary, {
        props: {
          capabilities: undefined,
          initialLoading: false,
          initialError: true,
          backgroundError: false,
          errorMessage: 'Skill 初始失败',
        },
      }),
    )
    await initialError.get('button').trigger('click')
    expect(initialError.emitted('retry')).toHaveLength(1)

    const background = track(
      mount(DeviceSkillSummary, {
        props: {
          capabilities,
          initialLoading: false,
          initialError: false,
          backgroundError: true,
          errorMessage: '技能能力后台失败',
        },
      }),
    )
    expect(background.text()).toContain('技能能力后台失败')
    expect(background.text()).toContain('业务能力2 个')
    await background.get('button').trigger('click')
    expect(background.emitted('retry')).toHaveLength(1)
  })
})
