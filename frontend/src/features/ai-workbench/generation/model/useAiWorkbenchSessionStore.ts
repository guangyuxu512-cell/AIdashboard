import { defineStore } from 'pinia'
import { ref } from 'vue'

import {
  aiWorkbenchApi,
  type BatchGenerationSubmitDto,
  type GenerationJobReadDto,
  type InstantGenerationSubmitDto,
} from '@/entities/ai-workbench'

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

function emptyInputs(): Record<
  GenerationInputSlotKey,
  GenerationSourceImageView[]
> {
  return {
    PRODUCT_IMAGES: [],
    REFERENCE_IMAGES: [],
  }
}

export const useAiWorkbenchSessionStore = defineStore(
  'ai-workbench-session',
  () => {
    const workMode = ref<GenerationWorkMode>('INSTANT')

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

    let actorContextVersion = 0
    let pendingInstantSubmission: Promise<GenerationJobReadDto | null> | null =
      null
    let pendingBatchSubmission: Promise<GenerationJobReadDto | null> | null =
      null

    function submitInstant(
      submission: InstantSubmission,
    ): Promise<GenerationJobReadDto | null> {
      if (pendingInstantSubmission) return pendingInstantSubmission

      const contextVersion = actorContextVersion
      const submissionKey = crypto.randomUUID()
      instantSubmitting.value = true
      instantSubmissionKey.value = submissionKey

      const request = aiWorkbenchApi.submitGeneration({
        work_mode: 'INSTANT',
        submission_key: submissionKey,
        ...submission,
      })
      const pending = request
        .then((job) => {
          if (contextVersion !== actorContextVersion) return null
          instantCurrentJobId.value = job.generation_job_id
          return job
        })
        .catch((error: unknown) => {
          if (contextVersion !== actorContextVersion) return null
          throw error
        })
        .finally(() => {
          if (pendingInstantSubmission !== pending) return
          pendingInstantSubmission = null
          if (contextVersion !== actorContextVersion) return
          instantSubmitting.value = false
          instantSubmissionKey.value = null
        })

      pendingInstantSubmission = pending
      return pending
    }

    function submitBatch(
      submission: BatchSubmission,
    ): Promise<GenerationJobReadDto | null> {
      if (pendingBatchSubmission) return pendingBatchSubmission

      const contextVersion = actorContextVersion
      const submissionKey = crypto.randomUUID()
      batchSubmitting.value = true
      batchSubmissionKey.value = submissionKey

      const request = aiWorkbenchApi.submitGeneration({
        work_mode: 'BATCH',
        submission_key: submissionKey,
        ...submission,
      })
      const pending = request
        .then((job) => {
          if (contextVersion !== actorContextVersion) return null
          batchCurrentJobId.value = job.generation_job_id
          return job
        })
        .catch((error: unknown) => {
          if (contextVersion !== actorContextVersion) return null
          throw error
        })
        .finally(() => {
          if (pendingBatchSubmission !== pending) return
          pendingBatchSubmission = null
          if (contextVersion !== actorContextVersion) return
          batchSubmitting.value = false
          batchSubmissionKey.value = null
        })

      pendingBatchSubmission = pending
      return pending
    }

    function resetForActorContextChange(): void {
      actorContextVersion += 1
      pendingInstantSubmission = null
      pendingBatchSubmission = null

      workMode.value = 'INSTANT'

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
    }

    return {
      workMode,
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
      submitInstant,
      submitBatch,
      resetForActorContextChange,
    }
  },
)
