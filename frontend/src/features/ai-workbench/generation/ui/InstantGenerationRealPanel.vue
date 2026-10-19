<script setup lang="ts">
import { useQueryClient } from '@tanstack/vue-query'
import { Sparkles, Trash2 } from '@lucide/vue'
import { useMessage } from 'naive-ui'
import { storeToRefs } from 'pinia'
import { computed, ref, watch } from 'vue'

import {
  aiAssetApi,
  getAiAssetContentUrl as getAssetContentUrl,
  getAiAssetThumbnailUrl as getAssetThumbnailUrl,
} from '@/entities/ai-workbench/api/ai-asset-api'
import { formatAssetOperationFailure } from '@/entities/asset/api/asset-api'
import {
  AssetDownloadStatusBar,
  AssetPreviewDialog,
  formatAssetDownloadFailure,
  useAssetDownloadQueue,
} from '@/entities/asset'
import {
  aiWorkbenchApi,
  aiWorkbenchQueryKeys,
  useGenerationJobQuery,
} from '@/entities/ai-workbench'
import type { GenerationJobReadDto } from '@/entities/ai-workbench'
import { AiWorkbenchLayout } from '@/features/ai-workbench'
import { getErrorMessage } from '@/shared/api'
import ContextSwitchBar from '@/shared/components/ContextSwitchBar.vue'
import ErrorState from '@/shared/components/ErrorState.vue'
import LoadingState from '@/shared/components/LoadingState.vue'
import {
  AppButton,
  AppDialog,
  AppInput,
  AppNumberInput,
  AppSelect,
} from '@/shared/ui'

import {
  GENERATION_MODE_ORDER,
  GENERATION_MODE_REGISTRY,
  type GenerationInputSlotDefinition,
} from '../model/generation-mode-registry'
import {
  GENERATION_OUTPUT_FORMAT_META,
  type GenerationExecutionResultView,
  type GenerationInputSlotKey,
  type GenerationOutputFormat,
  type GenerationProductView,
  type GenerationSize,
  type GenerationSourceImageView,
  type GenerationTemplateGroupView,
} from '../model/types'
import { toGenerationAssetDownloadRequests } from '../model/download'
import { useAiWorkbenchSessionStore } from '../model/useAiWorkbenchSessionStore'
import type { WorkbenchModelView } from '../../real-api/model/mappers'
import { mapInstantExecution } from '../../real-api/model/mappers'
import {
  compatibleWorkbenchModels,
  isWorkbenchModelInputCountAllowed,
  isWorkbenchModelSizeSupported,
  remainingWorkbenchModelInputCapacity,
  resolveWorkbenchModelId,
} from '../../real-api/model/model-selection'
import GenerationAssetPickerDialog from './GenerationAssetPickerDialog.vue'
import GenerationInputSlot from './GenerationInputSlot.vue'
import GenerationOutputCompressionSetting from './GenerationOutputCompressionSetting.vue'
import InstantResultViewer from './InstantResultViewer.vue'

const props = defineProps<{
  models: WorkbenchModelView[]
  products: GenerationProductView[]
  templateGroups: GenerationTemplateGroupView[]
}>()

const message = useMessage()
const queryClient = useQueryClient()
const downloads = useAssetDownloadQueue()
const sessionStore = useAiWorkbenchSessionStore()
const {
  instantMode: mode,
  instantSelectedModelId: selectedModelId,
  instantInputs: inputs,
  instantAppliedTemplateId: appliedTemplateId,
  instantPrompt: prompt,
  instantOutputFormat: outputFormat,
  outputCompressionEnabled,
  instantSize: size,
  instantCount: count,
  instantCurrentJobId: currentJobId,
  instantSubmitting: submitting,
  instantSubmissionKey: submissionKey,
  instantSubmissionRecoveryError: submissionRecoveryError,
} = storeToRefs(sessionStore)
const assetPickerVisible = ref(false)
const assetPickerSlotKey = ref<GenerationInputSlotKey>('PRODUCT_IMAGES')
const clearDialogVisible = ref(false)
const previewResultId = ref<string | null>(null)
const pendingUploadCount = ref(0)

