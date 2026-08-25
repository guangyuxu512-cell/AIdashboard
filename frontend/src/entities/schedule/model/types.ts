import type { TaskStatusDto } from '@/entities/task'

import type {
  ScheduleExecutionTypeDto,
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
  shopId: string | null
  deviceName: string
  executionType: ScheduleExecutionTypeDto
  executionTypeDisplay: string
  skillId: string
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
  applicationId: string | null
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
  shopId: string
  executionType: ScheduleExecutionTypeDto
  applicationId: string | null
  skillId: string | null
  parameters: Record<string, unknown>
  scheduleType: ScheduleTypeDto
  localTime: string
  timezone: string
  enabled: boolean
}
