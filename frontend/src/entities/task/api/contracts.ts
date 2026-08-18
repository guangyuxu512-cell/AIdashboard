export type TaskStatusDto =
  | 'pending'
  | 'running'
  | 'success'
  | 'failed'
  | 'lost'

export interface TaskReadDto {
  task_id: string
  target_device_id: string
  skill_id:
    | 'system.echo'
    | 'system.sleep'
    | 'yingdao.test'
    | 'yingdao.discover'
  status: TaskStatusDto
  input: Record<string, unknown>
  result: Record<string, unknown> | null
  error_code: string | null
  error_message: string | null
  lease_until: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
  updated_at: string
}

export interface TaskCreateDto {
  target_device_id: string
  skill_id: TaskReadDto['skill_id']
  input: Record<string, unknown>
}
