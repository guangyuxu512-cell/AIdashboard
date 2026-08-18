import { describe, expect, it } from 'vitest'

import { createMockDeviceDataSource } from './device-data-source'
import { mapDeviceDto } from './device-mapper'
import { deviceQueryKeys } from './device-queries'

const emptyFilters = {
  status: null,
  tag: null,
  workerVersion: null,
  capability: null,
  keyword: '',
} as const

describe('device mapper, query and mutation', () => {
  it('does not translate enabled into an online runtime status', () => {
    const viewModel = mapDeviceDto({
      device_id: '00000000-0000-0000-0000-000000000001',
      display_name: '真实设备',
      enabled: true,
      location: '杭州',
      note: null,
      worker_runtime: null,
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

  it('keeps server pagination in the device query key', () => {
    expect(
      deviceQueryKeys.list({ page: 3, pageSize: 50, filters: emptyFilters }),
    ).toEqual([
      'devices',
      'list',
      { page: 3, pageSize: 50, filters: emptyFilters },
    ])
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