const jobQuery = useGenerationJobQuery(currentJobId, { poll: true })

const modeDefinition = computed(() => GENERATION_MODE_REGISTRY[mode.value])
const compatibleModels = computed(() =>
  compatibleWorkbenchModels(props.models, mode.value),
)
const selectedModel = computed(
  () =>
    compatibleModels.value.find(
      (model) => model.id === selectedModelId.value,
    ) ?? null,
)
const modelOptions = computed(() =>
  compatibleModels.value.map((model) => ({
    label: model.name,
    value: model.id,
  })),
)
const sizeOptions = computed(() =>
  (selectedModel.value?.supportedSizes ?? []).map((value) => ({
    label: value,
    value,
  })),
)
const currentInputCount = computed(
  () =>
    inputs.value.PRODUCT_IMAGES.length + inputs.value.REFERENCE_IMAGES.length,
)
const hasInputLimitViolation = computed(
  () =>
    selectedModel.value !== null &&
    !isWorkbenchModelInputCountAllowed(
      selectedModel.value,
      currentInputCount.value,
    ),
)
const remainingInputCount = computed(() =>
  remainingWorkbenchModelInputCapacity(
    selectedModel.value,
    currentInputCount.value,
  ),
)
const templateGroups = computed(() =>
  props.templateGroups.filter(
    (group) => group.mode === mode.value && group.enabled,
  ),
)
const templateOptions = computed(() =>
  templateGroups.value.map((group) => ({
    type: 'group' as const,
    key: group.id,
    label: group.name,
    children: group.templates
      .filter((template) => template.enabled)
      .sort((left, right) => left.sortOrder - right.sortOrder)
      .map((template) => ({ label: template.name, value: template.id })),
  })),
)
const assetPickerDefinition = computed(
  () =>
    modeDefinition.value.inputSlots.find(
      (slot) => slot.key === assetPickerSlotKey.value,
    ) ?? modeDefinition.value.inputSlots[0]!,
)
const execution = computed(() =>
  jobQuery.data.value ? mapInstantExecution(jobQuery.data.value) : null,
)
const previewSources = computed(() =>
  (execution.value?.results ?? [])
    .filter(
      (result) => result.status === 'SUCCESS' && Boolean(result.previewUrl),
    )
    .map((result) => ({
      id: result.id,
      name: result.name ?? `生成结果 ${result.slotIndex + 1}`,
      contentUrl: result.previewUrl!,
    })),
)
const jobError = computed(() => jobQuery.error.value)
const restoringJob = computed(
  () => Boolean(currentJobId.value) && jobQuery.isPending.value,
)
const restoringSubmission = computed(
  () => !currentJobId.value && Boolean(submissionKey.value) && submitting.value,
)
const currentJobIsActive = computed(() => {
  const status = jobQuery.data.value?.status
  return (
    status === 'PENDING' ||
    status === 'RUNNING' ||
    (!currentJobId.value && Boolean(submissionKey.value))
  )
})
const canGenerate = computed(
  () =>
    Boolean(selectedModel.value) &&
    prompt.value.trim().length > 0 &&
    inputs.value.PRODUCT_IMAGES.length > 0 &&
    (mode.value === 'NORMAL_GENERATION' ||
      inputs.value.REFERENCE_IMAGES.length > 0) &&
    isWorkbenchModelInputCountAllowed(
      selectedModel.value,
      currentInputCount.value,
    ) &&
    isWorkbenchModelSizeSupported(selectedModel.value, size.value) &&
    !submitting.value &&
    !submissionKey.value,
)
const modeOptions = GENERATION_MODE_ORDER.map((value) => ({
  label: GENERATION_MODE_REGISTRY[value].label,
  key: value,
}))
const outputFormatOptions = [
  { label: GENERATION_OUTPUT_FORMAT_META.SINGLE.label, key: 'SINGLE' },
  {
    label: GENERATION_OUTPUT_FORMAT_META.COLLAGE_2X2.label,
    key: 'COLLAGE_2X2',
  },
]

