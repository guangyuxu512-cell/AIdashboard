import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  DEVICE_CENTER_LIST_PAGE_SIZE,
  DEVICE_CONNECTION_META,
  DEVICE_ENABLED_META,
  DEVICE_FILTER_LIST_PAGE_SIZE,
  DEVICE_REFRESH_INTERVAL_MS,
  DEVICE_SNAPSHOT_REFRESH_INTERVAL_MS,
  deviceQueryKeys,
  flattenDevicePages,
  formatRelativeHeartbeat,
  getDevice,
  getDeviceConnectionDisplayState,
  getDeviceProviderInventories,
  getDevices,
  getDeviceSkillCapabilities,
  getNextDevicePageParam,
  mapDeviceRead,
  summarizeDeviceCapabilities,
  YINGDAO_PROVIDER_STATUS_META,
  type DeviceProviderInventoryReadDto,
  type DeviceReadDto,
  type DeviceSkillCapabilityReadDto,
} from '@/entities/device'
import {
  getActiveTaskQueryOptions,
  getActiveTask,
  TASK_ACTIVE_REFRESH_INTERVAL_MS,
  taskQueryKeys,
  type ActiveTaskSummaryReadDto,
} from '@/entities/task'
import { apiClient } from '@/shared/api'

const deviceDto: DeviceReadDto = {
  device_id: 'device-1',
  display_name: '仓库设备',
  enabled: false,
  location: '华东仓',
  note: '只读备注',
  deleted_at: null,
  worker_runtime: {
    device_id: 'device-1',
    worker_version: '1.2.3',
    connection_status: 'online',
    last_seen_at: '2026-08-26T08:59:00.000Z',
    started_at: '2026-08-26T08:00:00.000Z',
    updated_at: '2026-08-26T08:59:00.000Z',
  },
  created_at: '2026-08-01T00:00:00.000Z',
  updated_at: '2026-08-26T08:59:00.000Z',
}

const activeTaskDto: ActiveTaskSummaryReadDto = {
  task_id: 'task-1',
  target_device_id: 'device-1',
  skill_id: 'sync-orders',
  execution_display_name: '同步订单',
  status: 'running',
  started_at: '2026-08-26T08:00:00.000Z',
  created_at: '2026-08-26T07:59:00.000Z',
  latest_event: null,
}

function capability(
  skillId: string,
  classification: 'business' | 'internal' | null,
): DeviceSkillCapabilityReadDto {
  return {
    device_id: 'device-1',
    skill_id: skillId,
    display_name: skillId,
    runtime: 'python',
    provider: null,
    version: '1.0.0',
    classification,
    input_schema: null,
    updated_at: '2026-08-26T08:00:00.000Z',
  }
}

