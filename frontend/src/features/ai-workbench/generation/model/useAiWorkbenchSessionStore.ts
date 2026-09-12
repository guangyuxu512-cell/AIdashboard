import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { z } from 'zod'

import {
  getAssetContentUrl,
  getAssetThumbnailUrl,
} from '@/entities/asset/api/asset-api'
import {
  aiWorkbenchApi,
  type BatchGenerationSubmitDto,
  type GenerationJobReadDto,
  type InstantGenerationSubmitDto,
} from '@/entities/ai-workbench'
import { getErrorMessage } from '@/shared/api'

import type {
  BatchProductScope,
  BatchTemplateSource,
  GenerationInputSlotKey,
  GenerationMode,
  GenerationOutputFormat,
  GenerationOutputRange,
  GenerationSize,
  GenerationSourceImageView,
  GenerationWorkMode,
} from './types'

type InstantSubmission = Omit<
  InstantGenerationSubmitDto,
  'submission_key' | 'work_mode'
>
type BatchSubmission = Omit<
  BatchGenerationSubmitDto,
  'submission_key' | 'work_mode'
>

interface ActorContextIdentity {
  userId: string
  teamId: string
}

interface InstantSubmissionIntent {
  submissionKey: string
  submission: InstantSubmission
}

interface BatchSubmissionIntent {
  submissionKey: string
  submission: BatchSubmission
}

export const AI_WORKBENCH_SESSION_STORAGE_PREFIX =
  'control-center.ai-workbench-session.v2'
export const AI_WORKBENCH_ACTIVE_CONTEXT_STORAGE_KEY =
  'control-center.ai-workbench-session.v2.active-context'

const sourceImageSchema = z
  .object({
    id: z.string().min(1),
    name: z.string(),
    role: z.enum(['PRODUCT_SOURCE', 'STYLE_REFERENCE']),
    sourceType: z.enum(['LOCAL_UPLOAD', 'ASSET_LIBRARY']),
    productId: z.string().optional(),
    productName: z.string().optional(),
  })
  .strict()

const instantSubmissionSchema = z
  .object({
    model_id: z.string().min(1),
    mode: z.enum(['NORMAL_GENERATION', 'STYLE_REPLICATION']),
    product_asset_ids: z.array(z.string().min(1)),
    reference_asset_ids: z.array(z.string().min(1)),
    prompt_template_id: z.string().min(1).nullable().optional(),
    prompt: z.string(),
    output_format: z.enum(['SINGLE', 'COLLAGE_2X2']),
    size: z.enum(['1:1', '3:4', '4:3', '16:9']),
    count: z.number().int().min(1).max(8),
    compress_output_under_1000kb: z.boolean().default(false),
  })
  .strict()

const batchSubmissionSchema = z
  .object({
    model_id: z.string().min(1),
    mode: z.enum(['NORMAL_GENERATION', 'STYLE_REPLICATION']),
    product_scope: z.enum(['ALL_ENABLED', 'SELECTED']),
    selected_product_ids: z.array(z.string().min(1)),
    template_source: z.enum(['PRODUCT_CONFIGURED', 'CURRENT_SELECTION']),
    selected_template_group_ids: z.array(z.string().min(1)),
    output_range: z.enum(['ALL', 'MAIN_IMAGE', 'DETAIL_IMAGE']),
    compress_output_under_1000kb: z.boolean().default(false),
  })
  .strict()