watch(
  compatibleModels,
  (models) => {
    selectedModelId.value = resolveWorkbenchModelId(
      models,
      mode.value,
      selectedModelId.value,
    )
  },
  { immediate: true },
)
watch(selectedModel, (model) => {
  if (model && !isWorkbenchModelSizeSupported(model, size.value)) {
    size.value = model.supportedSizes[0] ?? '1:1'
  }
})

function setJob(job: GenerationJobReadDto): void {
  currentJobId.value = job.generation_job_id
  queryClient.setQueryData(
    aiWorkbenchQueryKeys.generationJob(job.generation_job_id),
    job,
  )
  void queryClient.invalidateQueries({
    queryKey: aiWorkbenchQueryKeys.generations,
  })
}

function setMode(value: string): void {
  if (value !== 'NORMAL_GENERATION' && value !== 'STYLE_REPLICATION') return
  mode.value = value
  inputs.value.REFERENCE_IMAGES = []
  appliedTemplateId.value = null
}

function modelCapabilityMessage(): string {
  if (selectedModel.value === null) {
    return '模型能力正在加载，请稍后再试'
  }
  return `实际输入 ${currentInputCount.value} 张，模型最多 ${selectedModel.value.maxInputImages} 张`
}

function openAssetPicker(slot: GenerationInputSlotDefinition): void {
  if (selectedModel.value === null || remainingInputCount.value === null) {
    message.warning(modelCapabilityMessage())
    return
  }
  if (remainingInputCount.value === 0) {
    message.warning(modelCapabilityMessage())
    return
  }
  assetPickerSlotKey.value = slot.key
  assetPickerVisible.value = true
}

function addSources(
  slotKey: GenerationInputSlotKey,
  sources: GenerationSourceImageView[],
): boolean {
  if (selectedModel.value === null || remainingInputCount.value === null) {
    message.warning(modelCapabilityMessage())
    return false
  }
  const existing = new Set(inputs.value[slotKey].map((image) => image.id))
  const additions = sources.filter((source) => !existing.has(source.id))
  if (additions.length > remainingInputCount.value) {
    message.warning(
      `实际输入 ${currentInputCount.value + additions.length} 张，模型最多 ${selectedModel.value.maxInputImages} 张`,
    )
    return false
  }
  inputs.value[slotKey] = [...inputs.value[slotKey], ...additions]
  return true
}

function selectAsset(source: GenerationSourceImageView): void {
  addSources(assetPickerSlotKey.value, [source])
}

function upload(slot: GenerationInputSlotDefinition, files: File[]): void {
  if (!files.length) return
  if (selectedModel.value === null || remainingInputCount.value === null) {
    message.warning(modelCapabilityMessage())
    return
  }
  const availableCapacity = remainingInputCount.value - pendingUploadCount.value
  if (files.length > availableCapacity) {
    message.warning(
      `实际输入 ${currentInputCount.value + pendingUploadCount.value + files.length} 张，模型最多 ${selectedModel.value.maxInputImages} 张`,
    )
    return
  }
  pendingUploadCount.value += files.length
  const originalInputs = inputs.value
  void Promise.allSettled(files.map(aiAssetApi.upload))
    .then((results) => {
      // Actor/context recovery replaces this object; do not save old uploads
      // into another user's or Team's draft after a context change.
      if (inputs.value !== originalInputs) return
      const assets = results.flatMap((result) =>
        result.status === 'fulfilled' ? [result.value] : [],
      )
      results.forEach((result, index) => {
        if (result.status === 'rejected') {
          message.error(
            formatAssetOperationFailure(
              result.reason,
              `上传 ${files[index]!.name}`,
            ),
          )
        }
      })
      if (!assets.length) return
      const added = addSources(
        slot.key,
        assets.map((asset) => ({
          id: asset.asset_id,
          name: asset.original_filename,
          previewUrl: getAssetContentUrl(asset.asset_id),
          thumbnailUrl: getAssetThumbnailUrl(asset.asset_id),
          role: slot.acceptedMaterialRole,
          sourceType: 'LOCAL_UPLOAD',
        })),
      )
      if (added) message.success('图片已上传')
    })
    .catch((error) => message.error(formatAssetOperationFailure(error)))
    .finally(() => {
      pendingUploadCount.value -= files.length
    })
}

