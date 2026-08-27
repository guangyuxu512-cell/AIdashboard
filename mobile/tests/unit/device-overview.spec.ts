import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import type { Device } from '@/entities/device'
import type { ActiveTaskSummaryReadDto } from '@/entities/task'
import type { DeviceActiveTaskState } from '@/features/device-center'
import { DeviceOverviewCards } from '@/features/device-center'
import {
  filterDevicesByQuickFilter,
  getDeviceQuickFilterLabel,
  toggleDeviceMetricFilter,
} from '@/features/device-center/model/device-filter'
import { summarizeDeviceOverview } from '@/features/device-center/model/device-overview'

function device(
  deviceId: string,
  connectionStatus: 'online' | 'offline' | null,
): Device {
  return {
    deviceId,
    displayName: deviceId,
    enabled: true,
    location: null,
    note: null,
    deletedAt: null,
    workerRuntime:
      connectionStatus === null
        ? null
        : {
            deviceId,
            workerVersion: '1.0.0',
            connectionStatus,
            lastSeenAt: '2026-08-26T08:59:00.000Z',
            startedAt: '2026-08-26T08:00:00.000Z',
            updatedAt: '2026-08-26T08:59:00.000Z',
          },
    createdAt: '2026-08-01T00:00:00.000Z',
    updatedAt: '2026-08-26T08:59:00.000Z',
  }
}

function activeTask(
  deviceId: string,
  status: 'pending' | 'running',
): ActiveTaskSummaryReadDto {
  return {
    task_id: `task-${deviceId}`,
    target_device_id: deviceId,
    skill_id: 'sync-orders',
    execution_display_name: '同步订单',
    status,
    started_at: status === 'running' ? '2026-08-26T08:00:00.000Z' : null,
    created_at: '2026-08-26T07:59:00.000Z',
    latest_event: null,
  }
}

function activeState(
  task: ActiveTaskSummaryReadDto | null | undefined,
  overrides: Partial<DeviceActiveTaskState> = {},
): DeviceActiveTaskState {
  const hasSuccessfulData = task !== undefined
  return {
    task,
    hasSuccessfulData,
    initialLoading: !hasSuccessfulData,
    initialError: false,
    backgroundError: false,
    retry: () => undefined,
    ...overrides,
  }
}

