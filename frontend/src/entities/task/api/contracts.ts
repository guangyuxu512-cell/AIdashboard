export type TaskStatusDto =
  'pending' | 'running' | 'success' | 'failed' | 'lost'

export interface TaskReadDto {
  task_id: string
  target_device_id: string
  shop_ids: string[]
  asset_ids: string[]
  skill_id: string
  execution_display_name: string
  status: TaskStatusDto
  input: Record<string, unknown>
  result: Record<string, unknown> | null
  error_code: string | null
  error_message: string | null
  lease_until: string | null
  started_at: string | null
  finished_at: string | null
  runtime_events_purged_at: string | null
  created_at: string
  updated_at: string
}

export interface TaskCreateDto {
  target_device_id: string
  shop_ids?: string[]
  asset_ids?: string[]
  parameter_preset_id?: string
  skill_id: TaskReadDto['skill_id']
  input: Record<string, unknown>
}

export type TaskEventTypeDto =
  'status' | 'log' | 'progress' | 'completed' | 'failed'

export interface TaskEventReadDto {
  event_id: string
  task_id: string
  seq: number
  event_type: TaskEventTypeDto
  level: string
  message: string
  event_at: string
  metadata: Record<string, unknown>
  created_at: string
}

export interface TaskEventListReadDto {
  task_id: string
  after_seq: number | null
  before_seq: number | null
  next_after_seq: number
  next_before_seq: number | null
  has_more_before: boolean
  items: TaskEventReadDto[]
}

export interface ActiveTaskSummaryReadDto {
  task_id: string
  target_device_id: string
  skill_id: TaskReadDto['skill_id']
  execution_display_name: string
  status: 'pending' | 'running'
  started_at: string | null
  created_at: string
  latest_event: TaskEventReadDto | null
}

export interface TaskProgressSummaryReadDto {
  current: number
  total: number | null
}

export interface TaskListItemReadDto {
  task_id: string
  target_device_id: string
  device_display_name: string
  skill_id: TaskReadDto['skill_id']
  skill_display_name: string | null
  execution_display_name: string
  status: TaskStatusDto
  progress: TaskProgressSummaryReadDto | null
  current_message: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
}
