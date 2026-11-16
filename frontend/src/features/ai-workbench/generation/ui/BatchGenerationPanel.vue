<script setup lang="ts">
import { CheckCircle2, Folder, Play } from '@lucide/vue'
import { useMessage } from 'naive-ui'
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'

import { AiWorkbenchLayout } from '@/features/ai-workbench'
import CompactEntityRow from '@/shared/components/CompactEntityRow.vue'
import ContextSwitchBar from '@/shared/components/ContextSwitchBar.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import { AppButton, AppDialog, AppSelect } from '@/shared/ui'

import type { BatchTemplateExecutionIdentity } from '../model/batch-execution'
import {
  GENERATION_MODE_ORDER,
  GENERATION_MODE_REGISTRY,
} from '../model/generation-mode-registry'
import {
  BATCH_SKIP_REASON_META,
  GENERATION_OUTPUT_RANGE_META,
  type BatchTemplateExecutionView,
  type BatchProductScope,
  type BatchTemplateSource,
  type GenerationMode,
  type GenerationOutputRange,
} from '../model/types'
import { countGenerationProductSourceAssets } from '../model/product-source-assets'
import { useAiGenerationStore } from '../model/useAiGenerationStore'
import BatchExecutionViewer from './BatchExecutionViewer.vue'
import BatchProductPickerDialog from './BatchProductPickerDialog.vue'
import GenerationOutputCompressionSetting from './GenerationOutputCompressionSetting.vue'

const props = defineProps<{
  outputCompressionEnabled: boolean
}>()
const emit = defineEmits<{
  'update:outputCompressionEnabled': [value: boolean]
}>()

const generationStore = useAiGenerationStore()
const {
  batchDraft,
  batchExecution,
  batchChecked,
  batchPreflight,
  batchScopedProducts,
  products,
  availableBatchTemplateGroups,
} = storeToRefs(generationStore)
const message = useMessage()
const productPickerVisible = ref(false)
const preflightProblemsVisible = ref(false)

const modeOptions = GENERATION_MODE_ORDER.map((key) => ({
  label: GENERATION_MODE_REGISTRY[key].label,
  key,
}))
const productScopeOptions = [
  { label: '所有已启用产品', key: 'ALL_ENABLED' },
  { label: '选择产品', key: 'SELECTED' },
]
const templateSourceOptions = [
  { label: '产品已配置', key: 'PRODUCT_CONFIGURED' },
  { label: '本次选择', key: 'CURRENT_SELECTION' },
]
const outputRangeOptions = [
  { label: GENERATION_OUTPUT_RANGE_META.ALL.label, key: 'ALL' },
  {
    label: GENERATION_OUTPUT_RANGE_META.MAIN_IMAGE.label,
    key: 'MAIN_IMAGE',
  },
  {
    label: GENERATION_OUTPUT_RANGE_META.DETAIL_IMAGE.label,
    key: 'DETAIL_IMAGE',
  },
]
const templateGroupOptions = computed(() =>
  availableBatchTemplateGroups.value.map((group) => ({
    label: group.name,
    value: group.id,
    disabled: !group.enabled,
  })),
)
const selectableProducts = computed(() =>
  products.value.filter((product) => product.enabled),
)

function setMode(value: string): void {
  generationStore.setBatchMode(value as GenerationMode)
}

function setProductScope(value: string): void {
  generationStore.setBatchProductScope(value as BatchProductScope)
  if (value === 'SELECTED') productPickerVisible.value = true
}

function setTemplateSource(value: string): void {
  generationStore.setBatchTemplateSource(value as BatchTemplateSource)
}

function setOutputRange(value: string): void {
  generationStore.setBatchOutputRange(value as GenerationOutputRange)
}

function setSelectedTemplateGroups(values: Array<string | number>): void {
  generationStore.setBatchSelectedTemplateGroups(
    values.filter((value): value is string => typeof value === 'string'),
  )
}

function clearProducts(): void {
  generationStore.setBatchSelectedProducts([])
}

function clearTemplates(): void {
  generationStore.setBatchSelectedTemplateGroups([])
}

function openProductPicker(): void {
  if (batchDraft.value.productScope === 'SELECTED') {
    productPickerVisible.value = true
  }
}

function start(): void {
  if (generationStore.startBatchGeneration()) message.success('批量生成已创建')
}