function removeSource(slotKey: GenerationInputSlotKey, sourceId: string): void {
  inputs.value[slotKey] = inputs.value[slotKey].filter(
    (source) => source.id !== sourceId,
  )
}

function applyTemplate(value: string | number | null): void {
  const id = typeof value === 'string' ? value : null
  appliedTemplateId.value = id
  const template = templateGroups.value
    .flatMap((group) => group.templates)
    .find((item) => item.id === id)
  if (!template) return
  prompt.value = template.prompt
  outputFormat.value = template.outputFormat
  count.value = template.count
  if (isWorkbenchModelSizeSupported(selectedModel.value, template.size)) {
    size.value = template.size
  }
}

function setSize(value: string | number | null): void {
  if (
    isWorkbenchModelSizeSupported(selectedModel.value, value as GenerationSize)
  ) {
    size.value = value as GenerationSize
  }
}

async function generate(): Promise<void> {
  if (!canGenerate.value) return
  try {
    const job = await sessionStore.submitInstant({
      model_id: selectedModelId.value!,
      mode: mode.value,
      product_asset_ids: inputs.value.PRODUCT_IMAGES.map((image) => image.id),
      reference_asset_ids: inputs.value.REFERENCE_IMAGES.map(
        (image) => image.id,
      ),
      prompt_template_id: appliedTemplateId.value,
      prompt: prompt.value.trim(),
      output_format: outputFormat.value,
      size: size.value,
      count: count.value,
      compress_output_under_1000kb: outputCompressionEnabled.value,
    })
    if (!job) return
    setJob(job)
    message.success('生成任务已创建')
  } catch (error) {
    message.error(getErrorMessage(error))
  }
}

function reloadJob(): void {
  void jobQuery.refetch()
}

function retrySubmissionRecovery(): void {
  void sessionStore
    .resumeInstantSubmission()
    .catch((error) => message.error(getErrorMessage(error)))
}

function clearCurrentTask(): void {
  const clearedJobId = sessionStore.clearInstant()
  clearDialogVisible.value = false
  if (clearedJobId) {
    const queryKey = aiWorkbenchQueryKeys.generationJob(clearedJobId)
    void queryClient
      .cancelQueries({ queryKey, exact: true })
      .finally(() => queryClient.removeQueries({ queryKey, exact: true }))
  }
  message.success('已清空当前即时生成')
}

function beginDownload(
  results: readonly GenerationExecutionResultView[],
): void {
  if (downloads.isDownloading.value) return
  const requests = toGenerationAssetDownloadRequests(results)
  void downloads.start(requests).then((summary) => {
    if (!summary) return
    if (summary.succeeded)
      message.success(`已开始下载 ${summary.succeeded} 张图片`)
    if (summary.failed) {
      const firstFailure = summary.results.find(
        (result) => result.failure,
      )?.failure
      if (firstFailure) message.error(formatAssetDownloadFailure(firstFailure))
    }
  })
}

function downloadResult(result: GenerationExecutionResultView): void {
  beginDownload([result])
}

function previewResult(result: GenerationExecutionResultView): void {
  if (result.status !== 'SUCCESS' || !result.previewUrl) return
  previewResultId.value = result.id
}

function downloadPreviewResult(source: { id: string }): void {
  const result = execution.value?.results.find((item) => item.id === source.id)
  if (result) downloadResult(result)
}

