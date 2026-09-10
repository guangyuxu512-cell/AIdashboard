import type { Device } from '@/entities/device'

import type { DeviceOverview } from './device-overview'
import type { DeviceActiveTaskState } from './use-device-active-task'

export const DEVICE_QUICK_FILTERS = [
  { value: 'all', label: '全部', selectorLabel: '全部' },
  { value: 'online', label: '在线设备', selectorLabel: '在线' },
  { value: 'running', label: '运行中', selectorLabel: '运行中' },
  { value: 'offline', label: '离线设备', selectorLabel: '离线' },
] as const

export type DeviceQuickFilter = (typeof DEVICE_QUICK_FILTERS)[number]['value']
export type DeviceMetricFilter = DeviceQuickFilter

export function getDeviceQuickFilterLabel(filter: DeviceQuickFilter): string {
  return (
    DEVICE_QUICK_FILTERS.find((option) => option.value === filter)
      ?.selectorLabel ?? '全部'
  )
}

export function isDeviceQuickFilterAvailable(
  filter: DeviceQuickFilter,
  overview: DeviceOverview,
): boolean {
  if (filter === 'all') return true
  return overview.dataState === 'ready'
}

export function toggleDeviceMetricFilter(
  current: DeviceQuickFilter,
  selected: DeviceMetricFilter,
): DeviceQuickFilter {
  if (selected === 'all') return 'all'
  return current === selected ? 'all' : selected
}

export function searchDevicesByDisplayName(
  devices: readonly Device[],
  searchQuery: string,
): Device[] {
  const normalizedQuery = searchQuery.trim().toLocaleLowerCase()
  if (!normalizedQuery) return [...devices]

  return devices.filter((device) =>
    device.displayName.toLocaleLowerCase().includes(normalizedQuery),
  )
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
    if (device.workerRuntime?.connectionStatus !== 'online') return false
    const activeTaskState = activeTaskStates[device.deviceId]
    return (
      activeTaskState?.hasSuccessfulData === true &&
      activeTaskState.task?.status === 'running'
    )
  })
}
