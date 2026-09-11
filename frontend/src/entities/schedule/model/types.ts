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
  shopIds: string[]
  deviceName: string
  executionType: ScheduleExecutionTypeDto
  executionTypeDisplay: string
  skillId: string
  executionName: string
  scheduleType: ScheduleTypeDto
  localTime: string
  timezone: string
  localDate: string | null
  weekdays: number[]
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
  parameterPresetId: string | null
  parameters: Record<string, unknown>
}

export interface ScheduleListFilters {
  enabled: boolean | null
  deviceId: string | null
  search: string
  occurrenceDate: string | null
  viewTimezone: string | null
}

export interface ScheduleSaveInput {
  name: string
  deviceId: string
  shopIds: string[]
  executionType: ScheduleExecutionTypeDto
  applicationId: string | null
  parameterPresetId: string | null
  skillId: string | null
  parameters: Record<string, unknown>
  scheduleType: ScheduleTypeDto
  localTime: string
  timezone: string
  localDate: string | null
  weekdays: number[]
  enabled: boolean
}
