import type { StatusTone } from '@/shared/components/StatusTag.vue'

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