function download(): void {
  message.success('下载任务已创建')
}

function downloadTemplate(template: BatchTemplateExecutionView): void {
  message.success(`${template.templateName} 下载任务已创建`)
}

function retryTemplate(identity: BatchTemplateExecutionIdentity): void {
  if (generationStore.retryBatchTemplate(identity)) {
    message.success('失败项已重新生成')
  }
}
</script>

<template>
  <AiWorkbenchLayout
    label="批量生成工作台"
    operation-label="批量生成配置"
    workspace-label="批量执行结果"
  >
    <template #operation>
      <div class="batch-generation-pane">
        <header class="batch-generation-pane__header">
          <h2>批量配置</h2>
          <ContextSwitchBar
            label="批量生成模式"
            appearance="bare"
            :active-key="batchDraft.mode"
            :items="modeOptions"
            @select="setMode"
          />
        </header>
        <div class="batch-generation-pane__scroll">
          <section class="batch-generation-field">
            <strong>产品范围</strong>
            <ContextSwitchBar
              label="产品范围"
              appearance="bare"
              :active-key="batchDraft.productScope"
              :items="productScopeOptions"
              @select="setProductScope"
            />
            <div class="batch-generation-field__header">
              <span>当前产品</span>
              <AppButton
                v-if="
                  batchDraft.productScope === 'SELECTED' &&
                  batchDraft.selectedProductIds.length
                "
                tone="text"
                @click="clearProducts"
              >
                清空
              </AppButton>
            </div>
            <div
              class="batch-generation-product-list"
              data-testid="batch-product-list"
            >
              <EmptyState
                v-if="batchScopedProducts.length === 0"
                description="暂无产品"
              />
              <CompactEntityRow
                v-for="product in batchScopedProducts"
                v-else
                :key="product.id"
                :title="product.name"
                :count="`商品原图 ${countGenerationProductSourceAssets(product)}`"
                :select-label="`查看产品 ${product.name}`"
                @select="openProductPicker"
              >
                <template #icon><Folder :size="16" /></template>
              </CompactEntityRow>
            </div>
          </section>

          <section class="batch-generation-field">
            <strong>模板来源</strong>
            <ContextSwitchBar
              label="模板来源"
              appearance="bare"
              :active-key="batchDraft.templateSource"
              :items="templateSourceOptions"
              @select="setTemplateSource"
            />
            <div
              v-if="batchDraft.templateSource === 'CURRENT_SELECTION'"
              class="batch-generation-field__header"
            >
              <span>本次模板</span>
              <AppButton
                v-if="batchDraft.selectedTemplateGroupIds.length"
                tone="text"
                @click="clearTemplates"
              >
                清空
              </AppButton>
            </div>
            <AppSelect
              v-if="batchDraft.templateSource === 'CURRENT_SELECTION'"
              :model-value="batchDraft.selectedTemplateGroupIds"
              :options="templateGroupOptions"
              multiple
              clearable
              filterable
              max-tag-count="responsive"
              placeholder="选择模板组"
              aria-label="本次模板组"
              @update:values="setSelectedTemplateGroups"
            />
          </section>

          <section class="batch-generation-field">
            <strong>输出范围</strong>
            <ContextSwitchBar
              label="输出范围"
              appearance="bare"
              :active-key="batchDraft.outputRange"
              :items="outputRangeOptions"
              @select="setOutputRange"
            />
          </section>

          <GenerationOutputCompressionSetting
            :model-value="props.outputCompressionEnabled"
            @update:model-value="
              emit('update:outputCompressionEnabled', $event)
            "
          />

          <section
            v-if="batchChecked"
            class="batch-preflight"
            data-testid="batch-preflight"
          >
            <header class="batch-preflight__header">
              <strong>执行检查</strong>
              <AppButton
                v-if="batchPreflight.issues.length"
                tone="text"
                @click="preflightProblemsVisible = true"
              >
                查看问题
              </AppButton>
            </header>
            <dl class="batch-preflight__stats">
              <div>
                <dt>产品</dt>
                <dd>{{ batchPreflight.productCount }}</dd>
              </div>
              <div>
                <dt>可执行</dt>
                <dd>{{ batchPreflight.executableProductCount }}</dd>
              </div>
              <div>
                <dt>跳过</dt>
                <dd>{{ batchPreflight.skippedProductCount }}</dd>
              </div>
              <div>
                <dt>模板组</dt>
                <dd>{{ batchPreflight.templateGroupCount }}</dd>
              </div>
              <div>
                <dt>生成项</dt>
                <dd>{{ batchPreflight.generationItemCount }}</dd>
              </div>
            </dl>
          </section>
        </div>
        <footer class="batch-generation-pane__footer">
          <AppButton @click="generationStore.runBatchPreflight()">
            <CheckCircle2 :size="16" />
            执行检查
          </AppButton>
          <AppButton
            tone="primary"
            :disabled="
              !batchChecked || batchPreflight.generationItemCount === 0
            "
            @click="start"
          >
            <Play :size="16" />
            开始生成
          </AppButton>
        </footer>
      </div>
    </template>

    <template #workspace>
      <div class="batch-workspace-pane">
        <BatchExecutionViewer
          :execution="batchExecution"
          :preflight-issues="
            batchExecution && batchChecked ? batchPreflight.issues : []
          "
          @download-all="download"
          @download-template="downloadTemplate"
          @retry="retryTemplate"
        />
      </div>
    </template>
  </AiWorkbenchLayout>

  <BatchProductPickerDialog
    v-model:show="productPickerVisible"
    :products="selectableProducts"
    :selected-product-ids="batchDraft.selectedProductIds"
    @confirm="generationStore.setBatchSelectedProducts"
  />
  <AppDialog
    v-model:show="preflightProblemsVisible"
    title="执行问题"
    positive-text="关闭"
    :show-negative="false"
    @confirm="preflightProblemsVisible = false"
  >
    <ul class="batch-preflight-problems">
      <li v-for="issue in batchPreflight.issues" :key="issue.productId">
        <strong>{{ issue.productName }}</strong>
        <span>{{ BATCH_SKIP_REASON_META[issue.reason].label }}</span>
      </li>
    </ul>
  </AppDialog>
