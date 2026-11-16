import { describe, expect, it } from 'vitest'

import {
  canDownloadInstantExecution,
  completeInstantExecutionResult,
  createInstantExecutionView,
  retryInstantExecutionResult,
} from './instant-execution'
import type {
  GenerationExecutionResultStatus,
  GenerationExecutionResultView,
} from './types'

function result(
  slotIndex: number,
  status: GenerationExecutionResultStatus,
): GenerationExecutionResultView {
  return {
    id: `result-${slotIndex}`,
    slotIndex,
    name: `结果 ${slotIndex + 1}`,
    status,
    ...(status === 'SUCCESS' ? { previewUrl: `preview-${slotIndex}` } : {}),
    ...(status === 'FAILED'
      ? { errorCode: 'MOCK_FAILED', errorMessage: '生成失败' }
      : {}),
  }
}

function execution(statuses: GenerationExecutionResultStatus[]) {
  return createInstantExecutionView({
    id: 'instant-execution',
    results: statuses.map((status, index) => result(index, status)),
  })
}

describe('instant execution derivation', () => {
  it('keeps stable slot order independently of status', () => {
    const view = createInstantExecutionView({
      id: 'ordered',
      results: [
        result(2, 'SUCCESS'),
        result(0, 'WAITING'),
        result(1, 'FAILED'),
      ],
    })
    expect(view.results.map((item) => item.slotIndex)).toEqual([0, 1, 2])
    expect(view.results.map((item) => item.id)).toEqual([
      'result-0',
      'result-1',
      'result-2',
    ])
  })

  it('counts every result state and completed slot', () => {
    expect(
      execution(['WAITING', 'RUNNING', 'SUCCESS', 'FAILED']),
    ).toMatchObject({
      totalCount: 4,
      completedCount: 2,
      successCount: 1,
      runningCount: 1,
      waitingCount: 1,
      failedCount: 1,
    })
  })

  it.each([
    [['WAITING', 'WAITING'], 'WAITING'],
    [['SUCCESS', 'RUNNING'], 'RUNNING'],
    [['SUCCESS', 'SUCCESS'], 'SUCCESS'],
    [['SUCCESS', 'FAILED'], 'PARTIAL_FAILED'],
    [['FAILED', 'FAILED'], 'FAILED'],
  ] as const)('derives request status %s as %s', (statuses, expected) => {
    expect(execution([...statuses]).status).toBe(expected)
  })

  it('derives progress from completed slots', () => {
    const view = execution(['SUCCESS', 'FAILED', 'RUNNING', 'WAITING'])
    expect((view.completedCount / view.totalCount) * 100).toBe(50)
  })

  it('enables download all only when a success result exists', () => {
    expect(canDownloadInstantExecution(null)).toBe(false)
    expect(canDownloadInstantExecution(execution(['RUNNING', 'WAITING']))).toBe(
      false,
    )
    expect(canDownloadInstantExecution(execution(['SUCCESS', 'FAILED']))).toBe(
      true,
    )
  })

  it('retries only the targeted failed result and re-derives counts', () => {
    const view = execution(['SUCCESS', 'FAILED', 'FAILED'])
    const untouched = view.results[2]!
    expect(retryInstantExecutionResult(view, 'result-1')).toBe(true)
    expect(view.results.map((item) => item.status)).toEqual([
      'SUCCESS',
      'RUNNING',
      'FAILED',
    ])
    expect(view.results[2]).toBe(untouched)
    expect(view).toMatchObject({
      status: 'RUNNING',
      successCount: 1,
      runningCount: 1,
      failedCount: 1,
    })
  })

  it('completes only a running retry and preserves its stable identity', () => {
    const view = execution(['SUCCESS', 'FAILED'])
    const resultId = view.results[1]!.id
    const slotIndex = view.results[1]!.slotIndex
    retryInstantExecutionResult(view, resultId)
    expect(
      completeInstantExecutionResult(view, resultId, 'retry-preview'),
    ).toBe(true)
    expect(view.results[1]).toMatchObject({
      id: resultId,
      slotIndex,
      status: 'SUCCESS',
      previewUrl: 'retry-preview',
    })
    expect(view).toMatchObject({
      status: 'SUCCESS',
      completedCount: 2,
      successCount: 2,
      failedCount: 0,
    })
  })
})
