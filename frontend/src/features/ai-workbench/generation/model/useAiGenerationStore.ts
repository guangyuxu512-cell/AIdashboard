import { computed, onScopeDispose, ref } from 'vue'
import { defineStore } from 'pinia'

import { cloneGenerationConfig } from '../../shared/model/generation-config'
import {
  createBatchExecutionView,
  retryBatchTemplateFailures,
  type BatchTemplateExecutionIdentity,
} from './batch-execution'
import {
  canDownloadInstantExecution,
  completeInstantExecutionResult,
  createInstantExecutionView,
  refreshInstantExecutionView,
  retryInstantExecutionResult,
} from './instant-execution'
import { createGenerationObjectUrlRegistry } from './generation-object-url-registry'
import { getGenerationModeDefinition } from './generation-mode-registry'
import type {
  BatchExecutionView,
  BatchGenerationDraft,
  BatchPreflightIssueView,
  BatchPreflightProductPlan,
  BatchPreflightView,
  BatchProductResultView,
  BatchProductScope,
  BatchTemplateSource,
  GenerationConfig,
  GenerationExecutionResultStatus,
  GenerationExecutionResultView,
  GenerationExecutionStatus,
  GenerationInputSlotKey,
  GenerationMode,
  GenerationOutputRange,
  GenerationProductView,
  GenerationRecordSourceType,
  GenerationRecordStatus,
  GenerationRecordView,
  GenerationResultView,
  GenerationSize,
  GenerationSourceImageView,
  GenerationTemplateGroupView,
  GenerationTemplateView,
  GenerationVisualMockFixture,
  GenerationWorkMode,
  InstantGenerationDraft,
  InstantExecutionView,
} from './types'

const DEFAULT_PAGE_SIZE = 20

type BatchExecutionProfile =
  'MIXED' | 'SUCCESS' | 'WAITING' | 'FAILED' | 'PARTIAL_FAILED'

const BATCH_EXECUTION_PROFILES: readonly BatchExecutionProfile[] = [
  'MIXED',
  'SUCCESS',
  'WAITING',
  'FAILED',
  'PARTIAL_FAILED',
]

function mockExecutionResultStatus(
  profile: BatchExecutionProfile,
  templateIndex: number,
  resultIndex: number,
  resultCount: number,
): GenerationExecutionResultStatus {
  if (profile === 'SUCCESS') return 'SUCCESS'
  if (profile === 'WAITING') return 'WAITING'
  if (profile === 'FAILED') return 'FAILED'
  if (profile === 'PARTIAL_FAILED') {
    return templateIndex === 0 && resultIndex === 0 ? 'FAILED' : 'SUCCESS'
  }

  const templateState = templateIndex % 5
  if (templateState === 0) return 'SUCCESS'
  if (templateState === 1) {
    return resultIndex === resultCount - 1 ? 'RUNNING' : 'SUCCESS'
  }
  if (templateState === 2) return 'WAITING'
  if (templateState === 3) return 'FAILED'
  return resultIndex === resultCount - 1 ? 'FAILED' : 'SUCCESS'
}

function createInstantDraft(): InstantGenerationDraft {
  return {
    mode: 'NORMAL_GENERATION',
    inputs: {
      PRODUCT_IMAGES: [],
      REFERENCE_IMAGES: [],
    },
    appliedTemplate: null,
    config: {
      prompt: '',
      outputFormat: 'SINGLE',
      size: '1:1',
      count: 1,
    },
  }
}

function createBatchDraft(): BatchGenerationDraft {
  return {
    mode: 'NORMAL_GENERATION',
    productScope: 'ALL_ENABLED',
    selectedProductIds: [],
    templateSource: 'PRODUCT_CONFIGURED',
    selectedTemplateGroupIds: [],
    outputRange: 'ALL',
  }
}

function cloneFixture(
  fixture: GenerationVisualMockFixture,
): GenerationVisualMockFixture {
  return JSON.parse(JSON.stringify(fixture)) as GenerationVisualMockFixture
}

function matches(value: string, query: string): boolean {
  return value.toLocaleLowerCase().includes(query)
}

function recordTimestamp(record: GenerationRecordView): number {
  const value = new Date(record.createdAt).getTime()
  return Number.isNaN(value) ? 0 : value
}

export interface GenerationRecordFilters {
  search: string
  sourceType: 'ALL' | GenerationRecordSourceType
  mode: 'ALL' | GenerationMode
  status: 'ALL' | GenerationRecordStatus
}

