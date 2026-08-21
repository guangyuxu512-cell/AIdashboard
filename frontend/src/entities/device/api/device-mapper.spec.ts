import { describe, expect, it } from 'vitest'
import dayjs from 'dayjs'

import { createMockDeviceDataSource } from './device-data-source'
import { mapDeviceDto, mapYingdaoInventoryDto } from './device-mapper'
import { deviceQueryKeys } from './device-queries'
import { formatRelativeTime } from '../model/display'

const emptyFilters = {
  status: null,
  tag: null,
  workerVersion: null,
  capability: null,
  keyword: '',
} as const

describe('device mapper, query and mutation', () => {
  it('formats heartbeat timestamps as human-readable relative time', () => {
    const now = dayjs('2026-08-21T12:00:00+08:00')
    expect(formatRelativeTime('2026-08-21T11:59:57+08:00', now)).toBe('刚刚')
    expect(formatRelativeTime('2026-08-21T11:58:00+08:00', now)).toBe(
      '2 分钟前',
    )
    expect(formatRelativeTime('2026-08-21T10:00:00+08:00', now)).toBe(
      '2 小时前',
    )
  })

  it('does not translate enabled into an online runtime status', () => {
    const viewModel = mapDeviceDto({
      device_id: '00000000-0000-0000-0000-000000000001',
      display_name: '真实设备',
      enabled: true,
      location: '杭州',
      note: null,
      worker_runtime: null,
      deleted_at: null,
      created_at: '2026-08-18T10:00:00+00:00',
      updated_at: '2026-08-18T11:00:00+00:00',
    })

    expect(viewModel.enabledStatus).toBe('enabled')
    expect(viewModel.runtimeStatus).toBe('unavailable')
    expect(viewModel.workerVersionDisplay).toBe('未接入')
    expect(viewModel.currentTaskName).toBeNull()
    expect(viewModel.cpuUsageDisplay).toBe('—')
  })

  it('maps real Worker runtime without inventing resource telemetry', () => {
    const viewModel = mapDeviceDto({
      device_id: '00000000-0000-0000-0000-000000000001',
      display_name: 'Worker 设备',
      enabled: true,
      location: null,
      note: null,
      worker_runtime: {
        device_id: '00000000-0000-0000-0000-000000000001',
        worker_version: '0.1.0',
        connection_status: 'online',
        last_seen_at: '2026-08-19T08:30:00+00:00',
        started_at: '2026-08-19T08:00:00+00:00',
        updated_at: '2026-08-19T08:30:00+00:00',
      },
      deleted_at: null,
      created_at: '2026-08-18T10:00:00+00:00',
      updated_at: '2026-08-18T11:00:00+00:00',
    })

    expect(viewModel.runtimeStatus).toBe('online')
    expect(viewModel.workerVersionDisplay).toBe('0.1.0')
    expect(viewModel.lastHeartbeatAtDisplay).not.toBe('未接入')
    expect(viewModel.currentTaskName).toBeNull()
    expect(viewModel.cpuUsageDisplay).toBe('—')
    expect(viewModel.memoryUsageDisplay).toBe('—')
  })

  it('maps an offline Worker as a normal device and preserves its last heartbeat', () => {
    const viewModel = mapDeviceDto({
      device_id: '00000000-0000-0000-0000-000000000001',
      display_name: '离线设备',
      enabled: true,
      location: null,
      note: null,
      worker_runtime: {
        device_id: '00000000-0000-0000-0000-000000000001',
        worker_version: '0.1.0',
        connection_status: 'offline',
        last_seen_at: '2026-08-19T08:30:00+00:00',
        started_at: '2026-08-19T08:00:00+00:00',
        updated_at: '2026-08-19T08:31:00+00:00',
      },
      deleted_at: null,
      created_at: '2026-08-18T10:00:00+00:00',
      updated_at: '2026-08-18T11:00:00+00:00',
    })

    expect(viewModel.enabledStatus).toBe('enabled')
    expect(viewModel.runtimeStatus).toBe('offline')
    expect(viewModel.currentTaskName).toBeNull()
    expect(viewModel.lastHeartbeatAtDisplay).not.toBe('未接入')
  })

  it('keeps server pagination in the device query key', () => {
    expect(
      deviceQueryKeys.list({ page: 3, pageSize: 50, filters: emptyFilters }),
    ).toEqual([
      'devices',
      'list',
      { page: 3, pageSize: 50, filters: emptyFilters },
    ])
  })

  it('maps the latest Yingdao provider snapshot without exposing secrets', () => {
    const inventory = mapYingdaoInventoryDto({
      device_id: '00000000-0000-0000-0000-000000000001',
      provider_code: 'yingdao',
      available: true,
      provider_version: '6.2.23',
      account_display: 'GY00999',
      account_type: 'PersonalBasic',
      enterprise_account: false,
      last_discovered_at: '2026-08-20T12:00:00+00:00',
      updated_at: '2026-08-20T12:00:01+00:00',
      inventory: {
        provider: 'yingdao',
        available: true,
        provider_version: '6.2.23',
        logged_in: true,
        account_display: 'GY00999',
        account_type: 'PersonalBasic',
        enterprise_account: false,
        user_id: 'yingdao-user-test',
        applications: [
          {
            app_id: 'app-1',
            app_name: '应用一',
            package_version: '1',
            entrypoint: 'main',
          },
        ],
        discovered_at: '2026-08-20T12:00:00+00:00',
      },
    })

    expect(inventory.availabilityStatus).toBe('available')
    expect(inventory.providerVersion).toBe('6.2.23')
    expect(inventory.accountDisplay).toBe('GY00999')
    expect(inventory.applicationCount).toBe(1)
    expect(inventory.applications[0]).toEqual({
      appId: 'app-1',
      appName: '应用一',
      packageVersion: '1',
      entrypoint: 'main',
    })
  })

  it('creates and updates a mock device record without inventing runtime data', async () => {
    const source = createMockDeviceDataSource()
    const created = await source.create({
      deviceName: 'Mock Device',
      enabled: true,
      location: '',
      note: '',
    })
    const updated = await source.update(created.deviceId, {
      deviceName: 'Mock Device Updated',
      enabled: false,
      location: '测试区',
      note: '',
    })
    const page = await source.list({
      page: 1,
      pageSize: 10,
      filters: emptyFilters,
    })

    expect(updated.runtimeStatus).toBe('unavailable')
    expect(updated.enabledStatus).toBe('disabled')
    expect(page.items[0]?.deviceName).toBe('Mock Device Updated')
    expect(page.total).toBe(9)
  })
})
