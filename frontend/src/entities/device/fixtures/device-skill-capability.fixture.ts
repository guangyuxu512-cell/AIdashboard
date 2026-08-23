import type { DeviceSkillCapabilityViewModel } from '../model/types'

function skill(
  deviceId: string,
  skillId: string,
  displayName: string,
  runtime: DeviceSkillCapabilityViewModel['runtime'],
  provider: string | null = null,
): DeviceSkillCapabilityViewModel {
  return {
    deviceId,
    skillId,
    displayName,
    runtime,
    provider,
    version: '1',
    updatedAtDisplay: '2026-08-23 12:00',
  }
}

function workerSkills(deviceId: string): DeviceSkillCapabilityViewModel[] {
  return [
    skill(deviceId, 'system.echo', '系统回显', 'python'),
    skill(deviceId, 'system.sleep', '系统等待', 'python'),
    skill(deviceId, 'yingdao.app.run', '运行影刀应用', 'rpa', 'yingdao'),
    skill(deviceId, 'yingdao.test', '影刀无副作用测试', 'rpa', 'yingdao'),
    skill(deviceId, 'yingdao.discover', '发现影刀环境', 'discovery', 'yingdao'),
  ]
}

export const DEVICE_SKILL_CAPABILITY_FIXTURE_BY_DEVICE: Record<
  string,
  DeviceSkillCapabilityViewModel[]
> = Object.fromEntries(
  Array.from({ length: 8 }, (_, index) => {
    const deviceId = `device-fixture-${String(index + 1).padStart(3, '0')}`
    return [deviceId, workerSkills(deviceId)]
  }),
)
