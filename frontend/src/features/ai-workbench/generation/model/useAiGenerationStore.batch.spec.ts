import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { loadAiGenerationVisualMock } from './load-visual-mock'
import { useAiGenerationStore } from './useAiGenerationStore'

function createStore() {
  const store = useAiGenerationStore()
  store.initializeVisualMock(loadAiGenerationVisualMock())
  store.setWorkMode('BATCH')
  return store
}

describe('AI generation visual store: batch generation', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('defaults to all enabled products', () => {
    const store = createStore()
    expect(store.batchDraft.productScope).toBe('ALL_ENABLED')
    expect(store.batchScopedProducts.every((product) => product.enabled)).toBe(
      true,
    )
  })

  it('runs only a selected product subset', () => {
    const store = createStore()
    const productId = store.products.find((product) => product.enabled)!.id
    store.setBatchProductScope('SELECTED')
    store.setBatchSelectedProducts([productId])
    expect(store.batchScopedProducts.map((product) => product.id)).toEqual([
      productId,
    ])
  })

  it('reads normalTemplateGroupIds for normal generation', () => {
    const store = createStore()
    const phone = store.products.find(
      (product) => product.id === 'pmg-phone-stand',
    )!
    store.setBatchProductScope('SELECTED')
    store.setBatchSelectedProducts([phone.id])
    expect(
      store.batchPreflight.plans[0]!.groups.map((entry) => entry.group.id),
    ).toEqual(phone.normalTemplateGroupIds)
  })

  it('reads styleReplicationTemplateGroupIds for style replication', () => {
    const store = createStore()
    const phone = store.products.find(
      (product) => product.id === 'pmg-phone-stand',
    )!
    store.setBatchMode('STYLE_REPLICATION')
    store.setBatchProductScope('SELECTED')
    store.setBatchSelectedProducts([phone.id])
    expect(
      store.batchPreflight.plans[0]!.groups.map((entry) => entry.group.id),
    ).toEqual(phone.styleReplicationTemplateGroupIds)
  })

  it('uses product configured groups by default', () => {
    expect(createStore().batchDraft.templateSource).toBe('PRODUCT_CONFIGURED')
  })

  it('supports one or more template groups selected for this draft', () => {
    const store = createStore()
    const ids = store.availableBatchTemplateGroups
      .filter((group) => group.enabled)
      .slice(0, 2)
      .map((group) => group.id)
    store.setBatchTemplateSource('CURRENT_SELECTION')
    store.setBatchSelectedTemplateGroups(ids)
    expect(store.batchDraft.selectedTemplateGroupIds).toEqual(ids)
  })

  it('does not write a current selection back to Assets defaults', () => {
    const store = createStore()
    const product = store.products[0]!
    const original = [...product.normalTemplateGroupIds]
    store.setBatchTemplateSource('CURRENT_SELECTION')
    store.setBatchSelectedTemplateGroups(['normal-minimal-main'])
    expect(product.normalTemplateGroupIds).toEqual(original)
  })

  it('treats configured group ids separately from product enabled state', () => {
    const store = createStore()
    const product = store.products.find(
      (candidate) =>
        candidate.enabled && candidate.normalTemplateGroupIds.length > 0,
    )!
    store.setBatchProductScope('SELECTED')
    store.setBatchSelectedProducts([product.id])
    expect(
      store.batchPreflight.plans[0]!.groups.map((entry) => entry.group.id),
    ).toEqual(product.normalTemplateGroupIds)
    expect(product.enabled).toBe(true)
  })

  it('clears products and templates independently', () => {
    const store = createStore()
    const productId = store.products.find((product) => product.enabled)!.id
    const templateId = store.availableBatchTemplateGroups.find(
      (group) => group.enabled,
    )!.id
    store.setBatchProductScope('SELECTED')
    store.setBatchSelectedProducts([productId])
    store.setBatchTemplateSource('CURRENT_SELECTION')
    store.setBatchSelectedTemplateGroups([templateId])

    store.setBatchSelectedProducts([])
    expect(store.batchDraft.selectedProductIds).toEqual([])
    expect(store.batchDraft.selectedTemplateGroupIds).toEqual([templateId])

    store.setBatchSelectedProducts([productId])
    store.setBatchSelectedTemplateGroups([])
    expect(store.batchDraft.selectedProductIds).toEqual([productId])
    expect(store.batchDraft.selectedTemplateGroupIds).toEqual([])
  })

  it('counts all enabled templates for ALL output range', () => {
    const store = createStore()
    store.setBatchOutputRange('ALL')
    expect(store.batchPreflight.generationItemCount).toBeGreaterThan(0)
  })

  it('filters generation items to MAIN_IMAGE', () => {
    const store = createStore()
    store.setBatchOutputRange('MAIN_IMAGE')
    expect(
      store.batchPreflight.plans
        .flatMap((plan) => plan.groups)
        .every((entry) =>
          entry.templates.every(
            (template) => template.outputRole === 'MAIN_IMAGE',
          ),
        ),
    ).toBe(true)
  })

  it('filters generation items to DETAIL_IMAGE', () => {
    const store = createStore()
    store.setBatchOutputRange('DETAIL_IMAGE')
    expect(
      store.batchPreflight.plans
        .flatMap((plan) => plan.groups)
        .every((entry) =>
          entry.templates.every(
            (template) => template.outputRole === 'DETAIL_IMAGE',
          ),
        ),
    ).toBe(true)
  })

  it('reports product, executable, skipped, group and item statistics', () => {
    const preflight = createStore().runBatchPreflight()
    expect(preflight.productCount).toBe(
      preflight.executableProductCount + preflight.skippedProductCount,
    )
    expect(preflight.templateGroupCount).toBeGreaterThan(0)
    expect(preflight.generationItemCount).toBeGreaterThan(0)
  })

  it('covers all required skip reasons across normal and style checks', () => {
    const store = createStore()
    const reasons = new Set(
      store.batchPreflight.issues.map((issue) => issue.reason),
    )
    store.setBatchMode('STYLE_REPLICATION')
    store.batchPreflight.issues.forEach((issue) => reasons.add(issue.reason))
    expect(reasons).toEqual(
      new Set([
        'NO_PRODUCT_SOURCE',
        'NO_TEMPLATE_GROUPS',
        'NO_STYLE_REFERENCE',
        'MODE_DISABLED',
        'GROUP_DISABLED',
        'NO_ENABLED_TEMPLATES',
      ]),
    )
  })

  it('calculates normal item count from enabled template counts', () => {
    const store = createStore()
    const plan = store.batchPreflight.plans[0]!
    const expected = plan.groups.reduce(
      (total, entry) =>
        total +
        entry.templates.reduce((sum, template) => sum + template.count, 0),
      0,
    )
    expect(plan.itemCount).toBe(expected)
  })

  it('multiplies style items by STYLE_REFERENCE count', () => {
    const store = createStore()
    const phone = store.products.find(
      (product) => product.id === 'pmg-phone-stand',
    )!
    store.setBatchMode('STYLE_REPLICATION')
    store.setBatchProductScope('SELECTED')
    store.setBatchSelectedProducts([phone.id])
    const plan = store.batchPreflight.plans[0]!
    const templateTotal = plan.groups.reduce(
      (total, entry) =>
        total +
        entry.templates.reduce((sum, template) => sum + template.count, 0),
      0,
    )
    expect(plan.itemCount).toBe(templateTotal * plan.styleReferenceCount)
  })

  it('creates a BATCH record when batch generation starts', () => {
    const store = createStore()
    const record = store.startBatchGeneration()
    expect(record?.sourceType).toBe('BATCH')
  })

  it('organizes results by product, group and template', () => {
    const store = createStore()
    store.startBatchGeneration()
    const product = store.batchResults[0]!
    expect(product.productId).toBeTruthy()
    expect(product.groups[0]!.groupId).toBeTruthy()
    expect(product.groups[0]!.templates[0]!.templateId).toBeTruthy()
    expect(product.groups[0]!.templates[0]!.results.length).toBeGreaterThan(0)
  })
})
