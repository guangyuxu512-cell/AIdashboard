import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  aiWorkbenchApi,
  type GenerationJobReadDto,
} from '@/entities/ai-workbench'

import {
  AI_WORKBENCH_ACTIVE_CONTEXT_STORAGE_KEY,
  aiWorkbenchSessionStorageKey,
  useAiWorkbenchSessionStore,
} from './useAiWorkbenchSessionStore'

function generationJob(
  id: string,
  workMode: 'INSTANT' | 'BATCH' = 'INSTANT',
): GenerationJobReadDto {
  return {
    generation_job_id: id,
    submission_key: `submission-${id}`,
    model_id: 'model-1',
    model_code: 'gpt-image-2',
    model_display_name: 'GPT Image 2',
    work_mode: workMode,
    mode: 'NORMAL_GENERATION',
    compress_output_under_1000kb: false,
    status: 'PENDING',
    total_count: 1,
    pending_count: 1,
    running_count: 0,
    success_count: 0,
    failed_count: 0,
    input_summary: { count: 1, primary_name: '测试图片' },
    created_by_display_name: '测试人员',
    created_at: '2026-09-09T00:00:00Z',
    updated_at: '2026-09-09T00:00:00Z',
    started_at: null,
    finished_at: null,
    items: [],
  }
}

