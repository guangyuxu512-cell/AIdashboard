import { describe, expect, it } from 'vitest'

import {
  getAuditActionLabel,
  getAuditSummary,
  getAuditTargetLabel,
  type AuditLogViewModel,
} from './types'

describe('application Session audit', () => {
  it('labels the application access and its authorizer', () => {
    const row: AuditLogViewModel = {
      auditLogId: 'audit-1',
      requestId: 'request-1',
      actorUserId: 'user-1',
      actorDisplayName: '管理员',
      teamId: null,
      action: 'application.read_shop_session',
      targetType: 'shop_session',
      targetId: '12345678-1234-1234-1234-123456789abc',
      details: { actor_kind: 'application', application_id: 'product-library' },
      createdAt: '2026-10-31T00:00:00Z',
    }
    expect(getAuditActionLabel(row.action)).toBe('软件读取店铺会话')
    expect(getAuditTargetLabel(row)).toBe('店铺会话 · 12345678')
    expect(getAuditSummary(row)).toBe('授权人：管理员')
  })
})
