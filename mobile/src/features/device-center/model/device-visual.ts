import {
  DEVICE_CONNECTION_DISPLAY_META,
  getDeviceConnectionDisplayState,
  type Device,
  type DeviceArtworkState,
} from '@/entities/device'

import type { DeviceActiveTaskState } from './use-device-active-task'

export const DEVICE_VISUAL_STATE_LABELS = {
  online: '在线',
  running: '运行中',
  offline: '离线',
} as const satisfies Record<DeviceArtworkState, string>

export function getDeviceVisualState(
  device: Device,
  activeTaskState: DeviceActiveTaskState,
): DeviceArtworkState {
  const connectionStatus = device.workerRuntime?.connectionStatus
  if (connectionStatus === 'offline') return 'offline'
  if (
    connectionStatus === 'online' &&
    activeTaskState.hasSuccessfulData &&
    activeTaskState.task?.status === 'running'
  ) {
    return 'running'
  }
  if (connectionStatus === 'online') return 'online'

  // Frozen Artwork 只有三态；Runtime 缺失仅使用离线插画 fallback，文字由独立连接展示态表达为“未连接”。
  return 'offline'
}

export function getDeviceRuntimeDisplayLabel(
  device: Device,
  activeTaskState: DeviceActiveTaskState,
): string {
  const visualState = getDeviceVisualState(device, activeTaskState)
  if (visualState === 'running') return DEVICE_VISUAL_STATE_LABELS.running

  return DEVICE_CONNECTION_DISPLAY_META[
    getDeviceConnectionDisplayState(device.workerRuntime?.connectionStatus)
  ].label
}
