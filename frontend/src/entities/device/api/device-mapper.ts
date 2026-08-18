import dayjs from 'dayjs'

import type { DeviceListItemViewModel, DeviceSaveInput } from '../model/types'
import type {
  DeviceCreateDto,
  DeviceReadDto,
  DeviceUpdateDto,
} from './contracts'

function formatDateTime(value: string): string {
  return dayjs(value).format('YYYY-MM-DD HH:mm')
}

export function mapDeviceDto(dto: DeviceReadDto): DeviceListItemViewModel {
  return {
    deviceId: dto.device_id,
    deviceName: dto.display_name,
    enabled: dto.enabled,
    enabledStatus: dto.enabled ? 'enabled' : 'disabled',
    runtimeStatus: 'unavailable',
    location: dto.location || '未设置',
    note: dto.note || '',
    systemDisplay: '—',
    workerVersionDisplay: '未接入',
    currentTaskName: null,
    cpuUsageDisplay: '—',
    memoryUsageDisplay: '—',
    lastHeartbeatAtDisplay: '未接入',
    tags: [],
    capabilities: [],
    updatedAtDisplay: formatDateTime(dto.updated_at),
    dataSource: 'real',
  }
}

export function mapDeviceCreateInput(input: DeviceSaveInput): DeviceCreateDto {
  return {
    display_name: input.deviceName.trim(),
    enabled: input.enabled,
    location: input.location.trim() || null,
    note: input.note.trim() || null,
  }
}

export function mapDeviceUpdateInput(input: DeviceSaveInput): DeviceUpdateDto {
  return mapDeviceCreateInput(input)
}