</template>

<style scoped>
.batch-generation-pane,
.batch-workspace-pane {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}

.batch-generation-pane__header,
.batch-generation-pane__footer {
  display: flex;
  min-width: 0;
  flex: 0 0 auto;
  align-items: center;
  gap: var(--space-3);
}

.batch-generation-pane__header {
  justify-content: space-between;
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
}

.batch-generation-pane__header h2 {
  margin: 0;
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
}

.batch-generation-pane__scroll {
  min-width: 0;
  min-height: 0;
  flex: 1;
  overflow-y: auto;
}

.batch-generation-pane__scroll {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  padding: var(--space-4) var(--space-1) var(--space-4) 0;
}

.batch-generation-pane__footer {
  justify-content: flex-end;
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}

.batch-generation-field {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-2);
}

.batch-generation-field > strong {
  color: var(--text-primary);
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-medium);
}

.batch-generation-field__header {
  display: flex;
  min-width: 0;
  min-height: var(--control-height-default);
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}

.batch-generation-product-list {
  box-sizing: border-box;
  height: calc(var(--table-list-row-slot-height) * 4 + var(--space-1) * 3);
  min-width: 0;
  overflow-y: auto;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
}

.batch-preflight__stats {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-4);
  margin: 0;
}

.batch-preflight__header {
  display: flex;
  min-width: 0;
  min-height: var(--control-height-default);
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.batch-preflight {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-2);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}

.batch-preflight__stats > div {
  display: flex;
  align-items: baseline;
  gap: var(--space-1);
}

.batch-preflight__stats dt {
  color: var(--text-secondary);
}

.batch-preflight__stats dd {
  margin: 0;
  color: var(--text-primary);
  font-weight: var(--font-weight-semibold);
  font-variant-numeric: tabular-nums;
}

.batch-preflight-problems {
  margin: 0;
  padding: 0;
  list-style: none;
}

.batch-preflight-problems li {
  display: grid;
  min-width: 0;
  min-height: var(--table-row-height);
  align-items: center;
  gap: var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
  grid-template-columns: minmax(var(--field-width-xs), 0.45fr) minmax(0, 1fr);
}

.batch-preflight-problems li strong,
.batch-preflight-problems li span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.batch-preflight-problems li span {
  color: var(--text-secondary);
}

@media (max-width: 1100px) {
  .batch-generation-pane__scroll {
    overflow-y: visible;
  }
}
</style>
