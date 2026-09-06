<script setup lang="ts">
import { useMutation, useQueryClient } from '@tanstack/vue-query'
import { CheckCircle2, Folder, Play } from '@lucide/vue'
import { useMessage } from 'naive-ui'
import { computed, ref, watch } from 'vue'

import { fetchAssetContent } from '@/entities/asset/api/asset-api'
import {
  aiWorkbenchApi,
  aiWorkbenchQueryKeys,
  useGenerationJobQuery,
} from '@/entities/ai-workbench'
import type { GenerationJobReadDto } from '@/entities/ai-workbench'
import { AiWorkbenchLayout } from '@/features/ai-workbench'
import { getErrorMessage } from '@/shared/api'
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
  type BatchPreflightIssueView,
  type BatchPreflightView,
  type BatchProductScope,
  type BatchTemplateExecutionView,
  type BatchTemplateSource,
  type GenerationMode,
  type GenerationOutputRange,
  type GenerationProductView,
  type GenerationTemplateGroupView,
} from '../model/types'
import type { WorkbenchModelView } from '../../real-api/model/mappers'
import { mapBatchExecution } from '../../real-api/model/mappers'
import {
  compatibleWorkbenchModels,
  isWorkbenchModelSizeSupported,
  resolveWorkbenchModelId,
} from '../../real-api/model/model-selection'
import BatchExecutionViewer from './BatchExecutionViewer.vue'
import BatchProductPickerDialog from './BatchProductPickerDialog.vue'

const props = defineProps<{
  models: WorkbenchModelView[]
  products: GenerationProductView[]
  templateGroups: GenerationTemplateGroupView[]
}>()

const message = useMessage()
const queryClient = useQueryClient()
const mode = ref<GenerationMode>('NORMAL_GENERATION')
const selectedModelId = ref<string | null>(null)
const productScope = ref<BatchProductScope>('ALL_ENABLED')
const selectedProductIds = ref<string[]>([])
const templateSource = ref<BatchTemplateSource>('PRODUCT_CONFIGURED')
const selectedTemplateGroupIds = ref<string[]>([])
const outputRange = ref<GenerationOutputRange>('ALL')
const batchChecked = ref(false)
const currentJobId = ref<string | null>(null)
const productPickerVisible = ref(false)
const preflightProblemsVisible = ref(false)

const jobQuery = useGenerationJobQuery(currentJobId, { poll: true })
const submitMutation = useMutation({
  mutationFn: () =>
    aiWorkbenchApi.submitGeneration({
      work_mode: 'BATCH',
      submission_key: crypto.randomUUID(),
      model_id: selectedModelId.value!,
      mode: mode.value,
      product_scope: productScope.value,
      selected_product_ids:
        productScope.value === 'SELECTED' ? selectedProductIds.value : [],
      template_source: templateSource.value,
      selected_template_group_ids:
        templateSource.value === 'CURRENT_SELECTION'
          ? selectedTemplateGroupIds.value
          : [],
      output_range: outputRange.value,
    }),
  onSuccess: (job) => setJob(job),
})

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
const selectableProducts = computed(() =>
  props.products.filter((product) => product.enabled),
)
const scopedProducts = computed(() =>
  productScope.value === 'ALL_ENABLED'
    ? selectableProducts.value
    : selectableProducts.value.filter((product) =>
        selectedProductIds.value.includes(product.id),
      ),
)
const availableTemplateGroups = computed(() =>
  props.templateGroups.filter((group) => group.mode === mode.value),
)
const templateGroupOptions = computed(() =>
  availableTemplateGroups.value.map((group) => ({
    label: group.name,
    value: group.id,
    disabled: !group.enabled,
  })),
)
const preflight = computed<BatchPreflightView>(() => {
  const issues: BatchPreflightIssueView[] = []
  const plans: BatchPreflightView['plans'] = []
  const modelLimit = selectedModel.value?.maxInputImages ?? 0
  for (const product of scopedProducts.value) {
    const productSources = product.assets.filter(
      (asset) => asset.role === 'PRODUCT_SOURCE',
    )
    const styleReferences = product.assets.filter(
      (asset) => asset.role === 'STYLE_REFERENCE',
    )
    const modeEnabled =
      mode.value === 'NORMAL_GENERATION'
        ? product.normalGenerationEnabled
        : product.styleReplicationEnabled
    let reason: BatchPreflightIssueView['reason'] | null = null
    if (!modeEnabled) reason = 'MODE_DISABLED'
    else if (!productSources.length) reason = 'NO_PRODUCT_SOURCE'
    else if (mode.value === 'STYLE_REPLICATION' && !styleReferences.length) {
      reason = 'NO_STYLE_REFERENCE'
    } else if (
      productSources.length + (mode.value === 'STYLE_REPLICATION' ? 1 : 0) >
      modelLimit
    ) {
      reason = 'MODEL_INPUT_LIMIT'
    }

    const configuredIds =
      mode.value === 'NORMAL_GENERATION'
        ? product.normalTemplateGroupIds
        : product.styleReplicationTemplateGroupIds
    const groupIds =
      templateSource.value === 'CURRENT_SELECTION'
        ? selectedTemplateGroupIds.value
        : configuredIds
    const groups = groupIds
      .map((id) =>
        availableTemplateGroups.value.find((group) => group.id === id),
      )
      .filter((group): group is GenerationTemplateGroupView => Boolean(group))
      .filter((group) => group.enabled)
      .map((group) => ({
        group,
        templates: group.templates.filter(
          (template) =>
            template.enabled &&
            (outputRange.value === 'ALL' ||
              template.outputRole === outputRange.value),
        ),
      }))
      .filter((entry) => entry.templates.length > 0)
    if (!reason && !groups.length) reason = 'NO_TEMPLATE_GROUPS'
    if (
      !reason &&
      groups.some((entry) =>
        entry.templates.some(
          (template) =>
            !isWorkbenchModelSizeSupported(selectedModel.value, template.size),
        ),
      )
    ) {
      reason = 'MODEL_SIZE_UNSUPPORTED'
    }
    if (reason) {
      issues.push({ productId: product.id, productName: product.name, reason })
      continue
    }
    const multiplier =
      mode.value === 'STYLE_REPLICATION' ? styleReferences.length : 1
    plans.push({
      productId: product.id,
      productName: product.name,
      styleReferenceCount: styleReferences.length,
      groups,
      itemCount:
        multiplier *
        groups.reduce(
          (total, entry) =>
            total +
            entry.templates.reduce(
              (count, template) => count + template.count,
              0,
            ),
          0,
        ),
    })
  }
  return {
    productCount: scopedProducts.value.length,
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
    issues,
    plans,
  }
})
const execution = computed(() =>
  jobQuery.data.value ? mapBatchExecution(jobQuery.data.value) : null,
)
const hasModelCapabilityIssue = computed(() =>
  preflight.value.issues.some(
    (issue) =>
      issue.reason === 'MODEL_INPUT_LIMIT' ||
      issue.reason === 'MODEL_SIZE_UNSUPPORTED',
  ),
)

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
  { label: GENERATION_OUTPUT_RANGE_META.MAIN_IMAGE.label, key: 'MAIN_IMAGE' },
  {
    label: GENERATION_OUTPUT_RANGE_META.DETAIL_IMAGE.label,
    key: 'DETAIL_IMAGE',
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
watch(
  [
    mode,
    selectedModelId,
    productScope,
    selectedProductIds,
    templateSource,
    selectedTemplateGroupIds,
    outputRange,
  ],
  () => {
    batchChecked.value = false
  },
  { deep: true },
)

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
  selectedTemplateGroupIds.value = []
}