describe('device center formal contract', () => {
  afterEach(() => vi.restoreAllMocks())

  it('uses only the formal relative Device GET endpoints', async () => {
    const get = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: [] })

    await getDevices({ page: 2, page_size: 20 })
    await getDevice('device/1')
    await getDeviceProviderInventories('device/1')
    await getDeviceSkillCapabilities('device/1')

    expect(get).toHaveBeenNthCalledWith(1, 'devices', {
      params: { page: 2, page_size: 20 },
    })
    expect(get).toHaveBeenNthCalledWith(2, 'devices/device%2F1')
    expect(get).toHaveBeenNthCalledWith(
      3,
      'devices/device%2F1/provider-inventories',
    )
    expect(get).toHaveBeenNthCalledWith(
      4,
      'devices/device%2F1/skill-capabilities',
    )
  })

  it('maps Active Task 204 to idle and preserves the 200 DTO', async () => {
    const get = vi
      .spyOn(apiClient, 'get')
      .mockResolvedValueOnce({ status: 204, data: undefined })
      .mockResolvedValueOnce({ status: 200, data: activeTaskDto })

    await expect(getActiveTask('device/idle')).resolves.toBeNull()
    await expect(getActiveTask('device-1')).resolves.toEqual(activeTaskDto)
    expect(get).toHaveBeenNthCalledWith(1, 'tasks/active/device%2Fidle')
    expect(get).toHaveBeenNthCalledWith(2, 'tasks/active/device-1')
  })

  it('isolates the 20-row Device Center cache from the 100-row Task filter cache', () => {
    expect(DEVICE_CENTER_LIST_PAGE_SIZE).toBe(20)
    expect(DEVICE_FILTER_LIST_PAGE_SIZE).toBe(100)
    expect(deviceQueryKeys.list(20)).not.toEqual(deviceQueryKeys.list(100))
    expect(deviceQueryKeys.list(20)).toEqual([
      'devices',
      'list',
      { pageSize: 20 },
    ])
    expect(DEVICE_REFRESH_INTERVAL_MS).toBe(15_000)
    expect(DEVICE_SNAPSHOT_REFRESH_INTERVAL_MS).toBe(60_000)
    expect(TASK_ACTIVE_REFRESH_INTERVAL_MS).toBe(5_000)
    expect(taskQueryKeys.active('device-1')).toEqual([
      'tasks',
      'active',
      'device-1',
    ])
    const activeOptions = getActiveTaskQueryOptions('device-1')
    expect(activeOptions.queryKey.value).toEqual(
      taskQueryKeys.active('device-1'),
    )
    expect(activeOptions.refetchInterval.value).toBe(
      TASK_ACTIVE_REFRESH_INTERVAL_MS,
    )
  })

  it('maps the Device DTO without merging enabled and connection facts', () => {
    expect(mapDeviceRead(deviceDto)).toEqual(
      expect.objectContaining({
        deviceId: 'device-1',
        displayName: '仓库设备',
        enabled: false,
        workerRuntime: expect.objectContaining({
          connectionStatus: 'online',
          workerVersion: '1.2.3',
        }),
      }),
    )
    expect(getDeviceConnectionDisplayState(null)).toBe('unreported')
    expect(getDeviceConnectionDisplayState(undefined)).toBe('unreported')
    expect(getDeviceConnectionDisplayState('offline')).toBe('offline')
    expect(DEVICE_ENABLED_META.disabled.label).toBe('已停用')
    expect(DEVICE_CONNECTION_META.online.label).toBe('在线')
    expect('unreported' in DEVICE_CONNECTION_META).toBe(false)
  })

  it('keeps backend order while deduplicating device_id across pages', () => {
    const duplicate = { ...deviceDto, display_name: '重复设备' }
    const second = { ...deviceDto, device_id: 'device-2' }

    const devices = flattenDevicePages([
      { items: [deviceDto], total: 2, page: 1, page_size: 20 },
      { items: [duplicate, second], total: 2, page: 2, page_size: 20 },
    ])

    expect(devices.map((device) => device.deviceId)).toEqual([
      'device-1',
      'device-2',
    ])
    expect(devices[0]?.displayName).toBe('仓库设备')
  })

  it('continues pagination only when backend totals require another page', () => {
    expect(
      getNextDevicePageParam({
        items: [deviceDto],
        total: 21,
        page: 1,
        page_size: 20,
      }),
    ).toBe(2)
    expect(
      getNextDevicePageParam({
        items: [deviceDto],
        total: 20,
        page: 1,
        page_size: 20,
      }),
    ).toBeUndefined()
  })

  it('formats heartbeat only as display text and never derives a status', () => {
    const now = new Date('2026-08-26T09:00:00.000Z')

    expect(
      formatRelativeHeartbeat(deviceDto.worker_runtime!.last_seen_at, now),
    ).toBe('1 分钟前')
    expect(formatRelativeHeartbeat('2026-08-24T09:00:00.000Z', now)).toBe(
      '2 天前',
    )
    expect(formatRelativeHeartbeat(null, now)).toBe('—')
  })

  it('owns all six provider labels and keeps availability facts separate', () => {
    expect(
      Object.fromEntries(
        Object.entries(YINGDAO_PROVIDER_STATUS_META).map(([status, meta]) => [
          status,
          meta.label,
        ]),
      ),
    ).toEqual({
      not_installed: '未安装',
      version_unsupported: '版本不支持',
      starting: '启动中',
      need_login: '需要登录',
      interface_unreachable: '接口不可达',
      ready: '就绪',
    })

    const inventory = {
      available: true,
      inventory: {
        available: false,
        execution_available: true,
        logged_in: false,
      },
    } as DeviceProviderInventoryReadDto
    expect(inventory.available).toBe(true)
    expect(inventory.inventory.available).toBe(false)
    expect(inventory.inventory.execution_available).toBe(true)
    expect(inventory.inventory.logged_in).toBe(false)
  })

  it('counts business, internal and null classifications without guessing', () => {
    expect(
      summarizeDeviceCapabilities([
        capability('business-1', 'business'),
        capability('business-2', 'business'),
        capability('internal-1', 'internal'),
        capability('unknown-1', null),
      ]),
    ).toEqual({ business: 2, internal: 1, unclassified: 1, total: 4 })
  })
})
