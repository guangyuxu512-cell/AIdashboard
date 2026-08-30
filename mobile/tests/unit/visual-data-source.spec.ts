import { afterEach, describe, expect, it, vi } from 'vitest'
import type { AxiosResponse } from 'axios'

import {
  configureMobileDataSources,
  resolveMobileDataMode,
} from '@/app/providers/mobile-data-sources'
import {
  getDevice,
  getDeviceProviderInventories,
  getDevices,
  getDeviceSkillCapabilities,
} from '@/entities/device'
import {
  getActiveTask,
  getTask,
  getTaskEvents,
  getTasks,
} from '@/entities/task'
import { apiClient } from '@/shared/api'

describe('development-only visual data sources', () => {
  afterEach(async () => {
    vi.restoreAllMocks()
    await configureMobileDataSources('real')
  })

  it('enables mock only for a Development visual mode', () => {
    expect(resolveMobileDataMode(true, 'visual')).toBe('mock')
    expect(resolveMobileDataMode(true, 'development')).toBe('real')
    expect(resolveMobileDataMode(false, 'visual')).toBe('real')
    expect(resolveMobileDataMode(false, 'production')).toBe('real')
  })

  it('provides twenty contract-shaped devices and exact overview facts', async () => {
    await configureMobileDataSources('mock')
    const response = await getDevices({ page: 1, page_size: 20 })
    const statuses = response.items.map(
      (device) => device.worker_runtime?.connection_status ?? null,
    )
    const activeTasks = await Promise.all(
      response.items.map((device) => getActiveTask(device.device_id)),
    )

    expect(response.total).toBe(20)
    expect(statuses.filter((status) => status === 'online')).toHaveLength(8)
    expect(statuses.filter((status) => status === 'offline')).toHaveLength(12)
    expect(statuses.filter((status) => status === null)).toHaveLength(0)
    expect(response.items.filter((device) => !device.enabled)).toHaveLength(3)
    expect(
      activeTasks.filter((task) => task?.status === 'running'),
    ).toHaveLength(1)
    expect(
      activeTasks.filter((task) => task?.status === 'pending'),
    ).toHaveLength(0)
  })

  it('uses the same detail, provider and capability contracts as real mode', async () => {
    await configureMobileDataSources('mock')
    const deviceId = 'visual-device-operations'

    await expect(getDevice(deviceId)).resolves.toEqual(
      expect.objectContaining({
        device_id: deviceId,
        display_name: '运营',
      }),
    )
    const inventories = await getDeviceProviderInventories(deviceId)
    expect(inventories).toEqual([
      expect.objectContaining({
        device_id: deviceId,
        provider_code: 'yingdao',
        inventory: expect.objectContaining({ status: 'ready' }),
      }),
    ])
    expect(inventories[0]?.inventory).toEqual(
      expect.objectContaining({
        provider_version: '6.3.6',
        execution_version: '6.3.6',
      }),
    )
    expect(inventories[0]?.inventory.applications).toHaveLength(8)

    const capabilities = await getDeviceSkillCapabilities(deviceId)
    expect(capabilities).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ classification: 'business' }),
        expect.objectContaining({ classification: 'internal' }),
      ]),
    )
    const businessCapabilities = capabilities.filter(
      (item) => item.classification === 'business',
    )
    expect(businessCapabilities).toHaveLength(5)
    expect(
      businessCapabilities.every(
        (item) => item.runtime === 'python' && item.provider === null,
      ),
    ).toBe(true)
  })

  it('provides all five task states, detail and runtime events', async () => {
    await configureMobileDataSources('mock')
    const response = await getTasks({ page: 1, page_size: 20 })

    expect(response.total).toBe(5)
    expect(new Set(response.items.map((task) => task.status))).toEqual(
      new Set(['running', 'success', 'failed', 'pending', 'lost']),
    )
    await expect(getTask('visual-task-running')).resolves.toEqual(
      expect.objectContaining({ status: 'running' }),
    )
    await expect(
      getTaskEvents('visual-task-running', { limit: 100 }),
    ).resolves.toEqual(
      expect.objectContaining({
        task_id: 'visual-task-running',
        items: expect.arrayContaining([
          expect.objectContaining({ event_type: 'progress' }),
        ]),
      }),
    )
  })

  it('never falls back to visual data when the real source rejects', async () => {
    await configureMobileDataSources('real')
    vi.spyOn(apiClient, 'get').mockRejectedValueOnce(
      new Error('backend unavailable'),
    )

    await expect(getDevices({ page: 1, page_size: 20 })).rejects.toThrow(
      'backend unavailable',
    )
  })

  it('keeps the last requested mode when configuration overlaps', async () => {
    const realPage = {
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
    }
    vi.spyOn(apiClient, 'get').mockResolvedValueOnce({
      data: realPage,
    } as AxiosResponse<typeof realPage>)

    await Promise.all([
      configureMobileDataSources('mock'),
      configureMobileDataSources('real'),
    ])

    await expect(getDevices({ page: 1, page_size: 20 })).resolves.toEqual(
      realPage,
    )
    expect(apiClient.get).toHaveBeenCalledOnce()
  })
})
