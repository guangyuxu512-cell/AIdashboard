import { apiMode, type ApiMode, type PageResult } from '@/shared/api'

import type { AuditLogViewModel } from '../model/types'
import { auditLogApi, type AuditLogApiParams } from './audit-log-api'
import type { AuditLogReadDto } from './contracts'

export type AuditLogListParams = AuditLogApiParams

export interface AuditLogDataSource {
  readonly mode: ApiMode
  list(params: AuditLogListParams): Promise<PageResult<AuditLogViewModel>>
}

function mapAuditLog(dto: AuditLogReadDto): AuditLogViewModel {
  return {
    auditLogId: dto.audit_log_id,
    requestId: dto.request_id,
    actorUserId: dto.actor_user_id,
    actorDisplayName: dto.actor_display_name,
    teamId: dto.team_id,
    action: dto.action,
    targetType: dto.target_type,
    targetId: dto.target_id,
    details: dto.details,
    createdAt: dto.created_at,
  }
}

function createMockDataSource(): AuditLogDataSource {
  return {
    mode: 'mock',
    async list(params) {
      return {
        items: [],
        total: 0,
        page: params.page,
        pageSize: params.pageSize,
      }
    },
  }
}

const realDataSource: AuditLogDataSource = {
  mode: 'real',
  async list(params) {
    const page = await auditLogApi.list(params)
    return {
      items: page.items.map(mapAuditLog),
      total: page.total,
      page: page.page,
      pageSize: page.page_size,
    }
  },
}

export function createAuditLogDataSource(mode: ApiMode): AuditLogDataSource {
  return mode === 'real' ? realDataSource : createMockDataSource()
}

export const auditLogDataSource = createAuditLogDataSource(apiMode)
