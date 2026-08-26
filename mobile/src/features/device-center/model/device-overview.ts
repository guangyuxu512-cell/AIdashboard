import type { Device } from '@/entities/device'

import type { DeviceActiveTaskState } from './use-device-active-task'

export type DeviceOverviewActiveState =
  'loading' | 'error' | 'partial' | 'ready'
export type DeviceOverviewDataState = 'loading' | 'error' | 'ready'

export interface DeviceOverview {
  dataState: DeviceOverviewDataState
  loadedCount: number
  onlineCount: number | null
  offlineCount: number | null
  unreportedCount: number | null
  runningCount: number | null
  activeConfirmedCount: number
  activeUnknownCount: number
  activeBackgroundErrorCount: number
  activeInitialErrorCount: number
  activeState: DeviceOverviewActiveState
}

export function summarizeDeviceOverview(
  devices: readonly Device[],
  activeTaskStates: Readonly<Record<string, DeviceActiveTaskState>>,
  dataState: DeviceOverviewDataState,
  totalCount: number = devices.length,
): DeviceOverview {
  if (dataState !== 'ready') {
    return {
      dataState,
      loadedCount: 0,
      onlineCount: null,
      offlineCount: null,
      unreportedCount: null,
      runningCount: null,
      activeConfirmedCount: 0,
      activeUnknownCount: 0,
      activeBackgroundErrorCount: 0,
      activeInitialErrorCount: 0,
      activeState: dataState,
    }
  }

  const loadedCount = devices.length
  if (loadedCount < totalCount) {
    return {
      dataState: 'ready',
      loadedCount,
      onlineCount: null,
      offlineCount: null,
      unreportedCount: null,
      runningCount: null,
      activeConfirmedCount: 0,
      activeUnknownCount: totalCount,
      activeBackgroundErrorCount: 0,
      activeInitialErrorCount: 0,
      activeState: 'partial',
    }
  }

  let onlineCount = 0
  let offlineCount = 0
  let unreportedCount = 0
  let runningCount = 0
  let activeConfirmedCount = 0
  let activeBackgroundErrorCount = 0
  let activeInitialErrorCount = 0

  for (const device of devices) {
    const connectionStatus = device.workerRuntime?.connectionStatus
    if (connectionStatus === 'online') onlineCount += 1
    else if (connectionStatus === 'offline') offlineCount += 1
    else unreportedCount += 1

    const activeTaskState = activeTaskStates[device.deviceId]
    if (!activeTaskState) continue
    if (activeTaskState.hasSuccessfulData) {
      activeConfirmedCount += 1
      if (activeTaskState.task?.status === 'running') runningCount += 1
    }
    if (activeTaskState.backgroundError) activeBackgroundErrorCount += 1
    if (activeTaskState.initialError) activeInitialErrorCount += 1
  }

  const activeUnknownCount = loadedCount - activeConfirmedCount
  const activeState: DeviceOverviewActiveState =
    activeUnknownCount === 0
      ? 'ready'
      : activeConfirmedCount > 0
        ? 'partial'
        : activeInitialErrorCount > 0
          ? 'error'
          : 'loading'
  return {
    dataState: 'ready',
    loadedCount,
    onlineCount,
    offlineCount,
    unreportedCount,
    runningCount: activeUnknownCount === 0 ? runningCount : null,
    activeConfirmedCount,
    activeUnknownCount,
    activeBackgroundErrorCount,
    activeInitialErrorCount,
    activeState,
  }
}
