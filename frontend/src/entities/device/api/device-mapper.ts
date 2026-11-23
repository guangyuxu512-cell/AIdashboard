import dayjs from 'dayjs'

import { formatSkillName } from '@/entities/business-skill/model/display'

import type {
  DeviceListItemViewModel,
  DeviceSaveInput,
  DeviceSkillCapabilityViewModel,
} from '../model/types'
import { formatRelativeTime } from '../model/display'
import type {
  DeviceCreateDto,
  DeviceReadDto,
  DeviceSkillCapabilityReadDto,
  DeviceUpdateDto,
} from './contracts'

function formatDateTime(value: string): string {
  return dayjs(value).format('YYYY-MM-DD HH:mm')
}

export function mapDeviceDto(dto: DeviceReadDto): DeviceListItemViewModel {
  const runtime = dto.worker_runtime
  return {
    deviceId: dto.device_id,
    deviceName: dto.display_name,
    enabled: dto.enabled,
    enabledStatus: dto.enabled ? 'enabled' : 'disabled',
    runtimeStatus: runtime?.connection_status ?? 'unavailable',
    location: dto.location || '未设置',
    note: dto.note || '',
    systemDisplay: '—',
    workerVersionDisplay: runtime?.worker_version ?? '未接入',
    currentTaskName: null,
    cpuUsageDisplay: '—',
    memoryUsageDisplay: '—',
    lastHeartbeatAtDisplay: runtime
      ? formatRelativeTime(runtime.last_seen_at)
      : '—',
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

export function mapDeviceSkillCapabilityDto(
  dto: DeviceSkillCapabilityReadDto,
): DeviceSkillCapabilityViewModel {
  return {
    deviceId: dto.device_id,
    skillId: dto.skill_id,
    displayName: formatSkillName(dto.skill_id, dto.display_name),
    runtime: dto.runtime,
    provider: dto.provider,
    version: dto.version,
    classification: dto.classification,
    inputSchema: dto.input_schema,
    updatedAtDisplay: formatDateTime(dto.updated_at),
  }
}
