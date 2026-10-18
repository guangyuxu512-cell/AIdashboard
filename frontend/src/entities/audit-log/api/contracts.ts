import type { AuditAction, AuditTargetType } from '../model/types'

export interface AuditLogReadDto {
  audit_log_id: string
  request_id: string
  actor_user_id: string
  actor_display_name: string
  team_id: string | null
  action: AuditAction
  target_type: AuditTargetType
  target_id: string
  details: Record<string, unknown> | null
  created_at: string
}
