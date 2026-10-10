import { describe, it, expect } from 'vitest'
import { runWindow, runResult } from './run-display'
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
