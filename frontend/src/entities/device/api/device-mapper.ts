import dayjs from 'dayjs'

import type {
  DeviceListItemViewModel,
  DeviceSaveInput,
  DeviceSkillCapabilityViewModel,
  YingdaoInventoryViewModel,
} from '../model/types'
import { formatRelativeTime } from '../model/display'
import type {
  DeviceCreateDto,
  DeviceProviderInventoryReadDto,
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

export function mapYingdaoInventoryDto(
  dto: DeviceProviderInventoryReadDto,
): YingdaoInventoryViewModel {
  return {
    available: dto.available,
    availabilityStatus: dto.available ? 'available' : 'unavailable',
    providerStatus: dto.inventory.status,
    statusReason: dto.inventory.status_reason,
    providerVersion: dto.provider_version ?? '未知',
    executionAvailable: dto.inventory.execution_available ?? false,
    executionVersion: dto.inventory.execution_version ?? '—',
    executionUnavailableReason:
      dto.inventory.execution_unavailable_reason ?? null,
    loggedIn: dto.inventory.logged_in,
    accountDisplay: dto.account_display ?? '未知',
    accountType: dto.account_type ?? '未知',
    enterpriseAccount: dto.enterprise_account ?? false,
    applicationCount: dto.inventory.applications.length,
    applications: dto.inventory.applications.map((application) => ({
      appId: application.app_id,
      appName: application.app_name,
      versionId: application.version_id,
    })),
    lastDiscoveredAtDisplay: formatDateTime(dto.last_discovered_at),
  }
}

export function mapDeviceSkillCapabilityDto(
  dto: DeviceSkillCapabilityReadDto,
): DeviceSkillCapabilityViewModel {
  return {
    deviceId: dto.device_id,
    skillId: dto.skill_id,
    displayName: dto.display_name,
    runtime: dto.runtime,
    provider: dto.provider,
    version: dto.version,
    classification: dto.classification,
    updatedAtDisplay: formatDateTime(dto.updated_at),
  }
}
