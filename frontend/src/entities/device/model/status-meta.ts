import type { StatusTone } from '@/shared/components/StatusTag.vue'

import type { DeviceLocalShopDto } from '../api/contracts'
import type {
  DeviceCapability,
  DeviceCapabilityAvailability,
  DeviceEnabledStatus,
  DeviceRuntimeStatus,
} from './types'

export interface DeviceStatusMeta {
  label: string
  tone: StatusTone
}

export const DEVICE_STATUS_META = {
  online: { label: '在线', tone: 'success' },
  offline: { label: '离线', tone: 'neutral' },
  busy: { label: '忙碌', tone: 'info' },
  error: { label: '异常', tone: 'error' },
  unavailable: { label: '未接入', tone: 'neutral' },
} satisfies Record<DeviceRuntimeStatus, DeviceStatusMeta>

const SHOP_SESSION_STATUS_META = {
  valid: { label: '有效', tone: 'success' },
  invalid: { label: '失效', tone: 'error' },
  reauthorization_required: { label: '未保存', tone: 'warning' },
  unknown: { label: '未确认', tone: 'neutral' },
} satisfies Record<DeviceLocalShopDto['session_status'], DeviceStatusMeta>

export function workerShopSessionStatusMeta(
  status: DeviceLocalShopDto['session_status'], checkedAt?: string | null,
): DeviceStatusMeta {
  return status === 'unknown' && checkedAt
    ? { label: '待复验', tone: 'warning' }
    : SHOP_SESSION_STATUS_META[status]
}

export const DEVICE_ENABLED_STATUS_META = {
  enabled: { label: '已启用', tone: 'success' },
  disabled: { label: '已停用', tone: 'neutral' },
} satisfies Record<DeviceEnabledStatus, DeviceStatusMeta>

export const DEVICE_CAPABILITY_META = {
  rpa: { label: 'RPA' },
  python: { label: 'Python' },
  browser: { label: 'Browser' },
  node: { label: 'Node' },
} satisfies Record<DeviceCapability, { label: string }>

export const DEVICE_CAPABILITY_AVAILABILITY_META = {
  available: { label: '可用', tone: 'success' },
  unavailable: { label: '不可用', tone: 'neutral' },
} satisfies Record<DeviceCapabilityAvailability, DeviceStatusMeta>
