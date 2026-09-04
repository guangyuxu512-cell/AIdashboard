import { httpClient, type PageDto, type PageParams } from '@/shared/api'

import type { AuditAction } from '../model/types'
import type { AuditLogReadDto } from './contracts'

const basePath = '/api/v1/access-management/audit-logs'

export interface AuditLogApiParams extends PageParams {
  createdFrom?: string
  createdTo?: string
  actorUserId?: string
  action?: AuditAction
}

export const auditLogApi = {
  async list(
    params: AuditLogApiParams,
  ): Promise<PageDto<AuditLogReadDto>> {
    const response = await httpClient.get<PageDto<AuditLogReadDto>>(basePath, {
      params: {
        page: params.page,
        page_size: params.pageSize,
        created_from: params.createdFrom,
        created_to: params.createdTo,
        actor_user_id: params.actorUserId,
        action: params.action,
      },
    })
    return response.data
  },
}