function setPreviewVisible(visible: boolean): void {
  if (!visible) previewResultId.value = null
}

function downloadAll(): void {
  const results =
    execution.value?.results.filter((result) => result.status === 'SUCCESS') ??
    []
  beginDownload(results)
}

function retryFailedDownloads(): void {
  void downloads.retryFailed().then((summary) => {
    if (!summary) return
    if (summary.succeeded)
      message.success(`已重新下载 ${summary.succeeded} 张图片`)
    if (summary.failed) {
      const firstFailure = summary.results.find(
        (result) => result.failure,
      )?.failure
      if (firstFailure) message.error(formatAssetDownloadFailure(firstFailure))
    }
  })
}

function retryResult(result: GenerationExecutionResultView): void {
  const jobId = currentJobId.value
  const item = jobQuery.data.value?.items.find(
    (candidate) => candidate.generation_item_id === result.id,
  )
  if (!jobId || !item || item.status !== 'FAILED') return
  void aiWorkbenchApi
    .retryGenerationItems(jobId, {
      items: [
        {
          item_id: item.generation_item_id,
          expected_attempt_count: item.attempt_count,
        },
      ],
    })
    .then((job) => {
      setJob(job)
      message.success('失败项已重试')
    })
    .catch((error) => message.error(getErrorMessage(error)))
}
</script>

