import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { GENERATION_MODE_REGISTRY } from './generation-mode-registry'
import { loadAiGenerationVisualMock } from './load-visual-mock'
import { useAiGenerationStore } from './useAiGenerationStore'
import type { GenerationSourceImageView } from './types'

function createStore() {
  const store = useAiGenerationStore()
  store.initializeVisualMock(loadAiGenerationVisualMock())
  return store
}

function productSource(store: ReturnType<typeof useAiGenerationStore>) {
  return store.products
    .flatMap((product) => product.assets)
    .find((asset) => asset.role === 'PRODUCT_SOURCE')!
}

function styleReference(store: ReturnType<typeof useAiGenerationStore>) {
  return store.products
    .flatMap((product) => product.assets)
    .find((asset) => asset.role === 'STYLE_REFERENCE')!
}

function readyInstant(store: ReturnType<typeof useAiGenerationStore>): void {
  store.addInstantSources('PRODUCT_IMAGES', [productSource(store)])
  store.updateInstantPrompt('商品主体清晰')
}

describe('AI generation visual store: instant generation', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('defaults to instant generation with one editable config', () => {
    const store = createStore()
    expect(store.workMode).toBe('INSTANT')
    expect(store.instantDraft.mode).toBe('NORMAL_GENERATION')
    expect(store.instantDraft.appliedTemplate).toBeNull()
    expect(store.instantDraft.config).toEqual({
      prompt: '',
      outputFormat: 'SINGLE',
      size: '1:1',
      count: 1,
    })
    expect(store.instantExecution).toBeNull()
    expect(store.instantResults).toEqual([])
  })

  it('declares NORMAL with one product image slot in the registry', () => {
    expect(GENERATION_MODE_REGISTRY.NORMAL_GENERATION).toMatchObject({
      label: '普通生图',
      supportsTemplate: true,
    })
    expect(GENERATION_MODE_REGISTRY.NORMAL_GENERATION.inputSlots).toEqual([
      expect.objectContaining({
        key: 'PRODUCT_IMAGES',
        label: '商品图片',
        acceptedMaterialRole: 'PRODUCT_SOURCE',
      }),
    ])
  })

  it('declares STYLE with product and reference image slots', () => {
    const slots = GENERATION_MODE_REGISTRY.STYLE_REPLICATION.inputSlots
    expect(slots.map((slot) => slot.key)).toEqual([
      'PRODUCT_IMAGES',
      'REFERENCE_IMAGES',
    ])
    expect(slots[1]).toMatchObject({
      label: '参考图片',
      acceptedMaterialRole: 'STYLE_REFERENCE',
    })
  })

  it('switches to style replication through the registry definition', () => {
    const store = createStore()
    store.setInstantMode('STYLE_REPLICATION')
    expect(store.instantModeDefinition.inputSlots).toHaveLength(2)
    expect(store.instantDraft.inputs.REFERENCE_IMAGES).toEqual([])
  })

  it('accepts multiple local object-url images in one input slot', () => {
    const store = createStore()
    const sources: GenerationSourceImageView[] = [1, 2].map((index) => ({
      id: `local-${index}`,
      name: `local-${index}.webp`,
      previewUrl: `blob:http://localhost/local-${index}`,
      role: 'PRODUCT_SOURCE',
      sourceType: 'LOCAL_UPLOAD',
      objectUrl: true,
    }))
    store.addInstantSources('PRODUCT_IMAGES', sources)
    expect(store.instantDraft.inputs.PRODUCT_IMAGES).toEqual(sources)
  })

  it('accepts only PRODUCT_SOURCE in the product image slot', () => {
    const store = createStore()
    store.addInstantSources('PRODUCT_IMAGES', [
      productSource(store),
      styleReference(store),
    ])
    expect(store.instantDraft.inputs.PRODUCT_IMAGES).toHaveLength(1)
    expect(store.instantDraft.inputs.PRODUCT_IMAGES[0]!.role).toBe(
      'PRODUCT_SOURCE',
    )
  })

  it('accepts STYLE_REFERENCE only in the replication reference slot', () => {
    const store = createStore()
    store.setInstantMode('STYLE_REPLICATION')
    store.addInstantSources('REFERENCE_IMAGES', [
      productSource(store),
      styleReference(store),
    ])
    expect(store.instantDraft.inputs.REFERENCE_IMAGES).toHaveLength(1)
    expect(store.instantDraft.inputs.REFERENCE_IMAGES[0]!.role).toBe(
      'STYLE_REFERENCE',
    )
  })

  it('removes one image without clearing the rest of its slot', () => {
    const store = createStore()
    const first = productSource(store)
    const second = { ...first, id: 'second-source', name: 'second.webp' }
    store.addInstantSources('PRODUCT_IMAGES', [first, second])
    store.removeInstantSource('PRODUCT_IMAGES', first.id)
    expect(store.instantDraft.inputs.PRODUCT_IMAGES).toEqual([second])
  })

  it('keeps one canonical prompt and no negativePrompt field', () => {
    const store = createStore()
    store.updateInstantPrompt('统一提示词')
    expect(store.instantDraft.config.prompt).toBe('统一提示词')
    expect('negativePrompt' in store.instantDraft.config).toBe(false)
    expect('negativePrompt' in store.instantDraft).toBe(false)
  })

  it('selects one template as the applied fill source', () => {
    const store = createStore()
    const template = store.instantTemplateGroups[0]!.templates[0]!
    store.applyInstantTemplate(template.id)
    expect(store.instantDraft.appliedTemplate).toEqual({
      id: template.id,
      name: template.name,
    })
  })

  it('copies the template fields into the single isolated draft config', () => {
    const store = createStore()
    const template = store.instantTemplateGroups[0]!.templates[1]!
    store.applyInstantTemplate(template.id)
    expect(store.instantDraft.config).toEqual({
      prompt: template.prompt,
      outputFormat: template.outputFormat,
      size: template.size,
      count: template.count,
    })
    expect(store.instantDraft.config).not.toBe(template)
  })

  it('always uses the single draft config as effectiveConfig', () => {
    const store = createStore()
    const template = store.instantTemplateGroups[0]!.templates[1]!
    store.applyInstantTemplate(template.id)
    expect(store.instantEffectiveConfig).toEqual(store.instantDraft.config)
  })

  it('keeps template source immutable while the filled config remains editable', () => {
    const store = createStore()
    const template = store.instantTemplateGroups[0]!.templates[0]!
    const originalPrompt = template.prompt
    store.applyInstantTemplate(template.id)
    store.updateInstantPrompt('本次生成调整后的提示词')
    store.updateInstantSize('3:4')
    store.updateInstantCount(2)
    store.updateInstantOutputFormat('COLLAGE_2X2')
    expect(template.prompt).toBe(originalPrompt)
    expect(store.instantDraft.config).toEqual({
      prompt: '本次生成调整后的提示词',
      outputFormat: 'COLLAGE_2X2',
      size: '3:4',
      count: 2,
    })
  })

  it('clears only template metadata and preserves filled draft values', () => {
    const store = createStore()
    const template = store.instantTemplateGroups[0]!.templates[0]!
    store.applyInstantTemplate(template.id)
    const filledConfig = { ...store.instantDraft.config }
    store.clearInstantTemplate()
    expect(store.instantDraft.appliedTemplate).toBeNull()
    expect(store.instantDraft.config).toEqual(filledConfig)
  })

  it('replaces the current config when another template is selected', () => {
    const store = createStore()
    const [first, second] = store.instantTemplateGroups[0]!.templates
    const image = productSource(store)
    store.addInstantSources('PRODUCT_IMAGES', [image])
    store.applyInstantTemplate(first!.id)
    store.updateInstantPrompt('即将被新模板覆盖')
    store.applyInstantTemplate(second!.id)
    expect(store.instantDraft.appliedTemplate?.id).toBe(second!.id)
    expect(store.instantDraft.config).toEqual({
      prompt: second!.prompt,
      outputFormat: second!.outputFormat,
      size: second!.size,
      count: second!.count,
    })
    expect(store.instantDraft.inputs.PRODUCT_IMAGES).toEqual([image])
  })

  it('clears incompatible template metadata but retains its filled config on mode change', () => {
    const store = createStore()
    store.applyInstantTemplate(store.instantTemplateGroups[0]!.templates[0]!.id)
    const filledConfig = { ...store.instantDraft.config }
    store.setInstantMode('STYLE_REPLICATION')
    expect(store.instantDraft.appliedTemplate).toBeNull()
    expect(store.instantDraft.config).toEqual(filledConfig)
  })

  it('updates and bounds the shared generation parameters', () => {
    const store = createStore()
    store.updateInstantOutputFormat('COLLAGE_2X2')
    store.updateInstantSize('16:9')
    store.updateInstantCount(20)
    expect(store.instantDraft.config).toMatchObject({
      outputFormat: 'COLLAGE_2X2',
      size: '16:9',
      count: 8,
    })
  })

  it('creates deterministic results from the effective template config', () => {
    const store = createStore()
    store.addInstantSources('PRODUCT_IMAGES', [productSource(store)])
    const template = store.instantTemplateGroups[0]!.templates[1]!
    store.applyInstantTemplate(template.id)
    store.generateInstant()
    expect(store.instantResults).toHaveLength(template.count)
    expect(
      store.instantResults.every((result) => result.size === template.size),
    ).toBe(true)
    expect(store.instantResults.map((result) => result.slotIndex)).toEqual(
      Array.from({ length: template.count }, (_, index) => index),
    )
  })

  it('creates four fixed slots with all visual mock states', () => {
    const store = createStore()
    readyInstant(store)
    store.updateInstantCount(4)
    store.generateInstant()
    expect(store.instantExecution).toMatchObject({
      status: 'RUNNING',
      totalCount: 4,
      completedCount: 2,
      successCount: 1,
      runningCount: 1,
      waitingCount: 1,
      failedCount: 1,
    })
    expect(store.instantResults.map((result) => result.status)).toEqual([
      'SUCCESS',
      'RUNNING',
      'WAITING',
      'FAILED',
    ])
    expect(new Set(store.instantResults.map((result) => result.id)).size).toBe(
      4,
    )
  })

  it('completes pending slots without changing ids or order', () => {
    const store = createStore()
    readyInstant(store)
    store.updateInstantCount(4)
    store.generateInstant()
    const executionId = store.instantExecution!.id
    const identities = store.instantResults.map((result) => ({
      id: result.id,
      slotIndex: result.slotIndex,
    }))
    expect(store.completeInstantPendingResults(executionId)).toBe(true)
    expect(store.instantExecution).toMatchObject({
      status: 'PARTIAL_FAILED',
      completedCount: 4,
      successCount: 3,
      failedCount: 1,
    })
    expect(
      store.instantResults.map((result) => ({
        id: result.id,
        slotIndex: result.slotIndex,
      })),
    ).toEqual(identities)
  })

  it('retries and completes only one failed result', () => {
    const store = createStore()
    readyInstant(store)
    store.updateInstantCount(4)
    store.generateInstant()
    store.completeInstantPendingResults(store.instantExecution!.id)
    const failed = store.instantResults.find(
      (result) => result.status === 'FAILED',
    )!
    const otherResults = store.instantResults
      .filter((result) => result.id !== failed.id)
      .map((result) => ({ ...result }))

    expect(store.retryInstantResult(failed.id)).toBe(true)
    expect(failed.status).toBe('RUNNING')
    expect(store.completeInstantResult(failed.id)).toBe(true)
    expect(failed.status).toBe('SUCCESS')
    expect(store.instantExecution).toMatchObject({
      status: 'SUCCESS',
      completedCount: 4,
      successCount: 4,
      failedCount: 0,
    })
    expect(
      store.instantResults
        .filter((result) => result.id !== failed.id)
        .map((result) => ({ ...result })),
    ).toEqual(otherResults)
  })

  it('shares one result array with the active generation record', () => {
    const store = createStore()
    readyInstant(store)
    store.updateInstantCount(4)
    const record = store.generateInstant()!
    expect(record.detail.kind).toBe('INSTANT')
    if (record.detail.kind !== 'INSTANT') return
    const storedRecord = store.records.find(
      (candidate) => candidate.id === record.id,
    )!
    expect(storedRecord.detail.kind).toBe('INSTANT')
    if (storedRecord.detail.kind !== 'INSTANT') return
    expect(storedRecord.detail.results).toBe(store.instantExecution!.results)
    store.completeInstantPendingResults(store.instantExecution!.id)
    expect(record.status).toBe('PARTIAL_FAILED')
    expect(record.detail.results.map((result) => result.status)).toEqual(
      store.instantResults.map((result) => result.status),
    )
    const failed = store.instantResults.find(
      (result) => result.status === 'FAILED',
    )!
    store.retryInstantResult(failed.id)
    store.completeInstantResult(failed.id)
    expect(record.status).toBe('SUCCESS')
    expect(record.resultSummary).toBe('4 张')
  })

  it('keeps execution results independent from later template edits', () => {
    const store = createStore()
    readyInstant(store)
    store.updateInstantCount(2)
    store.generateInstant()
    const snapshot = store.instantResults.map((result) => ({ ...result }))
    const template = store.instantTemplateGroups[0]!.templates[0]!
    store.applyInstantTemplate(template.id)
    store.updateInstantPrompt('下一次任务使用的新提示词')
    expect(store.instantResults.map((result) => ({ ...result }))).toEqual(
      snapshot,
    )
  })

  it('marks a visual result as saved without writing Assets fixtures', () => {
    const store = createStore()
    readyInstant(store)
    store.generateInstant()
    const result = store.instantResults[0]!
    const product = store.products[0]!
    const assetCount = product.assets.length
    expect(store.saveInstantResult(result.id, product.id)).toBe(true)
    expect(result.savedToProductId).toBe(product.id)
    expect(product.assets).toHaveLength(assetCount)
  })

  it('records the effective config and template source only after generation', () => {
    const store = createStore()
    const initialCount = store.records.length
    store.addInstantSources('PRODUCT_IMAGES', [productSource(store)])
    const template = store.instantTemplateGroups[0]!.templates[1]!
    store.applyInstantTemplate(template.id)
    store.updateInstantPrompt('最终人工调整提示词')
    store.updateInstantSize('16:9')
    store.updateInstantCount(2)
    expect(store.records).toHaveLength(initialCount)
    const record = store.generateInstant()!
    expect(record.sourceType).toBe('INSTANT')
    expect(store.records).toHaveLength(initialCount + 1)
    expect(record.detail).toMatchObject({
      kind: 'INSTANT',
      templateId: template.id,
      templateName: template.name,
      effectiveConfig: {
        prompt: '最终人工调整提示词',
        outputFormat: template.outputFormat,
        size: '16:9',
        count: 2,
      },
    })
  })
})
