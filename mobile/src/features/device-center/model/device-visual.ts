import type { Device, DeviceArtworkState } from '@/entities/device'

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

  // Backend 当前允许 Runtime 为空，但没有第四种公开设备状态；视觉层安全降级为离线。
  return 'offline'
}
