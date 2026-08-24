import type { TaskStatusDto } from '@/entities/task'

export type ScheduleTypeDto = 'daily'
export type ScheduleRunTriggerResultDto = 'task_created' | 'blocked'

export interface ScheduleRunReadDto {
  run_id: string
  schedule_id: string
  scheduled_for: string
  task_id: string | null
  task_status: TaskStatusDto | null
  trigger_result: ScheduleRunTriggerResultDto
  trigger_error_code: string | null
  trigger_error_message: string | null
  created_at: string
}

export interface ScheduleListItemReadDto {
  schedule_id: string
  name: string
  enabled: boolean
  target_device_id: string
  device_display_name: string
  skill_id: 'yingdao.app.run'
  execution_display_name: string
  schedule_type: ScheduleTypeDto
  local_time: string
  timezone: string
  next_run_at: string | null
  latest_run: ScheduleRunReadDto | null
  created_at: string
  updated_at: string
}

export interface ScheduleReadDto extends ScheduleListItemReadDto {
  application_id: string
  parameters: Record<string, unknown>
}

export interface ScheduleCreateDto {
  name: string
  target_device_id: string
  application_id: string
  parameters: Record<string, unknown>
  schedule_type: ScheduleTypeDto
  local_time: string
  timezone: string
  enabled: boolean
}

export type ScheduleUpdateDto = Partial<ScheduleCreateDto>
