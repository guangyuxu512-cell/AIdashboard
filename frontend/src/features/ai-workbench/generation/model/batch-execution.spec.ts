import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import {
  createBatchExecutionView,
  deriveExecutionStatus,
  filterBatchExecutionProducts,
  findDefaultExpandedTemplateGroupId,
  resolveBatchProductSelection,
  retryBatchTemplateFailures,
  summarizeExecutionResults,
  type BatchExecutionSeed,
} from './batch-execution'
import { loadAiGenerationVisualMock } from './load-visual-mock'
import type {
  GenerationExecutionResultStatus,
  GenerationExecutionResultView,
} from './types'
import { useAiGenerationStore } from './useAiGenerationStore'

function result(
  id: string,
  status: GenerationExecutionResultStatus,
): GenerationExecutionResultView {
  return {
    id,
    slotIndex: Number(id.match(/\d+/)?.[0] ?? 0),
    status,
    ...(status === 'SUCCESS' ? { previewUrl: `preview-${id}` } : {}),
    ...(status === 'FAILED'
      ? { errorCode: 'MOCK_FAILED', errorMessage: '生成失败' }
      : {}),
  }
}

function seed(): BatchExecutionSeed {
  return {
    id: 'batch-1',
    products: [
      {
        productId: 'product-running',
        productName: '运行商品',
        templateGroups: [
          {
            templateGroupId: 'group-success',
            templateGroupName: '成功组',
            templates: [
              {
                templateId: 'template-success',
                templateName: '成功模板',
                outputRole: 'MAIN_IMAGE',
                results: [result('success-1', 'SUCCESS')],
              },
            ],
          },
          {
            templateGroupId: 'group-running',
            templateGroupName: '运行组',
            templates: [
              {
                templateId: 'template-running',
                templateName: '运行模板',
                outputRole: 'DETAIL_IMAGE',
                results: [
                  result('success-2', 'SUCCESS'),
                  result('running-1', 'RUNNING'),
                  result('waiting-1', 'WAITING'),
                ],
              },
            ],
          },
        ],
      },
      {
        productId: 'product-failed',
        productName: '失败商品',
        templateGroups: [
          {
            templateGroupId: 'group-failed',
            templateGroupName: '失败组',
            templates: [
              {
                templateId: 'template-failed',
                templateName: '失败模板',
                outputRole: 'MAIN_IMAGE',
                results: [result('failed-1', 'FAILED')],
              },
            ],
          },
        ],
      },
    ],
  }
}

function visualStore() {
  const store = useAiGenerationStore()
  store.initializeVisualMock(loadAiGenerationVisualMock())
  store.setWorkMode('BATCH')
  return store
}