const persistedSessionSchema = z
  .object({
    version: z.literal(2),
    workMode: z.enum(['INSTANT', 'BATCH']),
    outputCompressionEnabled: z.boolean().default(false),
    instant: z
      .object({
        mode: z.enum(['NORMAL_GENERATION', 'STYLE_REPLICATION']),
        selectedModelId: z.string().min(1).nullable(),
        inputs: z
          .object({
            PRODUCT_IMAGES: z.array(sourceImageSchema),
            REFERENCE_IMAGES: z.array(sourceImageSchema),
          })
          .strict(),
        appliedTemplateId: z.string().min(1).nullable(),
        prompt: z.string(),
        outputFormat: z.enum(['SINGLE', 'COLLAGE_2X2']),
        size: z.enum(['1:1', '3:4', '4:3', '16:9']),
        count: z.number().int().min(1).max(8),
        currentJobId: z.string().min(1).nullable(),
        submissionIntent: z
          .object({
            submissionKey: z.string().min(1),
            submission: instantSubmissionSchema,
          })
          .strict()
          .nullable(),
      })
      .strict(),
    batch: z
      .object({
        mode: z.enum(['NORMAL_GENERATION', 'STYLE_REPLICATION']),
        selectedModelId: z.string().min(1).nullable(),
        productScope: z.enum(['ALL_ENABLED', 'SELECTED']),
        selectedProductIds: z.array(z.string().min(1)),
        templateSource: z.enum(['PRODUCT_CONFIGURED', 'CURRENT_SELECTION']),
        selectedTemplateGroupIds: z.array(z.string().min(1)),
        outputRange: z.enum(['ALL', 'MAIN_IMAGE', 'DETAIL_IMAGE']),
        checked: z.boolean(),
        currentJobId: z.string().min(1).nullable(),
        submissionIntent: z
          .object({
            submissionKey: z.string().min(1),
            submission: batchSubmissionSchema,
          })
          .strict()
          .nullable(),
      })
      .strict(),
  })
  .strict()

type PersistedSession = z.infer<typeof persistedSessionSchema>
type PersistedSourceImage = z.infer<typeof sourceImageSchema>

function emptyInputs(): Record<
  GenerationInputSlotKey,
  GenerationSourceImageView[]
> {
  return {
    PRODUCT_IMAGES: [],
    REFERENCE_IMAGES: [],
  }
}

function storedSourceImage(
  source: GenerationSourceImageView,
): PersistedSourceImage {
  return {
    id: source.id,
    name: source.name,
    role: source.role,
    sourceType: source.sourceType,
    ...(source.productId ? { productId: source.productId } : {}),
    ...(source.productName ? { productName: source.productName } : {}),
  }
}

function restoredSourceImage(
  source: PersistedSourceImage,
): GenerationSourceImageView {
  return {
    ...source,
    previewUrl: getAssetContentUrl(source.id),
    thumbnailUrl: getAssetThumbnailUrl(source.id),
  }
}

function cloneInstantSubmission(
  submission: InstantSubmission,
): InstantSubmission {
  return {
    ...submission,
    product_asset_ids: [...submission.product_asset_ids],
    reference_asset_ids: [...submission.reference_asset_ids],
  }
}

function cloneBatchSubmission(submission: BatchSubmission): BatchSubmission {
  return {
    ...submission,
    selected_product_ids: [...submission.selected_product_ids],
    selected_template_group_ids: [...submission.selected_template_group_ids],
  }
}

export function aiWorkbenchSessionStorageKey(
  userId: string,
  teamId: string,
): string {
  return `${AI_WORKBENCH_SESSION_STORAGE_PREFIX}.${encodeURIComponent(userId)}.${encodeURIComponent(teamId)}`
}

function readLocalStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

function writeLocalStorage(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value)
  } catch {
    // Browser persistence is optional when storage is unavailable.
  }
}

function removeLocalStorage(key: string): void {
  try {
    window.localStorage.removeItem(key)
  } catch {
    // Browser persistence is optional when storage is unavailable.
  }
}

function readPersistedSession(key: string): PersistedSession | null {
  const raw = readLocalStorage(key)
  if (!raw) return null
  try {
    const parsed = persistedSessionSchema.safeParse(JSON.parse(raw))
    if (parsed.success) return parsed.data
  } catch {
    // Invalid local state is discarded below.
  }
  removeLocalStorage(key)
  return null
}

