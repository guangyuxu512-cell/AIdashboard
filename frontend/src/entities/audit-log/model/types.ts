export type AuditAction =
  | 'product_selection.block_candidate'
  | 'product_selection.restore_candidate'
  | 'access_management.create_member'
  | 'access_management.update_member'
  | 'access_management.reset_member_password'
  | 'access_management.create_membership'
  | 'access_management.update_membership'
  | 'access_management.create_team'
  | 'access_management.update_team'

export type AuditTargetType =
  'user' | 'membership' | 'team' | 'selection_candidate'

export interface AuditLogViewModel {
  auditLogId: string
  requestId: string
  actorUserId: string
  actorDisplayName: string
  teamId: string
  action: AuditAction
  targetType: AuditTargetType
  targetId: string
  details: Record<string, unknown> | null
  createdAt: string
}

const ACTION_LABELS: Record<AuditAction, string> = {
  'product_selection.block_candidate': '屏蔽候选商品',
  'product_selection.restore_candidate': '恢复候选商品',
  'access_management.create_member': '创建员工',
  'access_management.update_member': '更新员工状态',
  'access_management.reset_member_password': '重置密码',
  'access_management.create_membership': '新增成员关系',
  'access_management.update_membership': '更新成员权限',
  'access_management.create_team': '创建团队',
  'access_management.update_team': '更新团队',
}

const TARGET_LABELS: Record<AuditTargetType, string> = {
  selection_candidate: '候选商品',
  user: '员工',
  membership: '成员关系',
  team: '团队',
}

const CHANGE_LABELS: Record<string, string> = {
  enabled: '状态',
  role_code: '角色',
  data_scope: '数据范围',
  module_codes: '模块权限',
  name: '名称',
}

function valueLabel(value: unknown): string {
  if (value === true) return '启用'
  if (value === false) return '停用'
  if (value === 'self') return '仅自己'
  if (value === 'team') return '本团队'
  if (value === 'all') return '全部'
  return String(value)
}

export function getAuditActionLabel(action: AuditAction): string {
  return ACTION_LABELS[action]
}

export function getAuditTargetLabel(log: AuditLogViewModel): string {
  return `${TARGET_LABELS[log.targetType]} · ${log.targetId.slice(0, 8)}`
}

export function getAuditSummary(log: AuditLogViewModel): string {
  if (log.action === 'access_management.reset_member_password') {
    return '已重置密码'
  }
  const changes = log.details?.changes
  if (!changes || typeof changes !== 'object' || Array.isArray(changes)) {
    return '已完成'
  }
  const entries = Object.entries(changes as Record<string, unknown>)
  if (!entries.length) return '已完成'
  return entries
    .map(([field, change]) => {
      const label = CHANGE_LABELS[field] ?? field
      if (
        change &&
        typeof change === 'object' &&
        'from' in change &&
        'to' in change
      ) {
        const values = change as { from: unknown; to: unknown }
        return `${label}：${valueLabel(values.from)} → ${valueLabel(values.to)}`
      }
      return `${label}已更新`
    })
    .join('；')
}
