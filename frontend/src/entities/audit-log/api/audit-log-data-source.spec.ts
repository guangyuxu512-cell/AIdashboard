import { afterEach, describe, expect, it, vi } from 'vitest'

import { httpClient } from '@/shared/api'

import { createAuditLogDataSource } from './audit-log-data-source'

describe('Audit Log Data Source', () => {
  afterEach(() => vi.restoreAllMocks())

  it('maps the paginated audit-log contract in real mode', async () => {
    const get = vi.spyOn(httpClient, 'get').mockResolvedValue({
      data: {
        items: [
          {
            audit_log_id: 'log-1',
            request_id: 'request-1',
            actor_user_id: 'user-1',
            actor_display_name: '管理员',
            team_id: 'team-1',
            action: 'access_management.update_membership',
            target_type: 'membership',
            target_id: 'membership-1',
            details: {
              changes: { data_scope: { from: 'team', to: 'self' } },
            },
            created_at: '2026-09-04T08:00:00Z',
          },
        ],
        total: 1,
        page: 2,
        page_size: 10,
      },
    })
    const source = createAuditLogDataSource('real')

    await expect(
      source.list({
        page: 2,
        pageSize: 10,
        action: 'access_management.update_membership',
      }),
    ).resolves.toEqual({
      items: [
        {
          auditLogId: 'log-1',
          requestId: 'request-1',
          actorUserId: 'user-1',
          actorDisplayName: '管理员',
          teamId: 'team-1',
          action: 'access_management.update_membership',
          targetType: 'membership',
          targetId: 'membership-1',
          details: {
            changes: { data_scope: { from: 'team', to: 'self' } },
          },
          createdAt: '2026-09-04T08:00:00Z',
        },
      ],
      total: 1,
      page: 2,
      pageSize: 10,
    })
    expect(get).toHaveBeenCalledWith(
      '/api/v1/access-management/audit-logs',
      {
        params: {
          page: 2,
          page_size: 10,
          created_from: undefined,
          created_to: undefined,
          actor_user_id: undefined,
          action: 'access_management.update_membership',
        },
      },
    )
  })

  it('uses an empty real-contract-compatible list in mock mode', async () => {
    const source = createAuditLogDataSource('mock')

    await expect(source.list({ page: 1, pageSize: 20 })).resolves.toEqual({
      items: [],
      total: 0,
      page: 1,
      pageSize: 20,
    })
  })
})
