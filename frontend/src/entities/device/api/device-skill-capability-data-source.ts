import { apiMode } from '@/shared/api'

import { DEVICE_SKILL_CAPABILITY_FIXTURE_BY_DEVICE } from '../fixtures/device-skill-capability.fixture'
import type { DeviceSkillCapabilityViewModel } from '../model/types'
import { deviceApi } from './device-api'
import { mapDeviceSkillCapabilityDto } from './device-mapper'

export async function getDeviceSkillCapabilities(
  deviceId: string,
): Promise<DeviceSkillCapabilityViewModel[]> {
  if (apiMode === 'mock') {
    return DEVICE_SKILL_CAPABILITY_FIXTURE_BY_DEVICE[deviceId] ?? []
  }
  return (await deviceApi.getSkillCapabilities(deviceId)).map(
    mapDeviceSkillCapabilityDto,
  )
}
