import type { DeviceListItemViewModel } from '@/entities/device'
import type { ActiveTaskSummaryReadDto, TaskReadDto } from '@/entities/task'

import type { DeviceCurrentExecutionViewModel } from './types'

export function resolveDeviceCurrentExecution(
  device: DeviceListItemViewModel,
  activeTask: ActiveTaskSummaryReadDto | null,
  refreshTask: TaskReadDto | null,
): DeviceCurrentExecutionViewModel {
  if (activeTask) {
    const metadata = activeTask.latest_event?.metadata ?? {}
    const eventAppName =
      typeof metadata.app_name === 'string' ? metadata.app_name : null
    const snapshotName = activeTask.execution_display_name?.trim() || null
    const hasGenericYingdaoSnapshot =
      activeTask.skill_id === 'yingdao.app.run' &&
      snapshotName === activeTask.skill_id
    const displayName =
      hasGenericYingdaoSnapshot && eventAppName
        ? eventAppName
        : snapshotName || eventAppName || activeTask.skill_id
    return {
      status: activeTask.status,
      label: activeTask.status === 'pending' ? '待执行' : '执行中',
      name: displayName,
      tone: activeTask.status === 'pending' ? 'warning' : 'info',
      taskId: activeTask.task_id,
      appName: eventAppName,
      latestMessage: activeTask.latest_event?.message ?? null,
      startedAt: activeTask.started_at ?? activeTask.created_at,
    }
  }
  if (
    refreshTask?.target_device_id === device.deviceId &&
    (refreshTask.status === 'pending' || refreshTask.status === 'running')
  ) {
    return {
      status: refreshTask.status,
      label: refreshTask.status === 'pending' ? '待执行' : '执行中',
      name: refreshTask.execution_display_name || refreshTask.skill_id,
      tone: refreshTask.status === 'pending' ? 'warning' : 'info',
      taskId: refreshTask.task_id,
      appName: null,
      latestMessage: null,
      startedAt: refreshTask.started_at ?? refreshTask.created_at,
    }
  }
  if (device.dataSource === 'real') {
    return idle()
  }
  if (device.runtimeStatus === 'busy') {
    return {
      status: 'running',
      label: '执行中',
      name: device.currentTaskName,
      tone: 'info',
      taskId: null,
      appName: null,
      latestMessage: null,
      startedAt: null,
    }
  }
  if (device.currentTaskName) {
    return {
      status: 'pending',
      label: '待执行',
      name: device.currentTaskName,
      tone: 'warning',
      taskId: null,
      appName: null,
      latestMessage: null,
      startedAt: null,
    }
  }
  return idle()
}

function idle(): DeviceCurrentExecutionViewModel {
  return {
    status: 'idle',
    label: '空闲',
    name: null,
    tone: 'neutral',
    taskId: null,
    appName: null,
    latestMessage: null,
    startedAt: null,
  }
}