describe('device center overview', () => {
  it('keeps all three metrics unknown before the Device page succeeds', () => {
    const overview = summarizeDeviceOverview([], {}, 'loading')
    const wrapper = mount(DeviceOverviewCards, { props: { overview } })

    expect(overview.onlineCount).toBeNull()
    expect(overview.offlineCount).toBeNull()
    expect(overview.runningCount).toBeNull()
    expect(wrapper.get('[data-testid="summary-online"]').text()).toBe('—')
    expect(wrapper.get('[data-testid="summary-running"]').text()).toBe('—')
    expect(wrapper.get('[data-testid="summary-offline"]').text()).toBe('—')
    expect(wrapper.text()).toBe('—在线设备—运行中—离线设备')
    expect(wrapper.get('ul').attributes('aria-busy')).toBe('true')
    expect(wrapper.findAll('button')).toHaveLength(3)
    expect(
      wrapper
        .findAll('button')
        .every((button) => button.attributes('disabled') !== undefined),
    ).toBe(true)
  })

  it('keeps an initial Device error free of implementation explanations', () => {
    const overview = summarizeDeviceOverview([], {}, 'error')
    const wrapper = mount(DeviceOverviewCards, { props: { overview } })

    expect(overview.dataState).toBe('error')
    expect(overview.onlineCount).toBeNull()
    expect(overview.offlineCount).toBeNull()
    expect(overview.runningCount).toBeNull()
    expect(wrapper.get('[data-testid="summary-online"]').text()).toBe('—')
    expect(wrapper.get('[data-testid="summary-running"]').text()).toBe('—')
    expect(wrapper.get('[data-testid="summary-offline"]').text()).toBe('—')
    expect(wrapper.text()).toBe('—在线设备—运行中—离线设备')
    expect(wrapper.text()).not.toMatch(/统计|加载|已确认|数据/)
  })

  it('counts only loaded connection facts and excludes unreported Runtime from offline', () => {
    const devices = [
      device('device-online', 'online'),
      device('device-offline', 'offline'),
      device('device-unreported', null),
    ]
    const overview = summarizeDeviceOverview(
      devices,
      {
        'device-online': activeState(activeTask('device-online', 'running')),
        'device-offline': activeState(activeTask('device-offline', 'pending')),
        'device-unreported': activeState(null),
      },
      'ready',
    )
    const wrapper = mount(DeviceOverviewCards, { props: { overview } })

    expect(overview).toEqual(
      expect.objectContaining({
        loadedCount: 3,
        onlineCount: 1,
        offlineCount: 1,
        unreportedCount: 1,
        runningCount: 1,
        activeConfirmedCount: 3,
        activeUnknownCount: 0,
      }),
    )
    expect(
      wrapper
        .findAll('.mobile-summary-strip__label')
        .map((item) => item.text()),
    ).toEqual(['在线设备', '运行中', '离线设备'])
    expect(wrapper.findAll('.mobile-summary-strip__icon')).toHaveLength(3)
    expect(wrapper.text()).not.toContain('连接状态')
    expect(wrapper.get('[data-testid="summary-running"]').text()).toBe('1')
  })

  it('maps the three metrics to formal facts and emits the shared quick filter', async () => {
    const devices = [
      device('device-online-running', 'online'),
      device('device-online-idle', 'online'),
      device('device-offline', 'offline'),
      device('device-unreported', null),
    ]
    const states = {
      'device-online-running': activeState(
        activeTask('device-online-running', 'running'),
      ),
      'device-online-idle': activeState(null),
      'device-offline': activeState(activeTask('device-offline', 'pending')),
      'device-unreported': activeState(null),
    }
    const overview = summarizeDeviceOverview(devices, states, 'ready')
    const wrapper = mount(DeviceOverviewCards, {
      props: { overview, filter: 'online' },
    })

    expect(
      filterDevicesByQuickFilter(devices, states, 'online').map(
        (item) => item.deviceId,
      ),
    ).toEqual(['device-online-running', 'device-online-idle'])
    expect(
      filterDevicesByQuickFilter(devices, states, 'running').map(
        (item) => item.deviceId,
      ),
    ).toEqual(['device-online-running'])
    expect(
      filterDevicesByQuickFilter(devices, states, 'offline').map(
        (item) => item.deviceId,
      ),
    ).toEqual(['device-offline'])
    expect(toggleDeviceMetricFilter('all', 'online')).toBe('online')
    expect(toggleDeviceMetricFilter('online', 'online')).toBe('all')
    expect(getDeviceQuickFilterLabel('all')).toBe('全部')
    expect(getDeviceQuickFilterLabel('online')).toBe('在线')
    expect(getDeviceQuickFilterLabel('running')).toBe('运行中')
    expect(getDeviceQuickFilterLabel('offline')).toBe('离线')

    const online = wrapper.get('[data-testid="summary-metric-online"]')
    const running = wrapper.get('[data-testid="summary-metric-running"]')
    expect(online.attributes('aria-pressed')).toBe('true')
    expect(running.attributes('aria-pressed')).toBe('false')
    expect(online.attributes('aria-label')).toContain('点击恢复全部')
    await online.trigger('click')
    await running.trigger('click')
    expect(wrapper.emitted('select')).toEqual([['online'], ['running']])
  })

  it('keeps all metrics unknown until every Backend page is loaded', () => {
    const devices = [
      device('device-online', 'online'),
      device('device-offline', 'offline'),
    ]
    const overview = summarizeDeviceOverview(
      devices,
      {
        'device-online': activeState(activeTask('device-online', 'running')),
        'device-offline': activeState(null),
      },
      'ready',
      3,
    )
    const wrapper = mount(DeviceOverviewCards, { props: { overview } })

    expect(overview.loadedCount).toBe(2)
    expect(overview.activeState).toBe('partial')
    expect(overview.onlineCount).toBeNull()
    expect(overview.runningCount).toBeNull()
    expect(overview.offlineCount).toBeNull()
    expect(wrapper.text()).toBe('—在线设备—运行中—离线设备')
    expect(wrapper.text()).not.toMatch(/分页|统计|已加载/)
  })

  it('keeps partial Active Task counts honest without rendering a scope explanation', () => {
    const devices = [
      device('device-1', 'online'),
      device('device-2', 'online'),
      device('device-3', 'offline'),
    ]
    const overview = summarizeDeviceOverview(
      devices,
      {
        'device-1': activeState(activeTask('device-1', 'running')),
        'device-2': activeState(undefined, {
          initialLoading: false,
          initialError: true,
        }),
      },
      'ready',
    )
    const wrapper = mount(DeviceOverviewCards, { props: { overview } })

    expect(overview.activeState).toBe('partial')
    expect(overview.runningCount).toBeNull()
    expect(overview.activeConfirmedCount).toBe(1)
    expect(overview.activeUnknownCount).toBe(2)
    expect(wrapper.get('[data-testid="summary-running"]').text()).toBe('—')
    expect(wrapper.text()).not.toMatch(/已确认|统计|当前已加载/)

    const allUnknown = summarizeDeviceOverview(devices, {}, 'ready')
    expect(allUnknown.runningCount).toBeNull()
    expect(allUnknown.activeState).toBe('loading')

    const allFailed = summarizeDeviceOverview(
      devices,
      Object.fromEntries(
        devices.map((item) => [
          item.deviceId,
          activeState(undefined, {
            initialLoading: false,
            initialError: true,
          }),
        ]),
      ),
      'ready',
    )
    expect(allFailed.runningCount).toBeNull()
    expect(allFailed.activeState).toBe('error')

    const onlyPendingIsKnown = summarizeDeviceOverview(
      devices,
      {
        'device-1': activeState(activeTask('device-1', 'pending')),
      },
      'ready',
    )
    expect(onlyPendingIsKnown.runningCount).toBeNull()
    expect(onlyPendingIsKnown.activeState).toBe('partial')
  })

  it('keeps cached running data during a background error without explanatory copy', () => {
    const devices = [
      device('device-1', 'online'),
      device('device-2', 'offline'),
    ]
    const overview = summarizeDeviceOverview(
      devices,
      {
        'device-1': activeState(activeTask('device-1', 'running'), {
          backgroundError: true,
        }),
        'device-2': activeState(null),
      },
      'ready',
    )
    const wrapper = mount(DeviceOverviewCards, { props: { overview } })

    expect(overview.runningCount).toBe(1)
    expect(overview.activeConfirmedCount).toBe(2)
    expect(overview.activeBackgroundErrorCount).toBe(1)
    expect(wrapper.get('[data-testid="summary-running"]').text()).toBe('1')
    expect(wrapper.text()).not.toMatch(/刷新失败|已确认|保留/)

    const partialWithBackgroundError = summarizeDeviceOverview(
      [...devices, device('device-3', 'online')],
      {
        'device-1': activeState(activeTask('device-1', 'running'), {
          backgroundError: true,
        }),
        'device-2': activeState(null),
      },
      'ready',
    )
    expect(partialWithBackgroundError.runningCount).toBeNull()
  })

  it('shows exact zeros after a successful empty Device page', () => {
    const overview = summarizeDeviceOverview([], {}, 'ready')
    const wrapper = mount(DeviceOverviewCards, { props: { overview } })

    expect(overview.activeState).toBe('ready')
    expect(wrapper.get('[data-testid="summary-online"]').text()).toBe('0')
    expect(wrapper.get('[data-testid="summary-running"]').text()).toBe('0')
    expect(wrapper.get('[data-testid="summary-offline"]').text()).toBe('0')
  })
})