function setProductScope(value: string): void {
  if (value !== 'ALL_ENABLED' && value !== 'SELECTED') return
  productScope.value = value
  if (value === 'SELECTED') productPickerVisible.value = true
}

function setTemplateSource(value: string): void {
  if (value === 'PRODUCT_CONFIGURED' || value === 'CURRENT_SELECTION') {
    templateSource.value = value
  }
}

function setOutputRange(value: string): void {
  if (value === 'ALL' || value === 'MAIN_IMAGE' || value === 'DETAIL_IMAGE') {
    outputRange.value = value
  }
}

function setSelectedTemplateGroups(values: Array<string | number>): void {
  selectedTemplateGroupIds.value = values.map(String)
}

function runPreflight(): void {
  batchChecked.value = true
  if (preflight.value.issues.length) preflightProblemsVisible.value = true
}

function start(): void {
  if (
    !batchChecked.value ||
    !selectedModel.value ||
    preflight.value.generationItemCount === 0 ||
    hasModelCapabilityIssue.value ||
    submitMutation.isPending.value
  ) {
    return
  }
  submitMutation.mutate(undefined, {
    onSuccess: () => message.success('批量生成已创建'),
    onError: (error) => message.error(getErrorMessage(error)),
  })
}

async function downloadResult(
  result: NonNullable<
    typeof execution.value
  >['products'][number]['templateGroups'][number]['templates'][number]['results'][number],
): Promise<void> {
  if (!result.previewUrl) return
  const blob = await fetchAssetContent(result.previewUrl)
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = result.name ?? 'generation.png'
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

function downloadTemplate(template: BatchTemplateExecutionView): void {
  const results = template.results.filter(
    (result) => result.status === 'SUCCESS' && result.previewUrl,
  )
  void Promise.all(results.map(downloadResult))
    .then(() => message.success(`已开始下载 ${results.length} 张图片`))
    .catch((error) => message.error(getErrorMessage(error)))
}

function downloadAll(): void {
  const results =
    execution.value?.products.flatMap((product) =>
      product.templateGroups.flatMap((group) =>
        group.templates.flatMap((template) =>
          template.results.filter(
            (result) => result.status === 'SUCCESS' && result.previewUrl,
          ),
        ),
      ),
    ) ?? []
  void Promise.all(results.map(downloadResult))
    .then(() => message.success(`已开始下载 ${results.length} 张图片`))
    .catch((error) => message.error(getErrorMessage(error)))
}

function retryTemplate(identity: BatchTemplateExecutionIdentity): void {
  const job = jobQuery.data.value
  if (!job) return
  const items = job.items
    .filter(
      (item) =>
        item.status === 'FAILED' &&
        item.source_product_material_group_id === identity.productId &&
        item.source_template_group_id === identity.templateGroupId &&
        item.source_prompt_template_id === identity.templateId,
    )
    .map((item) => ({
      item_id: item.generation_item_id,
      expected_attempt_count: item.attempt_count,
    }))
  if (!items.length) return
  void aiWorkbenchApi
    .retryGenerationItems(job.generation_job_id, { items })
    .then((updated) => {
      setJob(updated)
      message.success('失败项已重新生成')
    })
    .catch((error) => message.error(getErrorMessage(error)))
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
            :active-key="mode"
            :items="modeOptions"
            @select="setMode"
          />
        </header>
        <div class="batch-generation-pane__scroll">
          <section class="batch-generation-field">
            <strong>模型</strong>
            <AppSelect
              v-model="selectedModelId"
              :options="modelOptions"
              placeholder="选择模型"
              aria-label="批量生成模型"
            />
          </section>
          <section class="batch-generation-field">
            <strong>产品范围</strong>
            <ContextSwitchBar
              label="产品范围"
              appearance="bare"
              :active-key="productScope"
              :items="productScopeOptions"
              @select="setProductScope"
            />
            <div class="batch-generation-field__header">
              <span>当前产品</span>
              <AppButton
                v-if="productScope === 'SELECTED' && selectedProductIds.length"
                tone="text"
                @click="selectedProductIds = []"
              >
                清空
              </AppButton>
            </div>
            <div
              class="batch-generation-product-list"
              data-testid="batch-product-list"
            >
              <EmptyState
                v-if="scopedProducts.length === 0"
                description="暂无产品"
              />
              <CompactEntityRow
                v-for="product in scopedProducts"
                v-else
                :key="product.id"
                :title="product.name"
                :count="product.assets.length"
                :select-label="`查看产品 ${product.name}`"
                @select="productPickerVisible = productScope === 'SELECTED'"
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
              :active-key="templateSource"
              :items="templateSourceOptions"
              @select="setTemplateSource"
            />
            <AppSelect
              v-if="templateSource === 'CURRENT_SELECTION'"
              :model-value="selectedTemplateGroupIds"
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
              :active-key="outputRange"
              :items="outputRangeOptions"
              @select="setOutputRange"
            />
          </section>

          <section
            v-if="batchChecked"
            class="batch-preflight"
            data-testid="batch-preflight"
          >
            <header class="batch-preflight__header">
              <strong>执行检查</strong>
              <AppButton
                v-if="preflight.issues.length"
                tone="text"
                @click="preflightProblemsVisible = true"
              >
                查看问题
              </AppButton>
            </header>
            <dl class="batch-preflight__stats">
              <div>
                <dt>产品</dt>
                <dd>{{ preflight.productCount }}</dd>
              </div>
              <div>
                <dt>可执行</dt>
                <dd>{{ preflight.executableProductCount }}</dd>
              </div>
              <div>
                <dt>跳过</dt>
                <dd>{{ preflight.skippedProductCount }}</dd>
              </div>
              <div>
                <dt>模板组</dt>
                <dd>{{ preflight.templateGroupCount }}</dd>
              </div>
              <div>
                <dt>生成项</dt>
                <dd>{{ preflight.generationItemCount }}</dd>
              </div>
            </dl>
          </section>
        </div>
        <footer class="batch-generation-pane__footer">
          <AppButton @click="runPreflight">
            <CheckCircle2 :size="16" />
            执行检查
          </AppButton>
          <AppButton
            tone="primary"
            :disabled="
              !batchChecked ||
              !selectedModel ||
              preflight.generationItemCount === 0 ||
              hasModelCapabilityIssue ||
              submitMutation.isPending.value
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
          :execution="execution"
          :preflight-issues="execution && batchChecked ? preflight.issues : []"
          @download-all="downloadAll"
          @download-template="downloadTemplate"
          @retry="retryTemplate"
        />
      </div>
    </template>
  </AiWorkbenchLayout>

  <BatchProductPickerDialog
    v-model:show="productPickerVisible"
    :products="selectableProducts"
    :selected-product-ids="selectedProductIds"
    @confirm="selectedProductIds = $event"
  />
  <AppDialog
    v-model:show="preflightProblemsVisible"
    title="执行问题"
    positive-text="关闭"
    :show-negative="false"
    @confirm="preflightProblemsVisible = false"
  >
    <ul class="batch-preflight-problems">
      <li v-for="issue in preflight.issues" :key="issue.productId">
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
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: var(--space-5);
  padding: var(--space-4) var(--space-1) var(--space-4) 0;
  overflow-y: auto;
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

.batch-generation-field__header,
.batch-preflight__header {
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
  height: calc(var(--table-list-row-slot-height) * 4 + var(--space-1) * 3);
  min-width: 0;
  overflow-y: auto;
}

.batch-preflight {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-2);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}

.batch-preflight__stats {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-4);
  margin: 0;
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

@media (max-width: 1100px) {
  .batch-generation-pane__scroll {
    overflow-y: visible;
  }
}
</style>
