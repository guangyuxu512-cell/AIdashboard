import {
  deriveExecutionStatus,
  summarizeExecutionResults,
} from './execution-result'
import type {
  GenerationExecutionResultView,
  InstantExecutionView,
} from './types'

export interface InstantExecutionSeed {
  id: string
  results: readonly GenerationExecutionResultView[]
}

export function refreshInstantExecutionView(
  execution: InstantExecutionView,
): InstantExecutionView {
  const counts = summarizeExecutionResults(execution.results)
  execution.status = deriveExecutionStatus(
    execution.results.map((result) => result.status),
  )
  execution.totalCount = counts.totalItems
  execution.completedCount = counts.completedItems
  execution.successCount = counts.successItems
  execution.runningCount = counts.runningItems
  execution.waitingCount = counts.waitingItems
  execution.failedCount = counts.failedItems
  return execution
}

export function createInstantExecutionView(
  seed: InstantExecutionSeed,
): InstantExecutionView {
  const execution: InstantExecutionView = {
    id: seed.id,
    status: 'WAITING',
    totalCount: 0,
    completedCount: 0,
    successCount: 0,
    runningCount: 0,
    waitingCount: 0,
    failedCount: 0,
    results: seed.results
      .map((result) => ({ ...result }))
      .sort((left, right) => left.slotIndex - right.slotIndex),
  }
  return refreshInstantExecutionView(execution)
}

export function retryInstantExecutionResult(
  execution: InstantExecutionView,
  resultId: string,
): boolean {
  const result = execution.results.find(
    (candidate) => candidate.id === resultId && candidate.status === 'FAILED',
  )
  if (!result) return false
  result.status = 'RUNNING'
  delete result.errorCode
  delete result.errorMessage
  refreshInstantExecutionView(execution)
  return true
}

export function completeInstantExecutionResult(
  execution: InstantExecutionView,
  resultId: string,
  previewUrl: string,
): boolean {
  const result = execution.results.find(
    (candidate) =>
      candidate.id === resultId &&
      (candidate.status === 'RUNNING' || candidate.status === 'WAITING'),
  )
  if (!result) return false
  result.status = 'SUCCESS'
  result.previewUrl = previewUrl
  refreshInstantExecutionView(execution)
  return true
}

export function canDownloadInstantExecution(
  execution: InstantExecutionView | null,
): boolean {
  return (execution?.successCount ?? 0) > 0
}
