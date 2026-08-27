import type { Device } from '@/entities/device'

import type { DeviceOverview } from './device-overview'
import type { DeviceActiveTaskState } from './use-device-active-task'

export const DEVICE_QUICK_FILTERS = [
  { value: 'all', label: '全部' },
  { value: 'online', label: '在线设备' },
  { value: 'running', label: '运行中' },
  { value: 'offline', label: '离线设备' },
] as const

export type DeviceQuickFilter = (typeof DEVICE_QUICK_FILTERS)[number]['value']
export type DeviceMetricFilter = Exclude<DeviceQuickFilter, 'all'>

export function getDeviceQuickFilterLabel(filter: DeviceQuickFilter): string {
  return (
    DEVICE_QUICK_FILTERS.find((option) => option.value === filter)?.label ??
    '全部'
  )
}

export function isDeviceQuickFilterAvailable(
  filter: DeviceQuickFilter,
  overview: DeviceOverview,
): boolean {
  if (filter === 'all') return true
  if (filter === 'online') return overview.onlineCount !== null
  if (filter === 'offline') return overview.offlineCount !== null
  return overview.runningCount !== null
}

export function toggleDeviceMetricFilter(
  current: DeviceQuickFilter,
  selected: DeviceMetricFilter,
): DeviceQuickFilter {
  return current === selected ? 'all' : selected
}

export function filterDevicesByQuickFilter(
  devices: readonly Device[],
  activeTaskStates: Readonly<Record<string, DeviceActiveTaskState>>,
  filter: DeviceQuickFilter,
): Device[] {
  if (filter === 'all') return [...devices]
  if (filter === 'online') {
    return devices.filter(
      (device) => device.workerRuntime?.connectionStatus === 'online',
    )
  }
  if (filter === 'offline') {
    return devices.filter(
      (device) => device.workerRuntime?.connectionStatus === 'offline',
    )
  }
  return devices.filter((device) => {
    const activeTaskState = activeTaskStates[device.deviceId]
    return (
      activeTaskState?.hasSuccessfulData === true &&
      activeTaskState.task?.status === 'running'
    )
  })
}
