<script setup lang="ts">
import { Sparkles } from '@lucide/vue'
import { useMessage } from 'naive-ui'
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'

import { AiWorkbenchLayout } from '@/features/ai-workbench'
import ContextSwitchBar from '@/shared/components/ContextSwitchBar.vue'
import { AppButton, AppInput, AppNumberInput, AppSelect } from '@/shared/ui'

import {
  GENERATION_MODE_ORDER,
  GENERATION_MODE_REGISTRY,
  type GenerationInputSlotDefinition,
} from '../model/generation-mode-registry'
import {
  GENERATION_OUTPUT_FORMAT_META,
  GENERATION_SIZE_OPTIONS,
  type GenerationExecutionResultView,
  type GenerationInputSlotKey,
  type GenerationMode,
  type GenerationOutputFormat,
  type GenerationSize,
  type GenerationSourceImageView,
} from '../model/types'
import { useAiGenerationStore } from '../model/useAiGenerationStore'
import GenerationAssetPickerDialog from './GenerationAssetPickerDialog.vue'
import GenerationInputSlot from './GenerationInputSlot.vue'
import GenerationOutputCompressionSetting from './GenerationOutputCompressionSetting.vue'
import InstantResultViewer from './InstantResultViewer.vue'

const VISUAL_MOCK_PENDING_COMPLETION_MS = 1600
const VISUAL_MOCK_RETRY_COMPLETION_MS = 360

const props = defineProps<{
  outputCompressionEnabled: boolean
}>()
const emit = defineEmits<{
  'update:outputCompressionEnabled': [value: boolean]
}>()

const generationStore = useAiGenerationStore()
const {
  instantDraft,
  instantExecution,
  products,
  instantTemplateGroups,
  instantModeDefinition,
  canGenerateInstant,
} = storeToRefs(generationStore)
const message = useMessage()

const assetPickerVisible = ref(false)
const assetPickerSlotKey = ref<GenerationInputSlotKey>('PRODUCT_IMAGES')

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
const sizeOptions = GENERATION_SIZE_OPTIONS.map((value) => ({
  label: value,
  value,
}))
const templateOptions = computed(() =>
  instantTemplateGroups.value.map((group) => ({
    type: 'group' as const,
    key: group.id,
    label: group.name,
    children: [...group.templates]
      .filter((template) => template.enabled)
      .sort((left, right) => left.sortOrder - right.sortOrder)
      .map((template) => ({ label: template.name, value: template.id })),
  })),
)
const assetPickerDefinition = computed(
  () =>
    instantModeDefinition.value.inputSlots.find(
      (slot) => slot.key === assetPickerSlotKey.value,
    ) ?? instantModeDefinition.value.inputSlots[0]!,
)

function openAssetPicker(slot: GenerationInputSlotDefinition): void {
  assetPickerSlotKey.value = slot.key
  assetPickerVisible.value = true
}

function selectAsset(source: GenerationSourceImageView): void {
  generationStore.addInstantSources(assetPickerSlotKey.value, [source])
}

function upload(slot: GenerationInputSlotDefinition, files: File[]): void {
  generationStore.addInstantUploadFiles(slot.key, files)
}

function setMode(value: string): void {
  generationStore.setInstantMode(value as GenerationMode)
}

function setOutputFormat(value: string): void {
  generationStore.updateInstantOutputFormat(value as GenerationOutputFormat)
}

function applyTemplate(value: string | number | null): void {
  generationStore.applyInstantTemplate(typeof value === 'string' ? value : null)
}

function setSize(value: string | number | null): void {
  if (value) generationStore.updateInstantSize(value as GenerationSize)
}

function generate(): void {
  const record = generationStore.generateInstant()
  const executionId = instantExecution.value?.id
  if (!record || !executionId) return
  message.success('生成任务已创建')
  window.setTimeout(() => {
    generationStore.completeInstantPendingResults(executionId)
  }, VISUAL_MOCK_PENDING_COMPLETION_MS)
}

function download(): void {
  message.success('下载任务已创建')
}