function deferred<T>(): {
  promise: Promise<T>
  resolve: (value: T) => void
  reject: (reason: unknown) => void
} {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

const instantSubmission = {
  model_id: 'model-1',
  mode: 'NORMAL_GENERATION' as const,
  product_asset_ids: ['asset-1'],
  reference_asset_ids: [],
  prompt_template_id: 'template-1',
  prompt: '白底商品图',
  output_format: 'SINGLE' as const,
  size: '1:1' as const,
  count: 1,
  compress_output_under_1000kb: false,
}

const batchSubmission = {
  model_id: 'model-1',
  mode: 'NORMAL_GENERATION' as const,
  product_scope: 'SELECTED' as const,
  selected_product_ids: ['product-1'],
  template_source: 'CURRENT_SELECTION' as const,
  selected_template_group_ids: ['group-1'],
  output_range: 'MAIN_IMAGE' as const,
  compress_output_under_1000kb: false,
}

describe('AI Workbench session state', () => {
  beforeEach(() => {
    window.localStorage.clear()
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('retains separate instant and batch drafts and current jobs in one session', () => {
    const store = useAiWorkbenchSessionStore()
    store.instantPrompt = '保留即时提示词'
    store.instantSelectedModelId = 'model-instant'
    store.instantAppliedTemplateId = 'template-instant'
    store.instantSize = '3:4'
    store.instantCount = 3
    store.instantOutputFormat = 'COLLAGE_2X2'
    store.instantInputs.PRODUCT_IMAGES = [
      {
        id: 'asset-1',
        name: '商品图.png',
        previewUrl: '/api/v1/assets/asset-1/content',
        thumbnailUrl: '/api/v1/assets/asset-1/thumbnail',
        role: 'PRODUCT_SOURCE',
        sourceType: 'ASSET_LIBRARY',
      },
    ]
    store.instantCurrentJobId = 'job-instant'
    store.outputCompressionEnabled = true

    store.workMode = 'BATCH'
    store.batchMode = 'STYLE_REPLICATION'
    store.batchSelectedModelId = 'model-batch'
    store.batchProductScope = 'SELECTED'
    store.batchSelectedProductIds = ['product-1']
    store.batchTemplateSource = 'CURRENT_SELECTION'
    store.batchSelectedTemplateGroupIds = ['group-1']
    store.batchOutputRange = 'DETAIL_IMAGE'
    store.batchChecked = true
    store.batchCurrentJobId = 'job-batch'

    const restored = useAiWorkbenchSessionStore()
    expect(restored.workMode).toBe('BATCH')
    expect(restored.instantPrompt).toBe('保留即时提示词')
    expect(restored.instantSelectedModelId).toBe('model-instant')
    expect(restored.instantAppliedTemplateId).toBe('template-instant')
    expect(restored.instantInputs.PRODUCT_IMAGES[0]?.id).toBe('asset-1')
    expect(restored.instantSize).toBe('3:4')
    expect(restored.instantCount).toBe(3)
    expect(restored.instantOutputFormat).toBe('COLLAGE_2X2')
    expect(restored.instantCurrentJobId).toBe('job-instant')
    expect(restored.outputCompressionEnabled).toBe(true)
    expect(restored.batchMode).toBe('STYLE_REPLICATION')
    expect(restored.batchSelectedModelId).toBe('model-batch')
    expect(restored.batchSelectedProductIds).toEqual(['product-1'])
    expect(restored.batchSelectedTemplateGroupIds).toEqual(['group-1'])
    expect(restored.batchOutputRange).toBe('DETAIL_IMAGE')
    expect(restored.batchChecked).toBe(true)
    expect(restored.batchCurrentJobId).toBe('job-batch')
  })

  it('keeps one delayed instant submission across remounts without another POST', async () => {
    const receipt = deferred<GenerationJobReadDto>()
    const submit = vi
      .spyOn(aiWorkbenchApi, 'submitGeneration')
      .mockReturnValue(receipt.promise)
    const store = useAiWorkbenchSessionStore()
    store.outputCompressionEnabled = true

    const first = store.submitInstant({
      ...instantSubmission,
      compress_output_under_1000kb: store.outputCompressionEnabled,
    })
    const restored = useAiWorkbenchSessionStore()
    const second = restored.submitInstant({
      ...instantSubmission,
      compress_output_under_1000kb: false,
    })

    expect(submit).toHaveBeenCalledTimes(1)
    expect(store.instantSubmitting).toBe(true)
    expect(store.instantSubmissionKey).not.toBeNull()
    expect(submit.mock.calls[0]?.[0]).toMatchObject({
      work_mode: 'INSTANT',
      product_asset_ids: ['asset-1'],
      compress_output_under_1000kb: true,
    })

    receipt.resolve(generationJob('job-delayed'))
    await expect(first).resolves.toMatchObject({
      generation_job_id: 'job-delayed',
    })
    await expect(second).resolves.toMatchObject({
      generation_job_id: 'job-delayed',
    })
    expect(store.instantCurrentJobId).toBe('job-delayed')
    expect(store.instantSubmitting).toBe(false)
    expect(store.instantSubmissionKey).toBeNull()
  })

  it('retains the batch task independently after submission', async () => {
    vi.spyOn(aiWorkbenchApi, 'submitGeneration').mockResolvedValue(
      generationJob('job-batch', 'BATCH'),
    )
    const store = useAiWorkbenchSessionStore()

    await expect(store.submitBatch(batchSubmission)).resolves.toMatchObject({
      generation_job_id: 'job-batch',
    })

    expect(store.batchCurrentJobId).toBe('job-batch')
    expect(store.instantCurrentJobId).toBeNull()
  })

  it('clears both modes for a new actor context and ignores an old response', async () => {
    const oldReceipt = deferred<GenerationJobReadDto>()
    const submit = vi
      .spyOn(aiWorkbenchApi, 'submitGeneration')
      .mockReturnValueOnce(oldReceipt.promise)
      .mockResolvedValueOnce(generationJob('job-new-context'))
    const store = useAiWorkbenchSessionStore()
    store.activateActorContext({ userId: 'user-old', teamId: 'team-old' })
    store.instantPrompt = '旧身份草稿'
    store.instantInputs.PRODUCT_IMAGES = [
      {
        id: 'asset-old',
        name: '旧图片.png',
        previewUrl: '/api/v1/assets/asset-old/content',
        role: 'PRODUCT_SOURCE',
        sourceType: 'ASSET_LIBRARY',
      },
    ]
    store.batchSelectedProductIds = ['product-old']
    store.batchCurrentJobId = 'job-old'

    const oldSubmission = store.submitInstant(instantSubmission)
    store.replaceActorContext({ userId: 'user-new', teamId: 'team-new' })

    expect(store.workMode).toBe('INSTANT')
    expect(store.instantPrompt).toBe('')
    expect(store.instantInputs.PRODUCT_IMAGES).toEqual([])
    expect(store.instantCurrentJobId).toBeNull()
    expect(store.batchSelectedProductIds).toEqual([])
    expect(store.batchCurrentJobId).toBeNull()
    expect(store.instantSubmitting).toBe(false)

    await expect(store.submitInstant(instantSubmission)).resolves.toMatchObject(
      { generation_job_id: 'job-new-context' },
    )
    oldReceipt.resolve(generationJob('job-old-response'))
    await expect(oldSubmission).resolves.toBeNull()

    expect(submit).toHaveBeenCalledTimes(2)
    expect(store.instantCurrentJobId).toBe('job-new-context')
    expect(
      window.localStorage.getItem(
        aiWorkbenchSessionStorageKey('user-new', 'team-new'),
      ),
    ).not.toContain('job-old-response')
  })

  it('persists both drafts by actor and restores asset ids without browser URLs', () => {
    const storageKey = aiWorkbenchSessionStorageKey('user-1', 'team-1')
    const store = useAiWorkbenchSessionStore()
    store.activateActorContext({ userId: 'user-1', teamId: 'team-1' })
    store.workMode = 'BATCH'
    store.instantPrompt = '刷新后保留'
    store.instantSelectedModelId = 'model-instant'
    store.instantAppliedTemplateId = 'template-instant'
    store.instantInputs.PRODUCT_IMAGES = [
      {
        id: 'asset-1',
        name: '商品图.png',
        previewUrl: 'blob:must-not-persist',
        objectUrl: true,
        role: 'PRODUCT_SOURCE',
        sourceType: 'LOCAL_UPLOAD',
      },
    ]
    store.instantCurrentJobId = 'job-instant'
    store.batchSelectedModelId = 'model-batch'
    store.batchSelectedProductIds = ['product-1']
    store.batchSelectedTemplateGroupIds = ['group-1']
    store.batchCurrentJobId = 'job-batch'

    const raw = window.localStorage.getItem(storageKey)
    expect(raw).not.toBeNull()
    expect(raw).not.toContain('blob:must-not-persist')
    expect(raw).not.toContain('objectUrl')
    expect(
      window.localStorage.getItem(AI_WORKBENCH_ACTIVE_CONTEXT_STORAGE_KEY),
    ).toBe(storageKey)

    setActivePinia(createPinia())
    const restored = useAiWorkbenchSessionStore()
    restored.activateActorContext({ userId: 'user-1', teamId: 'team-1' })

    expect(restored.workMode).toBe('BATCH')
    expect(restored.instantPrompt).toBe('刷新后保留')
    expect(restored.instantInputs.PRODUCT_IMAGES).toEqual([
      {
        id: 'asset-1',
        name: '商品图.png',
        previewUrl: '/api/v1/ai-workbench/assets/asset-1/content',
        role: 'PRODUCT_SOURCE',
        sourceType: 'LOCAL_UPLOAD',
        thumbnailUrl: '/api/v1/ai-workbench/assets/asset-1/thumbnail',
      },
    ])
    expect(restored.instantCurrentJobId).toBe('job-instant')
    expect(restored.batchSelectedProductIds).toEqual(['product-1'])
    expect(restored.batchCurrentJobId).toBe('job-batch')
  })

  it('restores a known job with reads only and does not submit again', () => {
    const submit = vi.spyOn(aiWorkbenchApi, 'submitGeneration')
    const store = useAiWorkbenchSessionStore()
    store.activateActorContext({ userId: 'user-1', teamId: 'team-1' })
    store.instantCurrentJobId = 'known-job'

    setActivePinia(createPinia())
    const restored = useAiWorkbenchSessionStore()
    restored.activateActorContext({ userId: 'user-1', teamId: 'team-1' })

    expect(restored.instantCurrentJobId).toBe('known-job')
    expect(submit).not.toHaveBeenCalled()
  })

  it('reuses the persisted submission key when a receipt was not returned', async () => {
    const submit = vi
      .spyOn(aiWorkbenchApi, 'submitGeneration')
      .mockRejectedValueOnce(new Error('receipt lost'))
      .mockResolvedValueOnce(generationJob('recovered-job'))
    const store = useAiWorkbenchSessionStore()
    store.activateActorContext({ userId: 'user-1', teamId: 'team-1' })

    await expect(store.submitInstant(instantSubmission)).rejects.toThrow(
      'receipt lost',
    )
    const firstRequest = submit.mock.calls[0]?.[0]

    setActivePinia(createPinia())
    const restored = useAiWorkbenchSessionStore()
    restored.activateActorContext({ userId: 'user-1', teamId: 'team-1' })
    await restored.resumePendingSubmissions()

    expect(submit).toHaveBeenCalledTimes(2)
    expect(submit.mock.calls[1]?.[0]).toEqual(firstRequest)
    expect(restored.instantCurrentJobId).toBe('recovered-job')
    expect(restored.instantSubmissionKey).toBeNull()
  })

  it('clears only the selected work mode and rejects its late receipt', async () => {
    const receipt = deferred<GenerationJobReadDto>()
    vi.spyOn(aiWorkbenchApi, 'submitGeneration').mockReturnValue(
      receipt.promise,
    )
    const store = useAiWorkbenchSessionStore()
    store.activateActorContext({ userId: 'user-1', teamId: 'team-1' })
    store.batchSelectedProductIds = ['product-kept']
    store.batchCurrentJobId = 'batch-kept'
    store.instantPrompt = '将被清空'

    const pending = store.submitInstant(instantSubmission)
    store.clearInstant()
    receipt.resolve(generationJob('late-job'))

    await expect(pending).resolves.toBeNull()
    expect(store.instantPrompt).toBe('')
    expect(store.instantCurrentJobId).toBeNull()
    expect(store.instantSubmissionKey).toBeNull()
    expect(store.batchSelectedProductIds).toEqual(['product-kept'])
    expect(store.batchCurrentJobId).toBe('batch-kept')

    setActivePinia(createPinia())
    const restored = useAiWorkbenchSessionStore()
    restored.activateActorContext({ userId: 'user-1', teamId: 'team-1' })
    expect(restored.instantCurrentJobId).toBeNull()
    expect(restored.instantPrompt).toBe('')
    expect(restored.batchCurrentJobId).toBe('batch-kept')
  })

  it('clears the previous actor storage when identity context changes', () => {
    const firstKey = aiWorkbenchSessionStorageKey('user-1', 'team-1')
    const secondKey = aiWorkbenchSessionStorageKey('user-1', 'team-2')
    const store = useAiWorkbenchSessionStore()
    store.activateActorContext({ userId: 'user-1', teamId: 'team-1' })
    store.instantPrompt = '旧团队草稿'
    expect(window.localStorage.getItem(firstKey)).not.toBeNull()

    store.replaceActorContext({ userId: 'user-1', teamId: 'team-2' })
    expect(window.localStorage.getItem(firstKey)).toBeNull()
    expect(store.instantPrompt).toBe('')
    store.instantPrompt = '新团队草稿'
    expect(window.localStorage.getItem(secondKey)).not.toBeNull()

    store.clearActiveActorContext()
    expect(window.localStorage.getItem(secondKey)).toBeNull()
    expect(
      window.localStorage.getItem(AI_WORKBENCH_ACTIVE_CONTEXT_STORAGE_KEY),
    ).toBeNull()
  })

  it('removes the last persisted actor after initial session restoration is rejected', () => {
    const storageKey = aiWorkbenchSessionStorageKey('user-1', 'team-1')
    const store = useAiWorkbenchSessionStore()
    store.activateActorContext({ userId: 'user-1', teamId: 'team-1' })
    store.instantPrompt = '失效会话草稿'
    expect(window.localStorage.getItem(storageKey)).not.toBeNull()

    setActivePinia(createPinia())
    const freshStore = useAiWorkbenchSessionStore()
    freshStore.clearLastPersistedActorContext()

    expect(window.localStorage.getItem(storageKey)).toBeNull()
    expect(
      window.localStorage.getItem(AI_WORKBENCH_ACTIVE_CONTEXT_STORAGE_KEY),
    ).toBeNull()
  })
})