export function filterAndSortGenerationRecords(
  records: readonly GenerationRecordView[],
  filters: GenerationRecordFilters,
): GenerationRecordView[] {
  const query = filters.search.trim().toLocaleLowerCase()
  return records
    .filter(
      (record) =>
        (filters.sourceType === 'ALL' ||
          record.sourceType === filters.sourceType) &&
        (filters.mode === 'ALL' || record.mode === filters.mode) &&
        (filters.status === 'ALL' || record.status === filters.status) &&
        (!query ||
          matches(record.id, query) ||
          matches(record.summary, query) ||
          matches(record.createdBy, query)),
    )
    .sort(
      (left, right) =>
        recordTimestamp(right) - recordTimestamp(left) ||
        right.id.localeCompare(left.id),
    )
}

export const useAiGenerationStore = defineStore('ai-generation', () => {
  const visualMockActive = ref(false)
  const visualMockLoaded = ref(false)
  const sourceProducts = ref<GenerationProductView[]>([])
  const sourceTemplateGroups = ref<GenerationTemplateGroupView[]>([])
  const sourceRecords = ref<GenerationRecordView[]>([])
  const resultPreviewUrls = ref<string[]>([])
  const workMode = ref<GenerationWorkMode>('INSTANT')
  const instantDraft = ref<InstantGenerationDraft>(createInstantDraft())
  const instantExecution = ref<InstantExecutionView | null>(null)
  const batchDraft = ref<BatchGenerationDraft>(createBatchDraft())
  const batchResults = ref<BatchProductResultView[]>([])
  const batchExecution = ref<BatchExecutionView | null>(null)
  const batchChecked = ref(false)
  const recordsSearch = ref('')
  const recordsSourceType = ref<'ALL' | GenerationRecordSourceType>('ALL')
  const recordsMode = ref<'ALL' | GenerationMode>('ALL')
  const recordsStatus = ref<'ALL' | GenerationRecordStatus>('ALL')
  const recordsPage = ref(1)
  const recordsPageSize = ref(DEFAULT_PAGE_SIZE)
  const activeInstantRecordId = ref<string | null>(null)
  const objectUrlRegistry = createGenerationObjectUrlRegistry()
  let localSequence = 0

  function draftObjectUrlOwner(
    slotKey: GenerationInputSlotKey,
    sourceId: string,
  ): string {
    return `draft:${slotKey}:${sourceId}`
  }

  function recordObjectUrlOwner(
    recordId: string,
    slotKey: GenerationInputSlotKey,
    sourceId: string,
  ): string {
    return `record:${recordId}:${slotKey}:${sourceId}`
  }

  function releaseDraftSourceObjectUrl(
    slotKey: GenerationInputSlotKey,
    source: GenerationSourceImageView,
  ): void {
    objectUrlRegistry.release(
      source.previewUrl,
      draftObjectUrlOwner(slotKey, source.id),
    )
  }

  function releaseInstantDraftObjectUrls(): void {
    for (const slotKey of Object.keys(
      instantDraft.value.inputs,
    ) as GenerationInputSlotKey[]) {
      for (const source of instantDraft.value.inputs[slotKey]) {
        releaseDraftSourceObjectUrl(slotKey, source)
      }
    }
  }

  function retainRecordObjectUrls(record: GenerationRecordView): void {
    if (record.detail.kind !== 'INSTANT') return
    for (const slot of record.detail.inputSlots) {
      for (const source of slot.images) {
        objectUrlRegistry.retain(
          source.previewUrl,
          recordObjectUrlOwner(record.id, slot.key, source.id),
        )
      }
    }
  }

  function releaseRecordObjectUrls(record: GenerationRecordView): void {
    if (record.detail.kind !== 'INSTANT') return
    for (const slot of record.detail.inputSlots) {
      for (const source of slot.images) {
        objectUrlRegistry.release(
          source.previewUrl,
          recordObjectUrlOwner(record.id, slot.key, source.id),
        )
      }
    }
  }

  function disposeGenerationObjectUrls(): void {
    releaseInstantDraftObjectUrls()
    sourceRecords.value.forEach(releaseRecordObjectUrls)
    objectUrlRegistry.disposeAll()
  }

  onScopeDispose(disposeGenerationObjectUrls)

  const products = computed(() =>
    visualMockActive.value ? sourceProducts.value : [],
  )
  const templateGroups = computed(() =>
    visualMockActive.value ? sourceTemplateGroups.value : [],
  )
  const records = computed(() =>
    visualMockActive.value ? sourceRecords.value : [],
  )

  const instantTemplateGroups = computed(() =>
    templateGroups.value.filter(
      (group) => group.enabled && group.mode === instantDraft.value.mode,
    ),
  )

  const instantModeDefinition = computed(() =>
    getGenerationModeDefinition(instantDraft.value.mode),
  )

  const instantEffectiveConfig = computed<GenerationConfig>(
    () => instantDraft.value.config,
  )

  const instantResults = computed(() => instantExecution.value?.results ?? [])

  const canDownloadInstantResults = computed(() =>
    canDownloadInstantExecution(instantExecution.value),
  )

  const canGenerateInstant = computed(
    () =>
      visualMockActive.value &&
      instantModeDefinition.value.inputSlots.every(
        (slot) =>
          !slot.required || instantDraft.value.inputs[slot.key].length > 0,
      ) &&
      Boolean(instantEffectiveConfig.value.prompt.trim()),
  )

  const batchScopedProducts = computed(() => {
    const enabledProducts = products.value.filter((product) => product.enabled)
    if (batchDraft.value.productScope === 'ALL_ENABLED') {
      return enabledProducts
    }
    const selectedIds = new Set(batchDraft.value.selectedProductIds)
    return enabledProducts.filter((product) => selectedIds.has(product.id))
  })

  const availableBatchTemplateGroups = computed(() =>
    templateGroups.value.filter(
      (group) => group.mode === batchDraft.value.mode,
    ),
  )

  function templatesForOutputRange(
    group: GenerationTemplateGroupView,
  ): GenerationTemplateView[] {
    return group.templates.filter(
      (template) =>
        template.enabled &&
        (batchDraft.value.outputRange === 'ALL' ||
          template.outputRole === batchDraft.value.outputRange),
    )
  }

  function configuredGroupIds(product: GenerationProductView): string[] {
    if (batchDraft.value.templateSource === 'CURRENT_SELECTION') {
      return [...batchDraft.value.selectedTemplateGroupIds]
    }
    return batchDraft.value.mode === 'NORMAL_GENERATION'
      ? [...product.normalTemplateGroupIds]
      : [...product.styleReplicationTemplateGroupIds]
  }

  function preflightIssue(
    product: GenerationProductView,
    reason: BatchPreflightIssueView['reason'],
  ): BatchPreflightIssueView {
    return { productId: product.id, productName: product.name, reason }
  }

  function planProduct(product: GenerationProductView): {
    plan: BatchPreflightProductPlan | null
    issue: BatchPreflightIssueView | null
  } {
    const modeEnabled =
      batchDraft.value.mode === 'NORMAL_GENERATION'
        ? product.normalGenerationEnabled
        : product.styleReplicationEnabled
    if (!modeEnabled) {
      return { plan: null, issue: preflightIssue(product, 'MODE_DISABLED') }
    }
    const productSources = product.assets.filter(
      (asset) => asset.role === 'PRODUCT_SOURCE',
    )
    if (productSources.length === 0) {
      return {
        plan: null,
        issue: preflightIssue(product, 'NO_PRODUCT_SOURCE'),
      }
    }
    const styleReferences = product.assets.filter(
      (asset) => asset.role === 'STYLE_REFERENCE',
    )
    if (
      batchDraft.value.mode === 'STYLE_REPLICATION' &&
      styleReferences.length === 0
    ) {
      return {
        plan: null,
        issue: preflightIssue(product, 'NO_STYLE_REFERENCE'),
      }
    }
    const groupIds = configuredGroupIds(product)
    if (groupIds.length === 0) {
      return {
        plan: null,
        issue: preflightIssue(product, 'NO_TEMPLATE_GROUPS'),
      }
    }
    const configuredGroups = groupIds
      .map((groupId) =>
        templateGroups.value.find(
          (group) =>
            group.id === groupId && group.mode === batchDraft.value.mode,
        ),
      )
      .filter((group): group is GenerationTemplateGroupView => Boolean(group))
    if (configuredGroups.length === 0) {
      return {
        plan: null,
        issue: preflightIssue(product, 'NO_TEMPLATE_GROUPS'),
      }
    }
    const enabledGroups = configuredGroups.filter((group) => group.enabled)
    if (enabledGroups.length === 0) {
      return { plan: null, issue: preflightIssue(product, 'GROUP_DISABLED') }
    }
    const groups = enabledGroups
      .map((group) => ({ group, templates: templatesForOutputRange(group) }))
      .filter((entry) => entry.templates.length > 0)
    if (groups.length === 0) {
      return {
        plan: null,
        issue: preflightIssue(product, 'NO_ENABLED_TEMPLATES'),
      }
    }
    const styleReferenceCount =
      batchDraft.value.mode === 'STYLE_REPLICATION' ? styleReferences.length : 1
    const itemCount = groups.reduce(
      (groupTotal, entry) =>
        groupTotal +
        entry.templates.reduce(
          (templateTotal, template) =>
            templateTotal + template.count * styleReferenceCount,
          0,
        ),
      0,
    )
    return {
      issue: null,
      plan: {
        productId: product.id,
        productName: product.name,
        styleReferenceCount,
        groups,
        itemCount,
      },
    }
  }

  const batchPreflight = computed<BatchPreflightView>(() => {
    const plans: BatchPreflightProductPlan[] = []
    const issues: BatchPreflightIssueView[] = []
    for (const product of batchScopedProducts.value) {
      const result = planProduct(product)
      if (result.plan) plans.push(result.plan)
      if (result.issue) issues.push(result.issue)
    }
    return {
      productCount: batchScopedProducts.value.length,
      executableProductCount: plans.length,
      skippedProductCount: issues.length,
      templateGroupCount: plans.reduce(
        (total, plan) => total + plan.groups.length,
        0,
      ),
      generationItemCount: plans.reduce(
        (total, plan) => total + plan.itemCount,
        0,
      ),
      plans,
      issues,
    }
  })

  const filteredRecords = computed(() =>
    filterAndSortGenerationRecords(records.value, {
      search: recordsSearch.value,
      sourceType: recordsSourceType.value,
      mode: recordsMode.value,
      status: recordsStatus.value,
    }),
  )
  const recordsPageCount = computed(() =>
    Math.max(
      1,
      Math.ceil(filteredRecords.value.length / recordsPageSize.value),
    ),
  )
  const visibleRecords = computed(() => {
    const start = (recordsPage.value - 1) * recordsPageSize.value
    return filteredRecords.value.slice(start, start + recordsPageSize.value)
  })

  function initializeVisualMock(fixture: GenerationVisualMockFixture): void {
    visualMockActive.value = true
    if (visualMockLoaded.value) return
    const cloned = cloneFixture(fixture)
    sourceProducts.value = cloned.products
    sourceTemplateGroups.value = cloned.templateGroups
    sourceRecords.value = cloned.records
    resultPreviewUrls.value = cloned.resultPreviewUrls
    visualMockLoaded.value = true
  }

  function resetInstantDraft(): void {
    releaseInstantDraftObjectUrls()
    instantDraft.value = createInstantDraft()
  }

  function setVisualMockActive(value: boolean): void {
    if (!value && visualMockActive.value) {
      workMode.value = 'INSTANT'
      resetInstantDraft()
      instantExecution.value = null
      activeInstantRecordId.value = null
      batchDraft.value = createBatchDraft()
      batchResults.value = []
      batchExecution.value = null
      batchChecked.value = false
    }
    visualMockActive.value = value
  }

  function setWorkMode(value: GenerationWorkMode): void {
    workMode.value = value
  }

  function clearInstantTemplate(): void {
    instantDraft.value.appliedTemplate = null
  }

  function setInstantMode(value: GenerationMode): void {
    if (instantDraft.value.mode === value) return
    instantDraft.value.mode = value
    const allowedSlots = new Set(
      getGenerationModeDefinition(value).inputSlots.map((slot) => slot.key),
    )
    for (const slotKey of Object.keys(
      instantDraft.value.inputs,
    ) as GenerationInputSlotKey[]) {
      if (allowedSlots.has(slotKey)) continue
      instantDraft.value.inputs[slotKey].forEach((source) =>
        releaseDraftSourceObjectUrl(slotKey, source),
      )
      instantDraft.value.inputs[slotKey] = []
    }
    clearInstantTemplate()
  }

  function addInstantSources(
    slotKey: GenerationInputSlotKey,
    sources: readonly GenerationSourceImageView[],
  ): void {
    const slot = instantModeDefinition.value.inputSlots.find(
      (candidate) => candidate.key === slotKey,
    )
    if (!slot) return
    const current = new Map(
      instantDraft.value.inputs[slotKey].map((source) => [source.id, source]),
    )
    sources
      .filter((source) => source.role === slot.acceptedMaterialRole)
      .forEach((source) => {
        const previous = current.get(source.id)
        if (previous && previous.previewUrl !== source.previewUrl) {
          releaseDraftSourceObjectUrl(slotKey, previous)
        }
        if (objectUrlRegistry.isManaged(source.previewUrl)) {
          objectUrlRegistry.retain(
            source.previewUrl,
            draftObjectUrlOwner(slotKey, source.id),
          )
        }
        current.set(source.id, { ...source })
      })
    instantDraft.value.inputs[slotKey] = [...current.values()]
  }

  function addInstantUploadFiles(
    slotKey: GenerationInputSlotKey,
    files: readonly File[],
  ): void {
    const slot = instantModeDefinition.value.inputSlots.find(
      (candidate) => candidate.key === slotKey,
    )
    if (!slot) return
    const current = new Map(
      instantDraft.value.inputs[slotKey].map((source) => [source.id, source]),
    )
    for (const file of files) {
      const sourceId = `local-${slot.key}-${file.name}-${file.size}-${file.lastModified}`
      const previous = current.get(sourceId)
      if (previous) {
        releaseDraftSourceObjectUrl(slotKey, previous)
        current.delete(sourceId)
        instantDraft.value.inputs[slotKey] = [...current.values()]
      }
      const previewUrl = objectUrlRegistry.create(
        file,
        draftObjectUrlOwner(slotKey, sourceId),
      )
      current.set(sourceId, {
        id: sourceId,
        name: file.name,
        previewUrl,
        role: slot.acceptedMaterialRole,
        sourceType: 'LOCAL_UPLOAD',
        objectUrl: true,
      })
      instantDraft.value.inputs[slotKey] = [...current.values()]
    }
  }

  function removeInstantSource(
    slotKey: GenerationInputSlotKey,
    sourceId: string,
  ): void {
    const source = instantDraft.value.inputs[slotKey].find(
      (candidate) => candidate.id === sourceId,
    )
    if (source) releaseDraftSourceObjectUrl(slotKey, source)
    instantDraft.value.inputs[slotKey] = instantDraft.value.inputs[
      slotKey
    ].filter((source) => source.id !== sourceId)
  }

  function applyInstantTemplate(templateId: string | null): void {
    if (!templateId) {
      clearInstantTemplate()
      return
    }
    const template = instantTemplateGroups.value
      .flatMap((group) => group.templates)
      .find((candidate) => candidate.id === templateId && candidate.enabled)
    if (!template) return
    instantDraft.value.appliedTemplate = {
      id: template.id,
      name: template.name,
    }
    instantDraft.value.config = cloneGenerationConfig(template)
  }

  function updateInstantPrompt(value: string): void {
    instantDraft.value.config.prompt = value
  }

  function updateInstantOutputFormat(
    value: GenerationConfig['outputFormat'],
  ): void {
    instantDraft.value.config.outputFormat = value
  }

  function updateInstantSize(value: GenerationSize): void {
    instantDraft.value.config.size = value
  }

  function updateInstantCount(value: number | null): void {
    if (!value || !Number.isInteger(value)) return
    instantDraft.value.config.count = Math.min(8, Math.max(1, value))
  }

  function nextPreviewUrl(index: number): string {
    if (resultPreviewUrls.value.length === 0) return ''
    return resultPreviewUrls.value[index % resultPreviewUrls.value.length] ?? ''
  }

  function instantMockResultStatus(
    index: number,
    count: number,
  ): GenerationExecutionResultStatus {
    if (count === 1) return 'SUCCESS'
    if (count === 2) return index === 0 ? 'SUCCESS' : 'FAILED'
    if (count === 3) {
      return (['SUCCESS', 'RUNNING', 'WAITING'] as const)[index] ?? 'WAITING'
    }
    return (
      (['SUCCESS', 'RUNNING', 'WAITING', 'FAILED'] as const)[index] ?? 'WAITING'
    )
  }

  function newInstantExecutionResult(
    index: number,
    count: number,
    size: GenerationSize,
  ): GenerationExecutionResultView {
    localSequence += 1
    const status = instantMockResultStatus(index, count)
    return {
      id: `instant-result-${localSequence}`,
      slotIndex: index,
      name: `生成结果-${String(index + 1).padStart(2, '0')}.webp`,
      status,
      outputRole: 'MAIN_IMAGE',
      size,
      ...(status === 'SUCCESS'
        ? { previewUrl: nextPreviewUrl(localSequence + index) }
        : {}),
      ...(status === 'FAILED'
        ? {
            errorCode: 'VISUAL_MOCK_FAILED',
            errorMessage: '生成失败',
          }
        : {}),
    }
  }

  function generationRecordStatus(
    status: GenerationExecutionStatus,
  ): GenerationRecordStatus {
    if (status === 'WAITING') return 'QUEUED'
    return status
  }

  function instantRecordSummary(execution: InstantExecutionView): string {
    if (execution.status === 'SUCCESS') return `${execution.totalCount} 张`
    if (execution.failedCount > 0) {
      return `${execution.successCount} 成功 · ${execution.failedCount} 失败`
    }
    return `${execution.completedCount} / ${execution.totalCount}`
  }

  function syncActiveInstantRecord(): void {
    const execution = instantExecution.value
    if (!execution || !activeInstantRecordId.value) return
    const record = sourceRecords.value.find(
      (candidate) => candidate.id === activeInstantRecordId.value,
    )
    if (!record || record.detail.kind !== 'INSTANT') return
    record.status = generationRecordStatus(execution.status)
    record.resultSummary = instantRecordSummary(execution)
    record.detail.results = execution.results
  }

  function newResult(
    prefix: string,
    index: number,
    outputRole: GenerationResultView['outputRole'] = 'MAIN_IMAGE',
    size: GenerationSize = instantEffectiveConfig.value.size,
    status: GenerationResultView['status'] = 'SUCCESS',
  ): GenerationResultView {
    localSequence += 1
    return {
      id: `${prefix}-${localSequence}`,
      name: `生成结果-${String(index + 1).padStart(2, '0')}.webp`,
      previewUrl: nextPreviewUrl(localSequence + index),
      status,
      outputRole,
      size,
    }
  }

  function generateInstant(): GenerationRecordView | null {
    const productImage = instantDraft.value.inputs.PRODUCT_IMAGES[0]
    if (!canGenerateInstant.value || !productImage) {
      return null
    }
    const effectiveConfig = cloneGenerationConfig(instantEffectiveConfig.value)
    const results = Array.from({ length: effectiveConfig.count }, (_, index) =>
      newInstantExecutionResult(
        index,
        effectiveConfig.count,
        effectiveConfig.size,
      ),
    )
    localSequence += 1
    const execution = createInstantExecutionView({
      id: `visual-instant-execution-${localSequence}`,
      results,
    })
    instantExecution.value = execution
    localSequence += 1
    const record: GenerationRecordView = {
      id: `visual-instant-record-${localSequence}`,
      sourceType: 'INSTANT',
      mode: instantDraft.value.mode,
      status: generationRecordStatus(execution.status),
      createdAt: new Date().toISOString(),
      createdBy: '当前用户',
      summary: productImage.productName ?? productImage.name,
      resultSummary: instantRecordSummary(execution),
      detail: {
        kind: 'INSTANT',
        executionId: execution.id,
        inputSlots: instantModeDefinition.value.inputSlots.map((slot) => ({
          key: slot.key,
          label: slot.label,
          images: instantDraft.value.inputs[slot.key].map((image) => ({
            ...image,
          })),
        })),
        templateId: instantDraft.value.appliedTemplate?.id ?? null,
        templateName: instantDraft.value.appliedTemplate?.name ?? null,
        effectiveConfig,
        results: execution.results,
      },
    }
    retainRecordObjectUrls(record)
    sourceRecords.value.push(record)
    activeInstantRecordId.value = record.id
    return record
  }

  function completeInstantPendingResults(executionId: string): boolean {
    const execution = instantExecution.value
    if (!execution || execution.id !== executionId) return false
    let changed = false
    for (const result of execution.results) {
      if (result.status !== 'RUNNING' && result.status !== 'WAITING') continue
      result.status = 'SUCCESS'
      result.previewUrl = nextPreviewUrl(localSequence + result.slotIndex)
      changed = true
    }
    if (!changed) return false
    refreshInstantExecutionView(execution)
    syncActiveInstantRecord()
    return true
  }

  function retryInstantResult(resultId: string): boolean {
    const execution = instantExecution.value
    if (!execution || !retryInstantExecutionResult(execution, resultId)) {
      return false
    }
    syncActiveInstantRecord()
    return true
  }

  function completeInstantResult(resultId: string): boolean {
    const execution = instantExecution.value
    if (!execution) return false
    const result = execution.results.find(
      (candidate) => candidate.id === resultId,
    )
    if (
      !result ||
      !completeInstantExecutionResult(
        execution,
        resultId,
        nextPreviewUrl(localSequence + result.slotIndex),
      )
    ) {
      return false
    }
    syncActiveInstantRecord()
    return true
  }

  function markBatchDirty(): void {
    batchChecked.value = false
  }

  function setBatchMode(value: GenerationMode): void {
    if (batchDraft.value.mode === value) return
    batchDraft.value.mode = value
    batchDraft.value.selectedProductIds = []
    batchDraft.value.selectedTemplateGroupIds = []
    batchResults.value = []
    batchExecution.value = null
    markBatchDirty()
  }

  function setBatchProductScope(value: BatchProductScope): void {
    batchDraft.value.productScope = value
    markBatchDirty()
  }

  function setBatchSelectedProducts(values: readonly string[]): void {
    const allowedIds = new Set(
      products.value
        .filter((product) => product.enabled)
        .map((product) => product.id),
    )
    batchDraft.value.selectedProductIds = [
      ...new Set(values.filter((value) => allowedIds.has(value))),
    ]
    markBatchDirty()
  }

  function setBatchTemplateSource(value: BatchTemplateSource): void {
    batchDraft.value.templateSource = value
    markBatchDirty()
  }

  function setBatchSelectedTemplateGroups(values: readonly string[]): void {
    const allowedIds = new Set(
      availableBatchTemplateGroups.value.map((group) => group.id),
    )
    batchDraft.value.selectedTemplateGroupIds = [
      ...new Set(values.filter((value) => allowedIds.has(value))),
    ]
    markBatchDirty()
  }

  function setBatchOutputRange(value: GenerationOutputRange): void {
    batchDraft.value.outputRange = value
    markBatchDirty()
  }

  function runBatchPreflight(): BatchPreflightView {
    batchChecked.value = true
    return batchPreflight.value
  }

  function buildBatchResults(): BatchProductResultView[] {
    let resultIndex = 0
    return batchPreflight.value.plans.map((plan) => ({
      productId: plan.productId,
      productName: plan.productName,
      groups: plan.groups.map((entry) => ({
        groupId: entry.group.id,
        groupName: entry.group.name,
        templates: entry.templates.map((template) => {
          const count = template.count * plan.styleReferenceCount
          const results = Array.from({ length: count }, (_, index) => {
            resultIndex += 1
            return newResult(
              'batch-result',
              index,
              template.outputRole,
              template.size,
              resultIndex % 17 === 0 ? 'FAILED' : 'SUCCESS',
            )
          })
          return {
            templateId: template.id,
            templateName: template.name,
            outputRole: template.outputRole,
            results,
          }
        }),
      })),
    }))
  }

  function buildBatchExecution(): BatchExecutionView {
    return createBatchExecutionView({
      id: `visual-batch-execution-${localSequence + 1}`,
      products: batchPreflight.value.plans.map((plan, productIndex) => {
        const profile =
          BATCH_EXECUTION_PROFILES[
            productIndex % BATCH_EXECUTION_PROFILES.length
          ] ?? 'MIXED'
        let templateIndex = 0
        return {
          productId: plan.productId,
          productName: plan.productName,
          templateGroups: plan.groups.map((entry) => ({
            templateGroupId: entry.group.id,
            templateGroupName: entry.group.name,
            templates: entry.templates.map((template) => {
              const currentTemplateIndex = templateIndex
              templateIndex += 1
              const count = template.count * plan.styleReferenceCount
              return {
                templateId: template.id,
                templateName: template.name,
                outputRole: template.outputRole,
                results: Array.from({ length: count }, (_, resultIndex) => {
                  const status = mockExecutionResultStatus(
                    profile,
                    currentTemplateIndex,
                    resultIndex,
                    count,
                  )
                  return {
                    id: `execution-${productIndex}-${currentTemplateIndex}-${resultIndex}`,
                    slotIndex: resultIndex,
                    status,
                    ...(status === 'SUCCESS'
                      ? {
                          previewUrl: nextPreviewUrl(
                            productIndex + currentTemplateIndex + resultIndex,
                          ),
                        }
                      : {}),
                    ...(status === 'FAILED'
                      ? {
                          errorCode: 'VISUAL_MOCK_FAILED',
                          errorMessage: '生成失败',
                        }
                      : {}),
                  }
                }),
              }
            }),
          })),
        }
      }),
    })
  }

  function startBatchGeneration(): GenerationRecordView | null {
    batchChecked.value = true
    if (
      !visualMockActive.value ||
      batchPreflight.value.generationItemCount === 0
    ) {
      return null
    }
    const results = buildBatchResults()
    batchResults.value = results
    batchExecution.value = buildBatchExecution()
    const allResults = results.flatMap((product) =>
      product.groups.flatMap((group) =>
        group.templates.flatMap((template) => template.results),
      ),
    )
    const failedCount = allResults.filter(
      (result) => result.status === 'FAILED',
    ).length
    const successCount = allResults.length - failedCount
    localSequence += 1
    const record: GenerationRecordView = {
      id: `visual-batch-record-${localSequence}`,
      sourceType: 'BATCH',
      mode: batchDraft.value.mode,
      status: failedCount > 0 ? 'PARTIAL_FAILED' : 'SUCCESS',
      createdAt: new Date().toISOString(),
      createdBy: '当前用户',
      summary: `${batchPreflight.value.executableProductCount} 个产品`,
      resultSummary:
        failedCount > 0
          ? `${successCount} 成功 · ${failedCount} 失败`
          : `${successCount} 张`,
      detail: {
        kind: 'BATCH',
        productCount: batchPreflight.value.executableProductCount,
        templateGroupCount: batchPreflight.value.templateGroupCount,
        generationItemCount: batchPreflight.value.generationItemCount,
        successCount,
        failedCount,
        results: JSON.parse(
          JSON.stringify(results),
        ) as BatchProductResultView[],
      },
    }
    sourceRecords.value.push(record)
    return record
  }

  function setRecordsSearch(value: string): void {
    recordsSearch.value = value
    recordsPage.value = 1
  }

  function setRecordsSourceType(
    value: 'ALL' | GenerationRecordSourceType,
  ): void {
    recordsSourceType.value = value
    recordsPage.value = 1
  }

  function setRecordsMode(value: 'ALL' | GenerationMode): void {
    recordsMode.value = value
    recordsPage.value = 1
  }

  function setRecordsStatus(value: 'ALL' | GenerationRecordStatus): void {
    recordsStatus.value = value
    recordsPage.value = 1
  }

  function setRecordsPage(value: number): void {
    recordsPage.value = Math.min(Math.max(1, value), recordsPageCount.value)
  }

  function setRecordsPageSize(value: number): void {
    if (!Number.isInteger(value) || value <= 0) return
    recordsPageSize.value = value
    recordsPage.value = 1
  }

  function retryFailedRecord(recordId: string): boolean {
    const record = sourceRecords.value.find(
      (candidate) => candidate.id === recordId,
    )
    if (
      !record ||
      (record.status !== 'FAILED' && record.status !== 'PARTIAL_FAILED')
    ) {
      return false
    }
    if (record.detail.kind === 'INSTANT') {
      record.detail.results.forEach((result) => {
        if (result.status !== 'FAILED') return
        result.status = 'SUCCESS'
        result.previewUrl ??= nextPreviewUrl(localSequence + result.slotIndex)
      })
      record.resultSummary = `${record.detail.results.length} 张`
      if (instantExecution.value?.id === record.detail.executionId) {
        refreshInstantExecutionView(instantExecution.value)
      }
    } else {
      const results = record.detail.results.flatMap((product) => {
        const productResults = product.groups.flatMap((group) =>
          group.templates.flatMap((template) => template.results),
        )
        productResults.forEach((result) => {
          result.status = 'SUCCESS'
        })
        return productResults
      })
      record.detail.successCount = results.length
      record.detail.failedCount = 0
      record.resultSummary = `${results.length} 张`
    }
    record.status = 'SUCCESS'
    return true
  }

  function retryBatchTemplate(
    identity: BatchTemplateExecutionIdentity,
  ): boolean {
    if (!batchExecution.value) return false
    const retried = retryBatchTemplateFailures(batchExecution.value, identity)
    if (retried === batchExecution.value) return false
    batchExecution.value = retried
    return true
  }

  return {
    visualMockActive,
    visualMockLoaded,
    workMode,
    instantDraft,
    instantExecution,
    instantResults,
    batchDraft,
    batchResults,
    batchExecution,
    batchChecked,
    recordsSearch,
    recordsSourceType,
    recordsMode,
    recordsStatus,
    recordsPage,
    recordsPageSize,
    products,
    templateGroups,
    records,
    instantTemplateGroups,
    instantModeDefinition,
    instantEffectiveConfig,
    canGenerateInstant,
    canDownloadInstantResults,
    batchScopedProducts,
    availableBatchTemplateGroups,
    batchPreflight,
    filteredRecords,
    visibleRecords,
    recordsPageCount,
    initializeVisualMock,
    resetInstantDraft,
    setVisualMockActive,
    setWorkMode,
    setInstantMode,
    addInstantSources,
    addInstantUploadFiles,
    removeInstantSource,
    clearInstantTemplate,
    applyInstantTemplate,
    updateInstantPrompt,
    updateInstantOutputFormat,
    updateInstantSize,
    updateInstantCount,
    generateInstant,
    completeInstantPendingResults,
    retryInstantResult,
    completeInstantResult,
    setBatchMode,
    setBatchProductScope,
    setBatchSelectedProducts,
    setBatchTemplateSource,
    setBatchSelectedTemplateGroups,
    setBatchOutputRange,
    runBatchPreflight,
    startBatchGeneration,
    retryBatchTemplate,
    setRecordsSearch,
    setRecordsSourceType,
    setRecordsMode,
    setRecordsStatus,
    setRecordsPage,
    setRecordsPageSize,
    retryFailedRecord,
  }
})
