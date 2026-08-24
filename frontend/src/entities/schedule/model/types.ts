import type { TaskStatusDto } from '@/entities/task'

import type {
  ScheduleRunTriggerResultDto,
  ScheduleTypeDto,
} from '../api/contracts'

export interface ScheduleRunViewModel {
  runId: string
  scheduledFor: string
  scheduledForDisplay: string
  taskId: string | null
  taskStatus: TaskStatusDto | null
  triggerResult: ScheduleRunTriggerResultDto
  triggerErrorCode: string | null
  triggerErrorMessage: string | null
}

export interface ScheduleListItemViewModel {
  scheduleId: string
  name: string
  enabled: boolean
  deviceId: string
  deviceName: string
  skillId: 'yingdao.app.run'
  executionName: string
  scheduleType: ScheduleTypeDto
  localTime: string
  timezone: string
  triggerRuleDisplay: string
  nextRunAt: string | null
  nextRunAtDisplay: string
  latestRun: ScheduleRunViewModel | null
  createdAt: string
  createdAtDisplay: string
  updatedAt: string
  updatedAtDisplay: string
}

export interface ScheduleDetailViewModel extends ScheduleListItemViewModel {
  applicationId: string
  parameters: Record<string, unknown>
}

export interface ScheduleListFilters {
  enabled: boolean | null
  deviceId: string | null
  search: string
}

export interface ScheduleSaveInput {
  name: string
  deviceId: string
  applicationId: string
  parameters: Record<string, unknown>
  scheduleType: ScheduleTypeDto
  localTime: string
  timezone: string
  enabled: boolean
}
