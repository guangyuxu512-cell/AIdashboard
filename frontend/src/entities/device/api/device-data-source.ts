import dayjs from 'dayjs'

import { apiMode, type ApiMode, type PageResult } from '@/shared/api'

import { DEVICE_LIST_FIXTURE } from '../fixtures/device-list.fixture'
import type {
  DeviceListFilters,
  DeviceListItemViewModel,
  DeviceSaveInput,
} from '../model/types'
import { deviceApi } from './device-api'
import {
  mapDeviceCreateInput,
  mapDeviceDto,
  mapDeviceUpdateInput,
} from './device-mapper'

export interface DeviceListParams {
  page: number
  pageSize: number
  filters: DeviceListFilters
}

export interface DeviceDataSource {
  readonly mode: ApiMode
  readonly supportsFilters: boolean
  list(params: DeviceListParams): Promise<PageResult<DeviceListItemViewModel>>
  get(deviceId: string): Promise<DeviceListItemViewModel>
  create(input: DeviceSaveInput): Promise<DeviceListItemViewModel>
  update(
    deviceId: string,
    input: DeviceSaveInput,
  ): Promise<DeviceListItemViewModel>
  setEnabled(
    deviceId: string,
    enabled: boolean,
  ): Promise<DeviceListItemViewModel>
  remove(deviceId: string): Promise<void>
}

function cloneFixtureRows(): DeviceListItemViewModel[] {
  return DEVICE_LIST_FIXTURE.map((device) => ({
    ...device,
    tags: [...device.tags],
    capabilities: device.capabilities.map((capability) => ({ ...capability })),
  }))
}

export function createMockDeviceDataSource(): DeviceDataSource {
  const rows = cloneFixtureRows()
  let sequence = rows.length + 1

  return {
    mode: 'mock',
    supportsFilters: true,
    async list(params) {
      const keyword = params.filters.keyword.trim().toLocaleLowerCase()
      const filtered = rows.filter((device) => {
        const matchesKeyword =
          !keyword ||
          [
            device.deviceName,
            device.location,
            device.systemDisplay,
            ...device.tags,
          ].some((value) => value.toLocaleLowerCase().includes(keyword))
        const matchesCapability =
          !params.filters.capability ||
          device.capabilities.some(
            (capability) =>
              capability.capability === params.filters.capability &&
              capability.availability === 'available',
          )
        return (
          matchesKeyword &&
          matchesCapability &&
          (!params.filters.status ||
            device.runtimeStatus === params.filters.status) &&
          (!params.filters.tag || device.tags.includes(params.filters.tag)) &&
          (!params.filters.workerVersion ||
            device.workerVersionDisplay === params.filters.workerVersion)
        )
      })
      const start = (params.page - 1) * params.pageSize
      return {
        items: filtered.slice(start, start + params.pageSize),
        total: filtered.length,
        page: params.page,
        pageSize: params.pageSize,
      }
    },
    async get(deviceId) {
      const device = rows.find((item) => item.deviceId === deviceId)
      if (!device) throw new Error('设备不存在')
      return { ...device }
    },
    async create(input) {
      const device: DeviceListItemViewModel = {
        deviceId: `device-fixture-${String(sequence++).padStart(3, '0')}`,
        deviceName: input.deviceName,
        enabled: input.enabled,
        enabledStatus: input.enabled ? 'enabled' : 'disabled',
        runtimeStatus: 'unavailable',
        location: input.location || '未设置',
        note: input.note,
        systemDisplay: '—',
        workerVersionDisplay: '未接入',
        currentTaskName: null,
        cpuUsageDisplay: '—',
        memoryUsageDisplay: '—',
        lastHeartbeatAtDisplay: '未接入',
        tags: [],
        capabilities: [],
        updatedAtDisplay: dayjs().format('YYYY-MM-DD HH:mm'),
        dataSource: 'mock',
      }
      rows.unshift(device)
      return { ...device }
    },
    async update(deviceId, input) {
      const index = rows.findIndex((item) => item.deviceId === deviceId)
      if (index < 0) throw new Error('设备不存在')
      const current = rows[index]!
      const updated: DeviceListItemViewModel = {
        ...current,
        deviceName: input.deviceName,
        enabled: input.enabled,
        enabledStatus: input.enabled ? 'enabled' : 'disabled',
        location: input.location || '未设置',
        note: input.note,
        updatedAtDisplay: dayjs().format('YYYY-MM-DD HH:mm'),
      }
      rows[index] = updated
      return { ...updated }
    },
    async setEnabled(deviceId, enabled) {
      const index = rows.findIndex((item) => item.deviceId === deviceId)
      if (index < 0) throw new Error('设备不存在')
      const updated: DeviceListItemViewModel = {
        ...rows[index]!,
        enabled,
        enabledStatus: enabled ? 'enabled' : 'disabled',
        updatedAtDisplay: dayjs().format('YYYY-MM-DD HH:mm'),
      }
      rows[index] = updated
      return { ...updated }
    },
    async remove(deviceId) {
      const index = rows.findIndex((item) => item.deviceId === deviceId)
      if (index < 0) throw new Error('设备不存在')
      if (rows[index]!.currentTaskName) {
        throw new Error('设备存在待执行或执行中的任务，暂时不能移除')
      }
      rows.splice(index, 1)
    },
  }
}

const realDeviceDataSource: DeviceDataSource = {
  mode: 'real',
  supportsFilters: true,
  async list(params) {
    const page = await deviceApi.list({
      ...params,
      search: params.filters.keyword,
    })
    return {
      items: page.items.map(mapDeviceDto),
      total: page.total,
      page: page.page,
      pageSize: page.page_size,
    }
  },
  async get(deviceId) {
    return mapDeviceDto(await deviceApi.get(deviceId))
  },
  async create(input) {
    return mapDeviceDto(await deviceApi.create(mapDeviceCreateInput(input)))
  },
  async update(deviceId, input) {
    return mapDeviceDto(
      await deviceApi.update(deviceId, mapDeviceUpdateInput(input)),
    )
  },
  async setEnabled(deviceId, enabled) {
    return mapDeviceDto(await deviceApi.update(deviceId, { enabled }))
  },
  async remove(deviceId) {
    await deviceApi.remove(deviceId)
  },
}

export function createDeviceDataSource(mode: ApiMode): DeviceDataSource {
  return mode === 'real' ? realDeviceDataSource : createMockDeviceDataSource()
}

export const deviceDataSource = createDeviceDataSource(apiMode)