<template>
  <AiWorkbenchLayout
    label="即时生成工作台"
    operation-label="即时生成配置"
    workspace-label="即时生成结果"
  >
    <template #operation>
      <div class="instant-generation-pane">
        <header class="instant-generation-pane__header">
          <h2>生成配置</h2>
          <ContextSwitchBar
            label="生成模式"
            appearance="bare"
            :active-key="mode"
            :items="modeOptions"
            @select="setMode"
          />
        </header>
        <div class="instant-generation-pane__scroll">
          <section class="instant-generation-field">
            <strong>模型</strong>
            <AppSelect
              v-model="selectedModelId"
              :options="modelOptions"
              placeholder="选择模型"
              aria-label="生成模型"
            />
            <span v-if="selectedModel" class="instant-generation-field__hint">
              最多 {{ selectedModel.maxInputImages }} 张输入图
            </span>
            <span
              v-if="hasInputLimitViolation"
              class="instant-generation-field__hint instant-generation-field__hint--error"
            >
              实际输入 {{ currentInputCount }} 张，模型最多
              {{ selectedModel?.maxInputImages }} 张
            </span>
          </section>

          <GenerationInputSlot
            v-for="slot in modeDefinition.inputSlots"
            :key="slot.key"
            :definition="slot"
            :images="inputs[slot.key]"
            @upload="upload(slot, $event)"
            @select="openAssetPicker(slot)"
            @remove="removeSource(slot.key, $event)"
          />

          <section class="instant-generation-field">
            <strong>模板</strong>
            <AppSelect
              :model-value="appliedTemplateId"
              :options="templateOptions"
              clearable
              filterable
              placeholder="选择模板"
              aria-label="生成模板"
              @update:model-value="applyTemplate"
            />
          </section>
          <section class="instant-generation-field">
            <strong>提示词</strong>
            <AppInput
              v-model="prompt"
              class="instant-generation-prompt"
              type="textarea"
              placeholder="请输入提示词"
              aria-label="提示词"
            />
          </section>
          <section class="instant-generation-field">
            <strong>输出格式</strong>
            <ContextSwitchBar
              label="输出格式"
              appearance="bare"
              :active-key="outputFormat"
              :items="outputFormatOptions"
              @select="outputFormat = $event as GenerationOutputFormat"
            />
          </section>
          <section class="instant-generation-field">
            <GenerationOutputCompressionSetting
              v-model="outputCompressionEnabled"
            />
          </section>
          <div class="instant-generation-parameters">
            <section class="instant-generation-field">
              <strong>比例</strong>
              <AppSelect
                :model-value="size"
                :options="sizeOptions"
                aria-label="生成比例"
                @update:model-value="setSize"
              />
            </section>
            <section class="instant-generation-field">
              <strong>数量</strong>
              <AppNumberInput
                v-model="count"
                :min="1"
                :max="8"
                aria-label="生成数量"
              />
            </section>
          </div>
        </div>
        <footer class="instant-generation-pane__footer">
          <AppButton @click="clearDialogVisible = true">
            <Trash2 :size="15" />
            清空当前任务
          </AppButton>
          <AppButton
            class="instant-generation-pane__generate"
            tone="primary"
            :disabled="!canGenerate"
            @click="generate"
          >
            <Sparkles :size="16" />
            生成
          </AppButton>
        </footer>
      </div>
    </template>

    <template #workspace>
      <ErrorState
        v-if="jobError"
        title="任务读取失败"
        :description="getErrorMessage(jobError)"
        retryable
        @retry="reloadJob"
      />
      <LoadingState v-else-if="restoringJob" description="正在恢复生成任务" />
      <LoadingState
        v-else-if="restoringSubmission"
        description="正在恢复生成任务回执"
      />
      <ErrorState
        v-else-if="submissionRecoveryError"
        title="任务回执恢复失败"
        :description="submissionRecoveryError"
        retryable
        @retry="retrySubmissionRecovery"
      />
      <InstantResultViewer
        v-else
        :execution="execution"
        @download-all="downloadAll"
        @download="downloadResult"
        @retry="retryResult"
        @preview="previewResult"
      />
      <AssetDownloadStatusBar
        :is-downloading="downloads.isDownloading.value"
        :progress-label="downloads.progressLabel.value"
        :failed-count="downloads.failedRequests.value.length"
        @cancel="downloads.cancel"
        @retry-failed="retryFailedDownloads"
      />
    </template>
  </AiWorkbenchLayout>

  <GenerationAssetPickerDialog
    v-model:show="assetPickerVisible"
    :products="products"
    :role="assetPickerDefinition.acceptedMaterialRole"
    @confirm="selectAsset"
  />
  <AssetPreviewDialog
    :show="Boolean(previewResultId)"
    :items="previewSources"
    :selected-asset-id="previewResultId"
    @update:show="setPreviewVisible"
    @download="downloadPreviewResult"
  />
  <AppDialog
    v-model:show="clearDialogVisible"
    title="清空当前任务"
    size="sm"
    positive-text="清空"
    @confirm="clearCurrentTask"
  >
    <p>将清空当前即时生成的草稿、任务引用和本地结果展示。</p>
    <p v-if="currentJobIsActive">
      运行中的后台任务不会取消，仍可在生成记录中查看。
    </p>
    <p v-else>生成记录、素材和文件不会被删除。</p>
  </AppDialog>
</template>

<style scoped>
.instant-generation-pane {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}

.instant-generation-pane__header {
  display: flex;
  min-width: 0;
  flex: 0 0 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
}

.instant-generation-pane__header h2 {
  margin: 0;
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
}

.instant-generation-pane__scroll {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: var(--space-5);
  padding: var(--space-4) var(--space-1) var(--space-4) 0;
  overflow-y: auto;
}

.instant-generation-pane__footer {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex: 0 0 auto;
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}

.instant-generation-pane__generate {
  min-width: 0;
  flex: 1;
}

.instant-generation-field {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-2);
}

.instant-generation-field > strong {
  color: var(--text-primary);
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-medium);
}

.instant-generation-field__hint {
  color: var(--text-tertiary);
  font-size: var(--font-size-secondary);
}

.instant-generation-field__hint--error {
  color: var(--status-danger);
}

.instant-generation-prompt {
  min-height: calc(var(--control-height-large) * 3);
}

.instant-generation-parameters {
  display: grid;
  min-width: 0;
  gap: var(--space-3);
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

@media (max-width: 1100px) {
  .instant-generation-pane__scroll {
    overflow-y: visible;
  }
}
</style>
