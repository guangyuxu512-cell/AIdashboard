import type { PageDto } from '@/shared/api'

import type {
  DeviceReadDto,
  DeviceSkillCapabilityReadDto,
} from '../api/contracts'
import type { Device, DeviceCapabilitySummary } from './types'

export function mapDeviceRead(dto: DeviceReadDto): Device {
  return {
    deviceId: dto.device_id,
    displayName: dto.display_name,
    enabled: dto.enabled,
    location: dto.location,
    note: dto.note,
    deletedAt: dto.deleted_at,
    workerRuntime: dto.worker_runtime
      ? {
          deviceId: dto.worker_runtime.device_id,
          workerVersion: dto.worker_runtime.worker_version,
          connectionStatus: dto.worker_runtime.connection_status,
          lastSeenAt: dto.worker_runtime.last_seen_at,
          startedAt: dto.worker_runtime.started_at,
          updatedAt: dto.worker_runtime.updated_at,
        }
      : null,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  }
}

export function flattenDevicePages(
  pages: readonly PageDto<DeviceReadDto>[],
): Device[] {
  const seen = new Set<string>()
  const devices: Device[] = []

  for (const page of pages) {
    for (const dto of page.items) {
      if (seen.has(dto.device_id)) continue
      seen.add(dto.device_id)
      devices.push(mapDeviceRead(dto))
    }
  }

  return devices
}

export function summarizeDeviceCapabilities(
  capabilities: readonly DeviceSkillCapabilityReadDto[],
): DeviceCapabilitySummary {
  const summary: DeviceCapabilitySummary = {
    business: 0,
    internal: 0,
    unclassified: 0,
    total: capabilities.length,
  }

  for (const capability of capabilities) {
    if (capability.classification === 'business') summary.business += 1
    else if (capability.classification === 'internal') summary.internal += 1
    else summary.unclassified += 1
  }

  return summary
}
