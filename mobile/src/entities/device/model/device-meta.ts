import type {
  DeviceConnectionStatusDto,
  YingdaoProviderStatusDto,
} from '../api/contracts'

type DeviceTagType = 'primary' | 'success' | 'danger' | 'warning' | 'default'

export type DeviceConnectionDisplayState = DeviceConnectionStatusDto

export const DEVICE_CONNECTION_META = {
  online: { label: '在线', tagType: 'success' },
  offline: { label: '离线', tagType: 'danger' },
} as const satisfies Record<
  DeviceConnectionDisplayState,
  { label: string; tagType: DeviceTagType }
>

export const DEVICE_ENABLED_META = {
  enabled: { label: '已启用', tagType: 'primary' },
  disabled: { label: '已停用', tagType: 'warning' },
} as const satisfies Record<
  'enabled' | 'disabled',
  { label: string; tagType: DeviceTagType }
>

export const YINGDAO_PROVIDER_STATUS_META = {
  not_installed: { label: '未安装', tagType: 'default' },
  version_unsupported: { label: '版本不支持', tagType: 'warning' },
  starting: { label: '启动中', tagType: 'primary' },
  need_login: { label: '需要登录', tagType: 'warning' },
  interface_unreachable: { label: '接口不可达', tagType: 'danger' },
  ready: { label: '就绪', tagType: 'success' },
} as const satisfies Record<
  YingdaoProviderStatusDto,
  { label: string; tagType: DeviceTagType }
>

export function getDeviceConnectionDisplayState(
  connectionStatus: DeviceConnectionStatusDto | null | undefined,
): DeviceConnectionDisplayState {
  // Contract 没有公开 unknown/unreported 状态；缺失连接事实时使用安全离线展示。
  return connectionStatus ?? 'offline'
}