describe('batch execution derivation', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('derives batch totals from every leaf result', () => {
    const execution = createBatchExecutionView(seed())
    expect(execution).toMatchObject({
      totalItems: 5,
      successItems: 2,
      runningItems: 1,
      waitingItems: 1,
      failedItems: 1,
      status: 'RUNNING',
    })
  })

  it('derives product totals and status from descendant results', () => {
    const product = createBatchExecutionView(seed()).products[0]!
    expect(product).toMatchObject({
      completedCount: 2,
      totalCount: 4,
      status: 'RUNNING',
    })
  })

  it('derives group totals and status from template results', () => {
    const group =
      createBatchExecutionView(seed()).products[0]!.templateGroups[1]!
    expect(group).toMatchObject({
      completedCount: 1,
      totalCount: 3,
      status: 'RUNNING',
    })
  })

  it('derives SUCCESS', () => {
    expect(deriveExecutionStatus(['SUCCESS', 'SUCCESS'])).toBe('SUCCESS')
  })

  it('derives RUNNING', () => {
    expect(deriveExecutionStatus(['SUCCESS', 'RUNNING'])).toBe('RUNNING')
  })

  it('derives WAITING', () => {
    expect(deriveExecutionStatus(['WAITING', 'WAITING'])).toBe('WAITING')
  })

  it('derives FAILED', () => {
    expect(deriveExecutionStatus(['FAILED', 'FAILED'])).toBe('FAILED')
  })

  it('derives PARTIAL_FAILED for a completed success/failure mix', () => {
    expect(deriveExecutionStatus(['SUCCESS', 'FAILED'])).toBe('PARTIAL_FAILED')
  })

  it('defines completed as success plus failure', () => {
    expect(
      summarizeExecutionResults([
        result('success', 'SUCCESS'),
        result('failed', 'FAILED'),
        result('running', 'RUNNING'),
        result('waiting', 'WAITING'),
      ]),
    ).toMatchObject({ totalItems: 4, completedItems: 2 })
  })

  it('returns every product for ALL', () => {
    const products = createBatchExecutionView(seed()).products
    expect(filterBatchExecutionProducts(products, 'ALL')).toHaveLength(2)
  })

  it('filters RUNNING by WAITING or RUNNING leaves', () => {
    const products = createBatchExecutionView(seed()).products
    expect(
      filterBatchExecutionProducts(products, 'RUNNING').map(
        (product) => product.productId,
      ),
    ).toEqual(['product-running'])
  })

  it('filters FAILED by failed leaves', () => {
    const products = createBatchExecutionView(seed()).products
    expect(
      filterBatchExecutionProducts(products, 'FAILED').map(
        (product) => product.productId,
      ),
    ).toEqual(['product-failed'])
  })

  it('corrects selection to the first filtered product', () => {
    const products = filterBatchExecutionProducts(
      createBatchExecutionView(seed()).products,
      'FAILED',
    )
    expect(resolveBatchProductSelection(products, 'product-running')).toBe(
      'product-failed',
    )
    expect(resolveBatchProductSelection([], 'product-running')).toBeNull()
  })

  it('expands the first group containing a running or failed result', () => {
    const product = createBatchExecutionView(seed()).products[0]!
    expect(findDefaultExpandedTemplateGroupId(product)).toBe('group-running')
  })

  it('preserves result preview and future failure fields', () => {
    const execution = createBatchExecutionView(seed())
    const results = execution.products.flatMap((product) =>
      product.templateGroups.flatMap((group) =>
        group.templates.flatMap((template) => template.results),
      ),
    )
    expect(results.find((item) => item.id === 'success-1')?.previewUrl).toBe(
      'preview-success-1',
    )
    expect(results.find((item) => item.id === 'failed-1')).toMatchObject({
      errorCode: 'MOCK_FAILED',
      errorMessage: '生成失败',
    })
  })

  it('retries only failed leaves and re-derives every aggregate', () => {
    const execution = createBatchExecutionView(seed())
    const retried = retryBatchTemplateFailures(execution, {
      productId: 'product-failed',
      templateGroupId: 'group-failed',
      templateId: 'template-failed',
    })
    expect(retried.failedItems).toBe(0)
    expect(retried.runningItems).toBe(2)
    expect(retried.products[1]!.status).toBe('RUNNING')
  })

  it('keeps preflight skips outside runtime failed totals', () => {
    const store = visualStore()
    const preflight = store.runBatchPreflight()
    store.startBatchGeneration()
    expect(preflight.skippedProductCount).toBeGreaterThan(0)
    expect(store.batchExecution).not.toBeNull()
    expect(store.batchExecution!.failedItems).not.toBe(
      store.batchExecution!.failedItems + preflight.skippedProductCount,
    )
  })

  it('keeps the visual fixture hierarchy and aggregate totals consistent', () => {
    const store = visualStore()
    const preflight = store.runBatchPreflight()
    store.startBatchGeneration()
    const execution = store.batchExecution!
    const leaves = execution.products.flatMap((product) =>
      product.templateGroups.flatMap((group) =>
        group.templates.flatMap((template) => template.results),
      ),
    )
    expect(execution.totalItems).toBe(preflight.generationItemCount)
    expect(execution.totalItems).toBe(leaves.length)
    expect(execution.successItems).toBe(
      leaves.filter((item) => item.status === 'SUCCESS').length,
    )
    expect(execution.runningItems).toBe(
      leaves.filter((item) => item.status === 'RUNNING').length,
    )
    expect(execution.waitingItems).toBe(
      leaves.filter((item) => item.status === 'WAITING').length,
    )
    expect(execution.failedItems).toBe(
      leaves.filter((item) => item.status === 'FAILED').length,
    )
    expect(
      new Set(execution.products.map((product) => product.status)),
    ).toEqual(
      new Set(['RUNNING', 'SUCCESS', 'WAITING', 'FAILED', 'PARTIAL_FAILED']),
    )
  })

  it('exposes retry through the visual store', () => {
    const store = visualStore()
    store.startBatchGeneration()
    const failedProduct = store.batchExecution!.products.find((product) =>
      product.templateGroups.some((group) =>
        group.templates.some((template) => template.status === 'FAILED'),
      ),
    )!
    const failedGroup = failedProduct.templateGroups.find((group) =>
      group.templates.some((template) => template.status === 'FAILED'),
    )!
    const failedTemplate = failedGroup.templates.find(
      (template) => template.status === 'FAILED',
    )!
    expect(
      store.retryBatchTemplate({
        productId: failedProduct.productId,
        templateGroupId: failedGroup.templateGroupId,
        templateId: failedTemplate.templateId,
      }),
    ).toBe(true)
    expect(
      store
        .batchExecution!.products.find(
          (product) => product.productId === failedProduct.productId,
        )!
        .templateGroups.find(
          (group) => group.templateGroupId === failedGroup.templateGroupId,
        )!
        .templates.find(
          (template) => template.templateId === failedTemplate.templateId,
        )!.status,
    ).toBe('RUNNING')
  })
})
