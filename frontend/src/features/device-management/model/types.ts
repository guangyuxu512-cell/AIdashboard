import type {
  DeviceCapability,
  DeviceListItemViewModel,
  DeviceStatus,
  YingdaoInventoryViewModel,
} from '@/entities/device'
import type { ActiveTaskSummaryReadDto } from '@/entities/task'
import type { StatusTone } from '@/shared/components/StatusTag.vue'

export interface DeviceFilterViewModel {
  status: DeviceStatus | null
  tag: string | null
  workerVersion: string | null
  capability: DeviceCapability | null
  keyword: string
}

export interface DeviceFormViewModel {
  deviceName: string
  enabled: boolean
  location: string
  note: string
}

export type DeviceFormMode = 'create' | 'edit'

export type DeviceCurrentExecutionStatus =
  'idle' | 'pending' | 'running' | 'unknown'

export interface DeviceCurrentExecutionViewModel {
  status: DeviceCurrentExecutionStatus
  label: string
  name: string | null
  tone: StatusTone
  taskId: string | null
  appName: string | null
  latestMessage: string | null
  startedAt: string | null
}

export interface DeviceManagementRowViewModel extends DeviceListItemViewModel {
  currentExecution: DeviceCurrentExecutionViewModel
  yingdaoInventory: YingdaoInventoryViewModel | null
  boundShopCount: number | null
  activeTask: ActiveTaskSummaryReadDto | null
}

export type DeviceRecentExecutionStatus = 'success' | 'failed' | 'lost'

export interface DeviceRecentExecutionViewModel {
  id: string
  name: string
  status: DeviceRecentExecutionStatus
  statusLabel: string
  tone: StatusTone
  timeDisplay: string
}
