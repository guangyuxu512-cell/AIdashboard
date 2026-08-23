import type {
  DeviceListItemViewModel,
  DeviceSkillCapabilityViewModel,
  ProviderApplicationViewModel,
  YingdaoInventoryViewModel,
} from '@/entities/device'
export {
  hasResolvedQueryData,
  isInitialQueryError,
  isInitialQueryLoading,
} from '@/shared/api/query-state'

export interface YingdaoApplicationRunAvailabilityInput {
  device: DeviceListItemViewModel | null
  skills: DeviceSkillCapabilityViewModel[]
  skillsLoading?: boolean
  skillsError?: string | null
  inventory: YingdaoInventoryViewModel | null
  providerLoading?: boolean
  providerError?: string | null
  application?: ProviderApplicationViewModel
}

export interface YingdaoApplicationRunAvailability {
  enabled: boolean
  disabledReason: string | null
}

export function resolveYingdaoApplicationRunAvailability(
  input: YingdaoApplicationRunAvailabilityInput,
): YingdaoApplicationRunAvailability {
  const reason = resolveDisabledReason(input)
  return { enabled: reason === null, disabledReason: reason }
}

function resolveDisabledReason(
  input: YingdaoApplicationRunAvailabilityInput,
): string | null {
  if (!input.device) return '当前未选择目标设备'
  if (!input.device.enabled) return '设备已停用'
  if (!['online', 'busy'].includes(input.device.runtimeStatus)) {
    return '设备当前离线'
  }
  if (input.skillsLoading && input.skills.length === 0) {
    return '正在读取设备 Skill 能力'
  }
  if (input.skillsError && input.skills.length === 0) {
    return '设备 Skill 能力读取失败'
  }
  if (!input.skills.some((skill) => skill.skillId === 'yingdao.app.run')) {
    return '当前 Worker 未声明 yingdao.app.run Skill'
  }
  if (input.providerLoading && !input.inventory) {
    return '正在读取影刀 Provider 状态'
  }
  if (input.providerError && !input.inventory) {
    return '影刀 Provider 状态读取失败'
  }
  if (!input.inventory) return '尚未获取影刀 Provider 状态'
  if (input.inventory.providerStatus === 'not_installed') {
    return '未检测到影刀 6.3.6'
  }
  if (input.inventory.providerStatus === 'version_unsupported') {
    return '影刀版本不受支持，当前仅支持 6.3.6'
  }
  if (input.inventory.providerStatus === 'starting') {
    return '影刀 6.3.6 正在启动'
  }
  if (input.inventory.providerStatus === 'need_login') {
    return '影刀 6.3.6 当前需要登录'
  }
  if (input.inventory.providerStatus === 'interface_unreachable') {
    return '影刀本地接口当前不可用'
  }
  if (input.inventory.providerStatus !== 'ready') {
    return input.inventory.statusReason || '影刀 Provider 尚未就绪'
  }
  if (input.inventory.providerVersion !== '6.3.6') {
    return '影刀版本不受支持，当前仅支持 6.3.6'
  }
  if (!input.inventory.loggedIn) {
    return '影刀 6.3.6 当前需要登录'
  }
  if (!input.inventory.executionAvailable) {
    return input.inventory.executionUnavailableReason || '影刀执行能力当前不可用'
  }
  if (
    input.application &&
    (!input.application.appId.trim() || !input.application.appName.trim())
  ) {
    return '当前 Application 不可用'
  }
  return null
}
