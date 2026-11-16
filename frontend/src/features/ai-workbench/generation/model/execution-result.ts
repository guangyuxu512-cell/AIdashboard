import type {
  GenerationExecutionResultStatus,
  GenerationExecutionResultView,
  GenerationExecutionStatus,
} from './types'

export interface ExecutionCounts {
  totalItems: number
  completedItems: number
  successItems: number
  runningItems: number
  waitingItems: number
  failedItems: number
}

export function summarizeExecutionResults(
  results: readonly GenerationExecutionResultView[],
): ExecutionCounts {
  const counts: ExecutionCounts = {
    totalItems: results.length,
    completedItems: 0,
    successItems: 0,
    runningItems: 0,
    waitingItems: 0,
    failedItems: 0,
  }

  for (const result of results) {
    if (result.status === 'SUCCESS') counts.successItems += 1
    if (result.status === 'RUNNING') counts.runningItems += 1
    if (result.status === 'WAITING') counts.waitingItems += 1
    if (result.status === 'FAILED') counts.failedItems += 1
  }
  counts.completedItems = counts.successItems + counts.failedItems
  return counts
}

export function deriveExecutionStatus(
  statuses: readonly GenerationExecutionResultStatus[],
): GenerationExecutionStatus {
  if (
    statuses.length === 0 ||
    statuses.every((status) => status === 'WAITING')
  ) {
    return 'WAITING'
  }
  if (statuses.every((status) => status === 'SUCCESS')) return 'SUCCESS'
  if (statuses.every((status) => status === 'FAILED')) return 'FAILED'
  if (statuses.some((status) => status === 'WAITING' || status === 'RUNNING')) {
    return 'RUNNING'
  }
  return 'PARTIAL_FAILED'
}
