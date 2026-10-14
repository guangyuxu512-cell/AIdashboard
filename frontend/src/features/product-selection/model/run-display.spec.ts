import { describe, it, expect } from 'vitest'
import { runWindow, runResult, triggerFailure } from './run-display'
import type { SelectionExecutionSummary } from './contracts'

const run: SelectionExecutionSummary = {
  run_id: 'r',
  request_shop_id: 's',
  status: 'succeeded',
  result_count: 0,
  saved_count: 0,
  supplement_failed_count: 0,
  error_code: null,
  request_conditions: {
    version: 2,
    scope: {
      begin_date: '2026/10/04 00:00:00',
      end_date: '2026/10/10 00:00:00',
    },
    date_plan: {
      backup_scope: {
        begin_date: '2026/10/03 00:00:00',
        end_date: '2026/10/09 00:00:00',
      },
    },
    date_outcome: { state: 'primary' },
  },
}
describe('actual persisted window and progress', () => {
  it('explains session failures without classifying unrelated failures as login expiry', () => {
    expect(
      runResult({
        ...run,
        status: 'failed',
        result_count: null,
        error_code: 'SHOP_SESSION_AUTHENTICATION_INVALID',
      }),
    ).toContain('重新登录')
    expect(triggerFailure('SHOP_SESSION_NOT_CONFIGURED', 'session')).toContain(
      '先登录',
    )
    expect(triggerFailure('unknown', 'untrusted raw prose')).not.toContain(
      'untrusted',
    )
    expect(
      runResult({
        ...run,
        status: 'failed',
        result_count: null,
        error_code: 'PLATFORM_SIGNER_FAILED',
        error_stage: 'signer',
      }),
    ).not.toContain('重新登录')
  })
  it('distinguishes the approved primary rejection probe from two successful empty windows', () => {
    for (const code of [621000704, '621000704'] as const) {
      const primary_error = {
        error_code: 'DOUYIN_SELECTION_BUSINESS_REJECTED',
        error_stage: 'platform_business',
        platform_business_code: code,
      } as const
      for (const [state, label] of [
        [
          'fallback_checking',
          '2026-10-04～2026-10-10 · 首查被平台拒绝（621000704），正在补查',
        ],
        ['backup', '2026-10-03～2026-10-09 · 已回退一天'],
        ['backup_empty', '2026-10-03～2026-10-09 · 已回退一天 · 备用窗口为空'],
        [
          'fallback_failed',
          '2026-10-04～2026-10-10 · 首查被平台拒绝（621000704）、回退失败',
        ],
      ] as const) {
        expect(
          runWindow({
            ...run,
            request_conditions: {
              ...run.request_conditions!,
              date_outcome: {
                state,
                fallback_reason: 'primary_business_rejection_probe',
                primary_error,
              },
            },
          }),
        ).toBe(label)
      }
      expect(
        runResult({
          ...run,
          status: 'failed',
          result_count: null,
          error_code: primary_error.error_code,
          error_stage: primary_error.error_stage,
          platform_business_code: code,
        }),
      ).toBe('获取失败 · 平台业务拒绝（621000704），原因未确定')
      expect(
        runWindow({
          ...run,
          status: 'interrupted',
          request_conditions: {
            ...run.request_conditions!,
            date_outcome: {
              state: 'fallback_checking',
              fallback_reason: 'primary_business_rejection_probe',
              primary_error,
            },
          },
        }),
      ).toBe('2026-10-04～2026-10-10 · 首查被平台拒绝（621000704），补查中断')
    }
  })
  it('shows explicit chosen dates, empty success and distinct fallback outcomes', () => {
    expect(runWindow(run)).toBe('2026-10-04～2026-10-10')
    expect(runResult(run)).toContain('没有结果')
    for (const [state, label] of [
      ['backup', '2026-10-03～2026-10-09 · 已回退一天'],
      ['both_empty', '2026-10-04～2026-10-10 · 两个窗口均已检查为空'],
      ['fallback_failed', '2026-10-04～2026-10-10 · 首查为空、回退失败'],
    ] as const) {
      expect(
        runWindow({
          ...run,
          request_conditions: {
            ...run.request_conditions!,
            date_outcome: { state },
          },
        }),
      ).toBe(label)
    }
    expect(runWindow({ ...run, request_conditions: undefined })).toBe('—')
    expect(
      runResult({
        ...run,
        status: 'failed',
        result_count: null,
        error_stage: 'platform_business',
      }),
    ).toContain('失败 · platform_business')
  })
})