export const useAiWorkbenchSessionStore = defineStore(
  'ai-workbench-session',
  () => {
    const workMode = ref<GenerationWorkMode>('INSTANT')
    const outputCompressionEnabled = ref(false)

    const instantMode = ref<GenerationMode>('NORMAL_GENERATION')
    const instantSelectedModelId = ref<string | null>(null)
    const instantInputs = ref(emptyInputs())
    const instantAppliedTemplateId = ref<string | null>(null)
    const instantPrompt = ref('')
    const instantOutputFormat = ref<GenerationOutputFormat>('SINGLE')
    const instantSize = ref<GenerationSize>('1:1')
    const instantCount = ref(1)
    const instantCurrentJobId = ref<string | null>(null)
    const instantSubmitting = ref(false)
    const instantSubmissionKey = ref<string | null>(null)
    const instantSubmissionRecoveryError = ref<string | null>(null)
    const instantSubmissionIntent = ref<InstantSubmissionIntent | null>(null)

    const batchMode = ref<GenerationMode>('NORMAL_GENERATION')
    const batchSelectedModelId = ref<string | null>(null)
    const batchProductScope = ref<BatchProductScope>('ALL_ENABLED')
    const batchSelectedProductIds = ref<string[]>([])
    const batchTemplateSource = ref<BatchTemplateSource>('PRODUCT_CONFIGURED')
    const batchSelectedTemplateGroupIds = ref<string[]>([])
    const batchOutputRange = ref<GenerationOutputRange>('ALL')
    const batchChecked = ref(false)
    const batchCurrentJobId = ref<string | null>(null)
    const batchSubmitting = ref(false)
    const batchSubmissionKey = ref<string | null>(null)
    const batchSubmissionRecoveryError = ref<string | null>(null)
    const batchSubmissionIntent = ref<BatchSubmissionIntent | null>(null)

    const activeStorageKey = ref<string | null>(null)
    const hasActiveActorContext = computed(
      () => activeStorageKey.value !== null,
    )

    let actorContextVersion = 0
    let instantStateVersion = 0
    let batchStateVersion = 0
    let inFlightInstantSubmission: Promise<GenerationJobReadDto | null> | null =
      null
    let inFlightBatchSubmission: Promise<GenerationJobReadDto | null> | null =
      null

    function persistedSession(): PersistedSession {
      return {
        version: 2,
        workMode: workMode.value,
        outputCompressionEnabled: outputCompressionEnabled.value,
        instant: {
          mode: instantMode.value,
          selectedModelId: instantSelectedModelId.value,
          inputs: {
            PRODUCT_IMAGES:
              instantInputs.value.PRODUCT_IMAGES.map(storedSourceImage),
            REFERENCE_IMAGES:
              instantInputs.value.REFERENCE_IMAGES.map(storedSourceImage),
          },
          appliedTemplateId: instantAppliedTemplateId.value,
          prompt: instantPrompt.value,
          outputFormat: instantOutputFormat.value,
          size: instantSize.value,
          count: instantCount.value,
          currentJobId: instantCurrentJobId.value,
          submissionIntent: instantSubmissionIntent.value
            ? {
                submissionKey: instantSubmissionIntent.value.submissionKey,
                submission: cloneInstantSubmission(
                  instantSubmissionIntent.value.submission,
                ),
              }
            : null,
        },
        batch: {
          mode: batchMode.value,
          selectedModelId: batchSelectedModelId.value,
          productScope: batchProductScope.value,
          selectedProductIds: [...batchSelectedProductIds.value],
          templateSource: batchTemplateSource.value,
          selectedTemplateGroupIds: [...batchSelectedTemplateGroupIds.value],
          outputRange: batchOutputRange.value,
          checked: batchChecked.value,
          currentJobId: batchCurrentJobId.value,
          submissionIntent: batchSubmissionIntent.value
            ? {
                submissionKey: batchSubmissionIntent.value.submissionKey,
                submission: cloneBatchSubmission(
                  batchSubmissionIntent.value.submission,
                ),
              }
            : null,
        },
      }
    }

    function persistActiveState(): void {
      if (!activeStorageKey.value) return
      writeLocalStorage(
        activeStorageKey.value,
        JSON.stringify(persistedSession()),
      )
    }

    function resetInstantState(): void {
      instantMode.value = 'NORMAL_GENERATION'
      instantSelectedModelId.value = null
      instantInputs.value = emptyInputs()
      instantAppliedTemplateId.value = null
      instantPrompt.value = ''
      instantOutputFormat.value = 'SINGLE'
      instantSize.value = '1:1'
      instantCount.value = 1
      instantCurrentJobId.value = null
      instantSubmitting.value = false
      instantSubmissionKey.value = null
      instantSubmissionRecoveryError.value = null
      instantSubmissionIntent.value = null
    }

    function resetBatchState(): void {
      batchMode.value = 'NORMAL_GENERATION'
      batchSelectedModelId.value = null
      batchProductScope.value = 'ALL_ENABLED'
      batchSelectedProductIds.value = []
      batchTemplateSource.value = 'PRODUCT_CONFIGURED'
      batchSelectedTemplateGroupIds.value = []
      batchOutputRange.value = 'ALL'
      batchChecked.value = false
      batchCurrentJobId.value = null
      batchSubmitting.value = false
      batchSubmissionKey.value = null
      batchSubmissionRecoveryError.value = null
      batchSubmissionIntent.value = null
    }

    function invalidateRuntimeState(): void {
      actorContextVersion += 1
      instantStateVersion += 1
      batchStateVersion += 1
      inFlightInstantSubmission = null
      inFlightBatchSubmission = null
    }

    function resetAllState(): void {
      workMode.value = 'INSTANT'
      outputCompressionEnabled.value = false
      resetInstantState()
      resetBatchState()
    }

    function hydrate(session: PersistedSession): void {
      workMode.value = session.workMode
      outputCompressionEnabled.value = session.outputCompressionEnabled
      instantMode.value = session.instant.mode
      instantSelectedModelId.value = session.instant.selectedModelId
      instantInputs.value = {
        PRODUCT_IMAGES:
          session.instant.inputs.PRODUCT_IMAGES.map(restoredSourceImage),
        REFERENCE_IMAGES:
          session.instant.inputs.REFERENCE_IMAGES.map(restoredSourceImage),
      }
      instantAppliedTemplateId.value = session.instant.appliedTemplateId
      instantPrompt.value = session.instant.prompt
      instantOutputFormat.value = session.instant.outputFormat
      instantSize.value = session.instant.size
      instantCount.value = session.instant.count
      instantCurrentJobId.value = session.instant.currentJobId
      instantSubmissionIntent.value = session.instant.currentJobId
        ? null
        : session.instant.submissionIntent
      instantSubmissionKey.value =
        instantSubmissionIntent.value?.submissionKey ?? null
      instantSubmitting.value = false
      instantSubmissionRecoveryError.value = null

      batchMode.value = session.batch.mode
      batchSelectedModelId.value = session.batch.selectedModelId
      batchProductScope.value = session.batch.productScope
      batchSelectedProductIds.value = [...session.batch.selectedProductIds]
      batchTemplateSource.value = session.batch.templateSource
      batchSelectedTemplateGroupIds.value = [
        ...session.batch.selectedTemplateGroupIds,
      ]
      batchOutputRange.value = session.batch.outputRange
      batchChecked.value = session.batch.checked
      batchCurrentJobId.value = session.batch.currentJobId
      batchSubmissionIntent.value = session.batch.currentJobId
        ? null
        : session.batch.submissionIntent
      batchSubmissionKey.value =
        batchSubmissionIntent.value?.submissionKey ?? null
      batchSubmitting.value = false
      batchSubmissionRecoveryError.value = null
    }

    function executeInstantSubmission(
      intent: InstantSubmissionIntent,
    ): Promise<GenerationJobReadDto | null> {
      if (inFlightInstantSubmission) return inFlightInstantSubmission

      const contextVersion = actorContextVersion
      const stateVersion = instantStateVersion
      instantSubmitting.value = true
      instantSubmissionKey.value = intent.submissionKey
      instantSubmissionIntent.value = intent
      instantSubmissionRecoveryError.value = null
      persistActiveState()

      const request = aiWorkbenchApi.submitGeneration({
        work_mode: 'INSTANT',
        submission_key: intent.submissionKey,
        ...cloneInstantSubmission(intent.submission),
      })
      const pending = request
        .then((job) => {
          if (
            contextVersion !== actorContextVersion ||
            stateVersion !== instantStateVersion
          ) {
            return null
          }
          instantCurrentJobId.value = job.generation_job_id
          instantSubmissionIntent.value = null
          instantSubmissionKey.value = null
          instantSubmissionRecoveryError.value = null
          persistActiveState()
          return job
        })
        .catch((error: unknown) => {
          if (
            contextVersion !== actorContextVersion ||
            stateVersion !== instantStateVersion
          ) {
            return null
          }
          instantSubmissionRecoveryError.value = getErrorMessage(error)
          persistActiveState()
          throw error
        })
        .finally(() => {
          if (inFlightInstantSubmission !== pending) return
          inFlightInstantSubmission = null
          if (
            contextVersion !== actorContextVersion ||
            stateVersion !== instantStateVersion
          ) {
            return
          }
          instantSubmitting.value = false
        })

      inFlightInstantSubmission = pending
      return pending
    }

    function executeBatchSubmission(
      intent: BatchSubmissionIntent,
    ): Promise<GenerationJobReadDto | null> {
      if (inFlightBatchSubmission) return inFlightBatchSubmission

      const contextVersion = actorContextVersion
      const stateVersion = batchStateVersion
      batchSubmitting.value = true
      batchSubmissionKey.value = intent.submissionKey
      batchSubmissionIntent.value = intent
      batchSubmissionRecoveryError.value = null
      persistActiveState()

      const request = aiWorkbenchApi.submitGeneration({
        work_mode: 'BATCH',
        submission_key: intent.submissionKey,
        ...cloneBatchSubmission(intent.submission),
      })
      const pending = request
        .then((job) => {
          if (
            contextVersion !== actorContextVersion ||
            stateVersion !== batchStateVersion
          ) {
            return null
          }
          batchCurrentJobId.value = job.generation_job_id
          batchSubmissionIntent.value = null
          batchSubmissionKey.value = null
          batchSubmissionRecoveryError.value = null
          persistActiveState()
          return job
        })
        .catch((error: unknown) => {
          if (
            contextVersion !== actorContextVersion ||
            stateVersion !== batchStateVersion
          ) {
            return null
          }
          batchSubmissionRecoveryError.value = getErrorMessage(error)
          persistActiveState()
          throw error
        })
        .finally(() => {
          if (inFlightBatchSubmission !== pending) return
          inFlightBatchSubmission = null
          if (
            contextVersion !== actorContextVersion ||
            stateVersion !== batchStateVersion
          ) {
            return
          }
          batchSubmitting.value = false
        })

      inFlightBatchSubmission = pending
      return pending
    }

    function submitInstant(
      submission: InstantSubmission,
    ): Promise<GenerationJobReadDto | null> {
      if (inFlightInstantSubmission) return inFlightInstantSubmission
      const intent = instantSubmissionIntent.value ?? {
        submissionKey: crypto.randomUUID(),
        submission: cloneInstantSubmission(submission),
      }
      return executeInstantSubmission(intent)
    }

    function submitBatch(
      submission: BatchSubmission,
    ): Promise<GenerationJobReadDto | null> {
      if (inFlightBatchSubmission) return inFlightBatchSubmission
      const intent = batchSubmissionIntent.value ?? {
        submissionKey: crypto.randomUUID(),
        submission: cloneBatchSubmission(submission),
      }
      return executeBatchSubmission(intent)
    }

    function resumeInstantSubmission(): Promise<GenerationJobReadDto | null> {
      if (instantCurrentJobId.value || !instantSubmissionIntent.value) {
        return Promise.resolve(null)
      }
      return executeInstantSubmission(instantSubmissionIntent.value)
    }

    function resumeBatchSubmission(): Promise<GenerationJobReadDto | null> {
      if (batchCurrentJobId.value || !batchSubmissionIntent.value) {
        return Promise.resolve(null)
      }
      return executeBatchSubmission(batchSubmissionIntent.value)
    }

    async function resumePendingSubmissions(): Promise<void> {
      await Promise.allSettled([
        resumeInstantSubmission(),
        resumeBatchSubmission(),
      ])
    }

    function activateActorContext(context: ActorContextIdentity): void {
      const key = aiWorkbenchSessionStorageKey(context.userId, context.teamId)
      if (activeStorageKey.value === key) return

      activeStorageKey.value = null
      invalidateRuntimeState()
      resetAllState()
      const stored = readPersistedSession(key)
      if (stored) hydrate(stored)
      activeStorageKey.value = key
      writeLocalStorage(AI_WORKBENCH_ACTIVE_CONTEXT_STORAGE_KEY, key)
    }

    function clearActiveActorContext(): void {
      const key = activeStorageKey.value
      activeStorageKey.value = null
      invalidateRuntimeState()
      resetAllState()
      if (key) removeLocalStorage(key)
      if (readLocalStorage(AI_WORKBENCH_ACTIVE_CONTEXT_STORAGE_KEY) === key) {
        removeLocalStorage(AI_WORKBENCH_ACTIVE_CONTEXT_STORAGE_KEY)
      }
    }

    function replaceActorContext(context: ActorContextIdentity): void {
      const nextKey = aiWorkbenchSessionStorageKey(
        context.userId,
        context.teamId,
      )
      if (activeStorageKey.value === nextKey) return
      clearActiveActorContext()
      activateActorContext(context)
    }

    function clearLastPersistedActorContext(): void {
      const key = readLocalStorage(AI_WORKBENCH_ACTIVE_CONTEXT_STORAGE_KEY)
      if (
        key?.startsWith(`${AI_WORKBENCH_SESSION_STORAGE_PREFIX}.`) &&
        key !== AI_WORKBENCH_ACTIVE_CONTEXT_STORAGE_KEY
      ) {
        removeLocalStorage(key)
      }
      removeLocalStorage(AI_WORKBENCH_ACTIVE_CONTEXT_STORAGE_KEY)
      if (activeStorageKey.value === key) {
        activeStorageKey.value = null
        invalidateRuntimeState()
        resetAllState()
      }
    }

    function clearInstant(): string | null {
      const jobId = instantCurrentJobId.value
      instantStateVersion += 1
      inFlightInstantSubmission = null
      resetInstantState()
      persistActiveState()
      return jobId
    }

    function clearBatch(): string | null {
      const jobId = batchCurrentJobId.value
      batchStateVersion += 1
      inFlightBatchSubmission = null
      resetBatchState()
      persistActiveState()
      return jobId
    }

    watch(
      [
        workMode,
        outputCompressionEnabled,
        instantMode,
        instantSelectedModelId,
        instantInputs,
        instantAppliedTemplateId,
        instantPrompt,
        instantOutputFormat,
        instantSize,
        instantCount,
        instantCurrentJobId,
        instantSubmissionIntent,
        batchMode,
        batchSelectedModelId,
        batchProductScope,
        batchSelectedProductIds,
        batchTemplateSource,
        batchSelectedTemplateGroupIds,
        batchOutputRange,
        batchChecked,
        batchCurrentJobId,
        batchSubmissionIntent,
      ],
      persistActiveState,
      { deep: true, flush: 'sync' },
    )

    return {
      workMode,
      outputCompressionEnabled,
      instantMode,
      instantSelectedModelId,
      instantInputs,
      instantAppliedTemplateId,
      instantPrompt,
      instantOutputFormat,
      instantSize,
      instantCount,
      instantCurrentJobId,
      instantSubmitting,
      instantSubmissionKey,
      instantSubmissionRecoveryError,
      batchMode,
      batchSelectedModelId,
      batchProductScope,
      batchSelectedProductIds,
      batchTemplateSource,
      batchSelectedTemplateGroupIds,
      batchOutputRange,
      batchChecked,
      batchCurrentJobId,
      batchSubmitting,
      batchSubmissionKey,
      batchSubmissionRecoveryError,
      hasActiveActorContext,
      submitInstant,
      submitBatch,
      resumeInstantSubmission,
      resumeBatchSubmission,
      resumePendingSubmissions,
      activateActorContext,
      replaceActorContext,
      clearActiveActorContext,
      clearLastPersistedActorContext,
      clearInstant,
      clearBatch,
    }
  },
)
