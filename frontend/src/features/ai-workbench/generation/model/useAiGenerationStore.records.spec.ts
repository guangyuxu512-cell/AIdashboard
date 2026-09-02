import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { loadAiGenerationVisualMock } from './load-visual-mock'
import { useAiGenerationStore } from './useAiGenerationStore'

function createStore() {
  const store = useAiGenerationStore()
  store.initializeVisualMock(loadAiGenerationVisualMock())
  return store
}

function readyInstant(store: ReturnType<typeof useAiGenerationStore>): void {
  const product = store.products[0]!
  store.addInstantSources('PRODUCT_IMAGES', [
    product.assets.find((asset) => asset.role === 'PRODUCT_SOURCE')!,
  ])
  store.updateInstantPrompt('new record')
}

describe('AI generation visual store: generation records', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('sorts by real createdAt descending', () => {
    const records = createStore().filteredRecords
    expect(
      records.every(
        (record, index) =>
          index === 0 ||
          new Date(records[index - 1]!.createdAt).getTime() >=
            new Date(record.createdAt).getTime(),
      ),
    ).toBe(true)
  })

  it('filters INSTANT records', () => {
    const store = createStore()
    store.setRecordsSourceType('INSTANT')
    expect(
      store.filteredRecords.every((record) => record.sourceType === 'INSTANT'),
    ).toBe(true)
  })

  it('filters BATCH records', () => {
    const store = createStore()
    store.setRecordsSourceType('BATCH')
    expect(
      store.filteredRecords.every((record) => record.sourceType === 'BATCH'),
    ).toBe(true)
  })

  it('filters generation mode', () => {
    const store = createStore()
    store.setRecordsMode('STYLE_REPLICATION')
    expect(
      store.filteredRecords.every(
        (record) => record.mode === 'STYLE_REPLICATION',
      ),
    ).toBe(true)
  })

  it('filters generation status', () => {
    const store = createStore()
    store.setRecordsStatus('PARTIAL_FAILED')
    expect(
      store.filteredRecords.every(
        (record) => record.status === 'PARTIAL_FAILED',
      ),
    ).toBe(true)
  })

  it('searches id, content and creator', () => {
    const store = createStore()
    store.setRecordsSearch('张三')
    expect(store.filteredRecords.length).toBeGreaterThan(0)
    expect(
      store.filteredRecords.every((record) => record.createdBy === '张三'),
    ).toBe(true)
  })

  it('paginates with the standard default and resets on size change', () => {
    const store = createStore()
    expect(store.recordsPageSize).toBe(20)
    expect(store.visibleRecords).toHaveLength(20)
    store.setRecordsPage(2)
    store.setRecordsPageSize(10)
    expect(store.recordsPage).toBe(1)
    expect(store.visibleRecords).toHaveLength(10)
  })

  it('keeps createdBy on every record', () => {
    expect(createStore().records.every((record) => record.createdBy)).toBe(true)
  })

  it('provides instant record detail', () => {
    const record = createStore().records.find(
      (candidate) => candidate.detail.kind === 'INSTANT',
    )!
    expect(record.detail.kind).toBe('INSTANT')
    if (record.detail.kind === 'INSTANT') {
      expect(record.detail.inputSlots[0]!.images[0]!.name).toBeTruthy()
      expect(record.detail.effectiveConfig.prompt).toBeTruthy()
      expect('negativePrompt' in record.detail).toBe(false)
      expect('negativePrompt' in record.detail.effectiveConfig).toBe(false)
    }
  })

  it('keeps saved and unsaved instant results distinguishable in records', () => {
    const results = createStore().records.flatMap((record) =>
      record.detail.kind === 'INSTANT'
        ? record.detail.results.filter((result) => result.status === 'SUCCESS')
        : [],
    )
    expect(results.some((result) => Boolean(result.savedToProductId))).toBe(
      true,
    )
    expect(results.some((result) => !result.savedToProductId)).toBe(true)
  })

  it('snapshots the manual effective config', () => {
    const store = createStore()
    readyInstant(store)
    store.updateInstantOutputFormat('COLLAGE_2X2')
    store.updateInstantSize('4:3')
    store.updateInstantCount(3)
    const record = store.generateInstant()!
    expect(record.detail).toMatchObject({
      kind: 'INSTANT',
      templateId: null,
      templateName: null,
      effectiveConfig: {
        prompt: 'new record',
        outputFormat: 'COLLAGE_2X2',
        size: '4:3',
        count: 3,
      },
    })
  })

  it('snapshots the template effective config and source', () => {
    const store = createStore()
    const product = store.products[0]!
    store.addInstantSources('PRODUCT_IMAGES', [
      product.assets.find((asset) => asset.role === 'PRODUCT_SOURCE')!,
    ])
    const template = store.instantTemplateGroups[0]!.templates[1]!
    store.applyInstantTemplate(template.id)
    const record = store.generateInstant()!
    expect(record.detail).toMatchObject({
      kind: 'INSTANT',
      templateId: template.id,
      templateName: template.name,
      effectiveConfig: {
        prompt: template.prompt,
        outputFormat: template.outputFormat,
        size: template.size,
        count: template.count,
      },
    })
  })

  it('keeps every template-backed fixture record mode-compatible and exact', () => {
    const store = createStore()
    const templateRecords = store.records.filter(
      (record) =>
        record.detail.kind === 'INSTANT' && record.detail.templateId !== null,
    )

    expect(templateRecords.length).toBeGreaterThan(0)
    for (const record of templateRecords) {
      if (record.detail.kind !== 'INSTANT') continue
      const detail = record.detail
      const template = store.templateGroups
        .filter((group) => group.mode === record.mode && group.enabled)
        .flatMap((group) => group.templates)
        .find((candidate) => candidate.id === detail.templateId)

      expect(template).toBeDefined()
      expect(detail.templateName).toBe(template!.name)
      expect(detail.effectiveConfig).toEqual({
        prompt: template!.prompt,
        outputFormat: template!.outputFormat,
        size: template!.size,
        count: template!.count,
      })
    }
  })

  it('provides batch record detail and hierarchy', () => {
    const record = createStore().records.find(
      (candidate) => candidate.detail.kind === 'BATCH',
    )!
    expect(record.detail.kind).toBe('BATCH')
    if (record.detail.kind === 'BATCH')
      expect(record.detail.results[0]!.groups[0]).toBeTruthy()
  })

  it('keeps every batch fixture hierarchy mode-compatible', () => {
    const store = createStore()
    const batchRecords = store.records.filter(
      (record) => record.detail.kind === 'BATCH',
    )

    for (const record of batchRecords) {
      if (record.detail.kind !== 'BATCH') continue
      const resultItems = record.detail.results.flatMap((product) =>
        product.groups.flatMap((group) =>
          group.templates.flatMap((template) => template.results),
        ),
      )
      expect(record.detail.productCount).toBe(record.detail.results.length)
      expect(record.detail.templateGroupCount).toBe(
        record.detail.results.reduce(
          (total, product) => total + product.groups.length,
          0,
        ),
      )
      expect(record.detail.generationItemCount).toBe(resultItems.length)
      expect(record.detail.successCount).toBe(
        resultItems.filter((result) => result.status === 'SUCCESS').length,
      )
      expect(record.detail.failedCount).toBe(
        resultItems.filter((result) => result.status === 'FAILED').length,
      )
      for (const product of record.detail.results) {
        for (const groupResult of product.groups) {
          const group = store.templateGroups.find(
            (candidate) =>
              candidate.id === groupResult.groupId &&
              candidate.mode === record.mode,
          )
          expect(group).toBeDefined()
          for (const templateResult of groupResult.templates) {
            expect(
              group!.templates.some(
                (template) => template.id === templateResult.templateId,
              ),
            ).toBe(true)
          }
        }
      }
    }
  })

  it('contains PARTIAL_FAILED fixture records', () => {
    expect(
      createStore().records.some(
        (record) => record.status === 'PARTIAL_FAILED',
      ),
    ).toBe(true)
  })

  it('retries failed entries as a mock interaction', () => {
    const store = createStore()
    const record = store.records.find(
      (candidate) =>
        candidate.status === 'FAILED' || candidate.status === 'PARTIAL_FAILED',
    )!
    expect(store.retryFailedRecord(record.id)).toBe(true)
    expect(record.status).toBe('SUCCESS')
  })

  it('archives batch results that succeed after a record retry', () => {
    const store = createStore()
    const record = store.records.find(
      (candidate) =>
        candidate.detail.kind === 'BATCH' &&
        (candidate.status === 'FAILED' ||
          candidate.status === 'PARTIAL_FAILED'),
    )!
    expect(store.retryFailedRecord(record.id)).toBe(true)
    expect(record.detail.kind).toBe('BATCH')
    if (record.detail.kind === 'BATCH') {
      for (const product of record.detail.results) {
        for (const result of product.groups.flatMap((group) =>
          group.templates.flatMap((template) => template.results),
        )) {
          expect(result.savedToProductId).toBe(product.productId)
        }
      }
    }
  })

  it('places a newly generated record first by timestamp', () => {
    const store = createStore()
    readyInstant(store)
    const record = store.generateInstant()!
    expect(store.filteredRecords[0]!.id).toBe(record.id)
  })

  it('exposes no fixture records when the normal runtime is active', () => {
    const store = createStore()
    readyInstant(store)
    store.generateInstant()
    store.setWorkMode('BATCH')
    store.setVisualMockActive(false)
    expect(store.records).toEqual([])
    expect(store.visibleRecords).toEqual([])
    expect(store.instantResults).toEqual([])
    expect(store.batchResults).toEqual([])
    expect(store.workMode).toBe('INSTANT')
  })
})