function retryResult(result: GenerationExecutionResultView): void {
  if (!generationStore.retryInstantResult(result.id)) return
  message.info('正在重试')
  window.setTimeout(() => {
    if (generationStore.completeInstantResult(result.id)) {
      message.success('重试成功')
    }
  }, VISUAL_MOCK_RETRY_COMPLETION_MS)
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
            :active-key="instantDraft.mode"
            :items="modeOptions"
            @select="setMode"
          />
        </header>

        <div class="instant-generation-pane__scroll">
          <GenerationInputSlot
            v-for="slot in instantModeDefinition.inputSlots"
            :key="slot.key"
            :definition="slot"
            :images="instantDraft.inputs[slot.key]"
            @upload="upload(slot, $event)"
            @select="openAssetPicker(slot)"
            @remove="generationStore.removeInstantSource(slot.key, $event)"
          />

          <section class="instant-generation-field">
            <strong>模板</strong>
            <AppSelect
              :model-value="instantDraft.appliedTemplate?.id ?? null"
              :options="templateOptions"
              clearable
              filterable
              placeholder="选择模板"
              aria-label="生成模板"
              @update:model-value="applyTemplate"
            />
          </section>

          <div
            class="instant-generation-config"
            data-testid="instant-generation-config"
          >
            <section class="instant-generation-field">
              <strong>提示词</strong>
              <AppInput
                :model-value="instantDraft.config.prompt"
                class="instant-generation-prompt"
                type="textarea"
                placeholder="请输入提示词"
                aria-label="提示词"
                @update:model-value="generationStore.updateInstantPrompt"
              />
            </section>

            <section class="instant-generation-field">
              <strong>输出格式</strong>
              <ContextSwitchBar
                label="输出格式"
                appearance="bare"
                :active-key="instantDraft.config.outputFormat"
                :items="outputFormatOptions"
                @select="setOutputFormat"
              />
            </section>

            <div class="instant-generation-parameters">
              <section class="instant-generation-field">
                <strong>比例</strong>
                <AppSelect
                  :model-value="instantDraft.config.size"
                  :options="sizeOptions"
                  aria-label="生成比例"
                  @update:model-value="setSize"
                />
              </section>
              <section class="instant-generation-field">
                <strong>数量</strong>
                <AppNumberInput
                  :model-value="instantDraft.config.count"
                  :min="1"
                  :max="8"
                  aria-label="生成数量"
                  @update:model-value="generationStore.updateInstantCount"
                />
              </section>
            </div>
            <GenerationOutputCompressionSetting
              :model-value="props.outputCompressionEnabled"
              @update:model-value="emit('update:outputCompressionEnabled', $event)"
            />
          </div>
        </div>

        <footer class="instant-generation-pane__footer">
          <AppButton
            block
            tone="primary"
            :disabled="!canGenerateInstant"
            @click="generate"
          >
            <Sparkles :size="16" />
            生成
          </AppButton>
        </footer>
      </div>
    </template>

    <template #workspace>
      <InstantResultViewer
        :execution="instantExecution"
        @download-all="download"
        @download="download"
        @retry="retryResult"
      />
    </template>
  </AiWorkbenchLayout>

  <GenerationAssetPickerDialog
    v-model:show="assetPickerVisible"
    :products="products"
    :role="assetPickerDefinition.acceptedMaterialRole"
    @confirm="selectAsset"
  />
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
  min-width: 0;
  min-height: 0;
  flex: 1;
  overflow-y: auto;
}

.instant-generation-pane__scroll {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  padding: var(--space-4) var(--space-1) var(--space-4) 0;
}

.instant-generation-pane__footer {
  flex: 0 0 auto;
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}

.instant-generation-field,
.instant-generation-config {
  display: flex;
  min-width: 0;
  flex-direction: column;
}

.instant-generation-field {
  gap: var(--space-2);
}

.instant-generation-config {
  gap: var(--space-5);
}

.instant-generation-field__header {
  display: flex;
  min-width: 0;
  min-height: var(--control-height-default);
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.instant-generation-field > strong,
.instant-generation-field__header > strong {
  color: var(--text-primary);
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-medium);
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
