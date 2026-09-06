import type {
  BatchExecutionFilter,
  BatchExecutionView,
  BatchProductExecutionView,
  BatchTemplateExecutionView,
  BatchTemplateGroupExecutionView,
  GenerationExecutionResultStatus,
  GenerationExecutionResultView,
  GenerationOutputRole,
} from './types'
import {
  deriveExecutionStatus,
  summarizeExecutionResults,
} from './execution-result'

export {
  deriveExecutionStatus,
  summarizeExecutionResults,
} from './execution-result'
export type { ExecutionCounts } from './execution-result'

export interface BatchTemplateExecutionSeed {
  templateId: string
  templateName: string
  outputRole: GenerationOutputRole
  results: GenerationExecutionResultView[]
}

export interface BatchTemplateGroupExecutionSeed {
  templateGroupId: string
  templateGroupName: string
  templates: BatchTemplateExecutionSeed[]
}

export interface BatchProductExecutionSeed {
  productId: string
  productName: string
  templateGroups: BatchTemplateGroupExecutionSeed[]
}

export interface BatchExecutionSeed {
  id: string
  products: BatchProductExecutionSeed[]
}

function createTemplateExecution(
  seed: BatchTemplateExecutionSeed,
): BatchTemplateExecutionView {
  const results = seed.results.map((result) => ({ ...result }))
  const counts = summarizeExecutionResults(results)
  return {
    templateId: seed.templateId,
    templateName: seed.templateName,
    outputRole: seed.outputRole,
    status: deriveExecutionStatus(results.map((result) => result.status)),
    completedCount: counts.completedItems,
    totalCount: counts.totalItems,
    results,
  }
}

function createTemplateGroupExecution(
  seed: BatchTemplateGroupExecutionSeed,
): BatchTemplateGroupExecutionView {
  const templates = seed.templates.map(createTemplateExecution)
  const results = templates.flatMap((template) => template.results)
  const counts = summarizeExecutionResults(results)
  return {
    templateGroupId: seed.templateGroupId,
    templateGroupName: seed.templateGroupName,
    status: deriveExecutionStatus(results.map((result) => result.status)),
    completedCount: counts.completedItems,
    totalCount: counts.totalItems,
    templates,
  }
}

function createProductExecution(
  seed: BatchProductExecutionSeed,
): BatchProductExecutionView {
  const templateGroups = seed.templateGroups.map(createTemplateGroupExecution)
  const results = templateGroups.flatMap((group) =>
    group.templates.flatMap((template) => template.results),
  )
  const counts = summarizeExecutionResults(results)
  return {
    productId: seed.productId,
    productName: seed.productName,
    status: deriveExecutionStatus(results.map((result) => result.status)),
    completedCount: counts.completedItems,
    totalCount: counts.totalItems,
    templateGroups,
  }
}

export function createBatchExecutionView(
  seed: BatchExecutionSeed,
): BatchExecutionView {
  const products = seed.products.map(createProductExecution)
  const results = products.flatMap((product) =>
    product.templateGroups.flatMap((group) =>
      group.templates.flatMap((template) => template.results),
    ),
  )
  const counts = summarizeExecutionResults(results)
  return {
    id: seed.id,
    status: deriveExecutionStatus(results.map((result) => result.status)),
    totalItems: counts.totalItems,
    successItems: counts.successItems,
    runningItems: counts.runningItems,
    waitingItems: counts.waitingItems,
    failedItems: counts.failedItems,
    products,
  }
}

export function filterBatchExecutionProducts(
  products: readonly BatchProductExecutionView[],
  filter: BatchExecutionFilter,
): BatchProductExecutionView[] {
  if (filter === 'ALL') return [...products]
  const acceptedStatuses: GenerationExecutionResultStatus[] =
    filter === 'RUNNING' ? ['WAITING', 'RUNNING'] : ['FAILED']
  const accepted = new Set<GenerationExecutionResultStatus>(acceptedStatuses)
  return products.filter((product) =>
    product.templateGroups.some((group) =>
      group.templates.some((template) =>
        template.results.some((result) => accepted.has(result.status)),
      ),
    ),
  )
}

export function resolveBatchProductSelection(
  products: readonly BatchProductExecutionView[],
  selectedProductId: string | null,
): string | null {
  return products.some((product) => product.productId === selectedProductId)
    ? selectedProductId
    : (products[0]?.productId ?? null)
}

export function findDefaultExpandedTemplateGroupId(
  product: BatchProductExecutionView,
): string | null {
  const priorityGroup = product.templateGroups.find((group) =>
    group.templates.some((template) =>
      template.results.some(
        (result) => result.status === 'RUNNING' || result.status === 'FAILED',
      ),
    ),
  )
  return (
    priorityGroup?.templateGroupId ??
    product.templateGroups[0]?.templateGroupId ??
    null
  )
}

export interface BatchTemplateExecutionIdentity {
  productId: string
  templateGroupId: string
  templateId: string
}

export function retryBatchTemplateFailures(
  execution: BatchExecutionView,
  identity: BatchTemplateExecutionIdentity,
): BatchExecutionView {
  let changed = false
  const products = execution.products.map((product) => ({
    productId: product.productId,
    productName: product.productName,
    templateGroups: product.templateGroups.map((group) => ({
      templateGroupId: group.templateGroupId,
      templateGroupName: group.templateGroupName,
      templates: group.templates.map((template) => {
        const shouldRetry =
          product.productId === identity.productId &&
          group.templateGroupId === identity.templateGroupId &&
          template.templateId === identity.templateId
        return {
          templateId: template.templateId,
          templateName: template.templateName,
          outputRole: template.outputRole,
          results: template.results.map((result) => {
            if (!shouldRetry || result.status !== 'FAILED') return { ...result }
            changed = true
            return {
              ...result,
              status: 'RUNNING' as const,
              errorCode: undefined,
              errorMessage: undefined,
            }
          }),
        }
      }),
    })),
  }))

  return changed
    ? createBatchExecutionView({ id: execution.id, products })
    : execution
}
