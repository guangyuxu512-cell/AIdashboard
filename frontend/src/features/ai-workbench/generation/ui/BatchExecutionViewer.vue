<script setup lang="ts">
import { Download } from '@lucide/vue'
import { NCollapse, NCollapseItem, NProgress } from 'naive-ui'
import { computed, ref, watch } from 'vue'

import ContextSwitchBar from '@/shared/components/ContextSwitchBar.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import { AppButton, AppDialog } from '@/shared/ui'

import {
  filterBatchExecutionProducts,
  findDefaultExpandedTemplateGroupId,
  resolveBatchProductSelection,
  type BatchTemplateExecutionIdentity,
} from '../model/batch-execution'
import {
  BATCH_EXECUTION_STATUS_META,
  BATCH_SKIP_REASON_META,
  type BatchExecutionFilter,
  type BatchExecutionView,
  type BatchPreflightIssueView,
  type BatchTemplateExecutionView,
} from '../model/types'
import BatchProductTaskRow from './BatchProductTaskRow.vue'
import BatchTemplateExecutionCard from './BatchTemplateExecutionCard.vue'

const props = defineProps<{
  execution: BatchExecutionView | null
  preflightIssues: readonly BatchPreflightIssueView[]
}>()

defineEmits<{
  downloadAll: []
  downloadTemplate: [template: BatchTemplateExecutionView]
  retry: [identity: BatchTemplateExecutionIdentity]
}>()

const filter = ref<BatchExecutionFilter>('ALL')
const selectedProductId = ref<string | null>(null)
const expandedGroupNames = ref<string[]>([])
const problemsVisible = ref(false)

const filterOptions = [
  { key: 'ALL', label: '全部' },
  { key: 'RUNNING', label: '生成中' },
  { key: 'FAILED', label: '失败' },
] as const

const filteredProducts = computed(() =>
  filterBatchExecutionProducts(props.execution?.products ?? [], filter.value),
)

const selectedProduct = computed(
  () =>
    filteredProducts.value.find(
      (product) => product.productId === selectedProductId.value,
    ) ?? null,
)

const completedItems = computed(
  () =>
    (props.execution?.successItems ?? 0) + (props.execution?.failedItems ?? 0),
)

const progressPercentage = computed(() => {
  const total = props.execution?.totalItems ?? 0
  return total === 0 ? 0 : (completedItems.value / total) * 100
})

const progressLabel = computed(() => `${progressPercentage.value.toFixed(1)}%`)

const runtimeFailures = computed(() =>
  (props.execution?.products ?? []).flatMap((product) =>
    product.templateGroups.flatMap((group) =>
      group.templates.flatMap((template) =>
        template.results
          .filter((result) => result.status === 'FAILED')
          .map((result) => ({
            id: result.id,
            productName: product.productName,
            templateGroupName: group.templateGroupName,
            templateName: template.templateName,
            message: result.errorMessage ?? '生成失败',
          })),
      ),
    ),
  ),
)

const problemCount = computed(
  () => props.preflightIssues.length + runtimeFailures.value.length,
)

watch(
  () => props.execution?.id ?? null,
  (executionId, previousExecutionId) => {
    if (executionId !== previousExecutionId) {
      filter.value = 'ALL'
      selectedProductId.value = null
    }
  },
  { flush: 'sync' },
)

watch(
  filteredProducts,
  (products) => {
    selectedProductId.value = resolveBatchProductSelection(
      products,
      selectedProductId.value,
    )
  },
  { immediate: true, flush: 'sync' },
)

watch(
  () => selectedProduct.value?.productId ?? null,
  () => {
    const defaultGroup = selectedProduct.value
      ? findDefaultExpandedTemplateGroupId(selectedProduct.value)
      : null
    expandedGroupNames.value = defaultGroup ? [defaultGroup] : []
  },
  { immediate: true, flush: 'sync' },
)

function setFilter(value: string): void {
  filter.value = value as BatchExecutionFilter
}
</script>

<template>
  <section class="batch-execution-viewer" data-testid="batch-execution-viewer">
    <header
      class="batch-execution-summary"
      data-testid="batch-execution-summary"
    >
      <div class="batch-execution-summary__heading">
        <h2>执行结果</h2>
        <div v-if="execution" class="batch-execution-summary__state">
          <StatusTag
            :label="BATCH_EXECUTION_STATUS_META[execution.status].label"
            :tone="BATCH_EXECUTION_STATUS_META[execution.status].tone"
          />
          <strong>{{ completedItems }} / {{ execution.totalItems }}</strong>
          <span>{{ progressLabel }}</span>
        </div>
      </div>

      <template v-if="execution">
        <NProgress
          data-testid="batch-execution-progress"
          type="line"
          :percentage="progressPercentage"
          :show-indicator="false"
          :processing="execution.status === 'RUNNING'"
        />
        <dl
          class="batch-execution-summary__stats"
          data-testid="batch-runtime-stats"
        >
          <div>
            <dt>成功</dt>
            <dd>{{ execution.successItems }}</dd>
          </div>
          <div>
            <dt>生成中</dt>
            <dd>{{ execution.runningItems }}</dd>
          </div>
          <div>
            <dt>等待中</dt>
            <dd>{{ execution.waitingItems }}</dd>
          </div>
          <div>
            <dt>失败</dt>
            <dd>{{ execution.failedItems }}</dd>
          </div>
        </dl>
      </template>

      <div class="batch-execution-summary__toolbar">
        <ContextSwitchBar
          v-if="execution"
          label="执行结果筛选"
          appearance="bare"
          :items="filterOptions"
          :active-key="filter"
          @select="setFilter"
        />
        <AppButton
          v-if="problemCount"
          tone="text"
          @click="problemsVisible = true"
        >
          查看问题
        </AppButton>
        <AppButton v-if="execution" tone="text" @click="$emit('downloadAll')">
          <Download :size="15" />
          下载全部
        </AppButton>
      </div>
    </header>

    <EmptyState v-if="!execution" description="暂无生成结果" />

    <div
      v-else-if="filteredProducts.length"
      class="batch-execution-body"
      data-testid="batch-execution-body"
    >
      <section class="batch-product-task-list" aria-label="产品任务列表">
        <header>
          <strong>产品任务列表</strong>
          <span>{{ filteredProducts.length }}</span>
        </header>
        <div
          class="batch-product-task-list__scroll"
          data-testid="batch-product-task-list"
        >
          <BatchProductTaskRow
            v-for="product in filteredProducts"
            :key="product.productId"
            :product="product"
            :active="product.productId === selectedProductId"
            @select="selectedProductId = product.productId"
          />
        </div>
      </section>

      <section
        v-if="selectedProduct"
        class="batch-product-result-detail"
        aria-label="当前产品详情"
        data-testid="batch-product-result-detail"
      >
        <header class="batch-product-result-detail__header">
          <span>当前产品详情</span>
          <strong :title="selectedProduct.productName">
            {{ selectedProduct.productName }}
          </strong>
          <span>
            {{ selectedProduct.completedCount }} /
            {{ selectedProduct.totalCount }}
          </span>
        </header>
        <div
          class="batch-product-result-detail__scroll"
          data-testid="batch-product-detail-scroll"
        >
          <NCollapse v-model:expanded-names="expandedGroupNames">
            <NCollapseItem
              v-for="group in selectedProduct.templateGroups"
              :key="group.templateGroupId"
              :name="group.templateGroupId"
              :title="group.templateGroupName"
              data-testid="batch-template-group"
              :data-template-group-id="group.templateGroupId"
            >
              <template #header-extra>
                <span class="batch-template-group__summary">
                  <span
                    >{{ group.completedCount }} / {{ group.totalCount }}</span
                  >
                  <StatusTag
                    :label="BATCH_EXECUTION_STATUS_META[group.status].label"
                    :tone="BATCH_EXECUTION_STATUS_META[group.status].tone"
                  />
                </span>
              </template>
              <div class="batch-template-group__templates">
                <BatchTemplateExecutionCard
                  v-for="template in group.templates"
                  :key="template.templateId"
                  :product-id="selectedProduct.productId"
                  :template-group-id="group.templateGroupId"
                  :template="template"
                  @retry="$emit('retry', $event)"
                  @download="$emit('downloadTemplate', $event)"
                />
              </div>
            </NCollapseItem>
          </NCollapse>
        </div>
      </section>
    </div>

    <EmptyState v-else description="暂无匹配结果" />
  </section>

  <AppDialog
    v-model:show="problemsVisible"
    title="执行问题"
    positive-text="关闭"
    :show-negative="false"
    @confirm="problemsVisible = false"
  >
    <div class="batch-execution-problems">
      <section v-if="preflightIssues.length">
        <h3>跳过</h3>
        <ul>
          <li v-for="issue in preflightIssues" :key="issue.productId">
            <strong>{{ issue.productName }}</strong>
            <span>{{ BATCH_SKIP_REASON_META[issue.reason].label }}</span>
          </li>
        </ul>
      </section>
      <section v-if="runtimeFailures.length">
        <h3>失败</h3>
        <ul>
          <li v-for="issue in runtimeFailures" :key="issue.id">
            <strong>{{ issue.productName }} · {{ issue.templateName }}</strong>
            <span>{{ issue.templateGroupName }} · {{ issue.message }}</span>
          </li>
        </ul>
      </section>
      <EmptyState v-if="problemCount === 0" description="暂无问题" />
    </div>
  </AppDialog>
</template>

<style scoped>
.batch-execution-viewer {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}

.batch-execution-summary {
  display: flex;
  min-width: 0;
  flex: 0 0 auto;
  flex-direction: column;
  gap: var(--space-2);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
}

.batch-execution-summary__heading,
.batch-execution-summary__state,
.batch-execution-summary__toolbar,
.batch-product-task-list > header,
.batch-product-result-detail__header,
.batch-template-group__summary {
  display: flex;
  min-width: 0;
  align-items: center;
}

.batch-execution-summary__heading {
  justify-content: space-between;
  gap: var(--space-3);
}

.batch-execution-summary h2 {
  margin: 0;
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
}

.batch-execution-summary__state,
.batch-execution-summary__toolbar,
.batch-template-group__summary {
  gap: var(--space-2);
}

.batch-execution-summary__state strong,
.batch-execution-summary__state span,
.batch-execution-summary__stats dd,
.batch-product-result-detail__header > span:last-child,
.batch-template-group__summary > span:first-child {
  font-variant-numeric: tabular-nums;
}

.batch-execution-summary__state span,
.batch-product-task-list > header span,
.batch-product-result-detail__header > span,
.batch-template-group__summary > span:first-child {
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}

.batch-execution-summary__stats {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  gap: var(--space-4);
  margin: 0;
}

.batch-execution-summary__stats > div {
  display: flex;
  align-items: baseline;
  gap: var(--space-1);
}

.batch-execution-summary__stats dt {
  color: var(--text-secondary);
}

.batch-execution-summary__stats dd {
  margin: 0;
  color: var(--text-primary);
  font-weight: var(--font-weight-semibold);
}

.batch-execution-summary__toolbar {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.batch-execution-body {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1;
  gap: var(--layout-card-gap);
  padding-top: var(--space-3);
  overflow: hidden;
}

.batch-product-task-list,
.batch-product-result-detail {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
}

.batch-product-task-list {
  width: clamp(
    calc(var(--field-width-md) + var(--space-8) + var(--space-2)),
    42%,
    calc(var(--field-width-lg) - var(--space-5))
  );
  flex: 0 0
    clamp(
      calc(var(--field-width-md) + var(--space-8) + var(--space-2)),
      42%,
      calc(var(--field-width-lg) - var(--space-5))
    );
  padding-right: var(--space-3);
  border-right: 1px solid var(--border-subtle);
}

.batch-product-task-list > header,
.batch-product-result-detail__header {
  min-height: var(--control-height-default);
  flex: 0 0 auto;
  gap: var(--space-2);
  border-bottom: 1px solid var(--border-subtle);
}

.batch-product-task-list > header {
  justify-content: space-between;
}

.batch-product-task-list__scroll,
.batch-product-result-detail__scroll {
  min-width: 0;
  min-height: 0;
  flex: 1;
  overflow-y: auto;
}

.batch-product-task-list__scroll {
  padding: var(--space-2) var(--space-1) var(--space-2) 0;
}

.batch-product-result-detail {
  flex: 1;
}

.batch-product-result-detail__header > strong {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.batch-product-result-detail__scroll {
  padding: var(--space-2) var(--space-1) var(--space-2) 0;
}

.batch-template-group__summary {
  padding-right: var(--space-2);
}

.batch-template-group__templates {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-2) 0 var(--space-3);
}

.batch-execution-problems {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-5);
}

.batch-execution-problems h3 {
  margin: 0 0 var(--space-2);
  font-size: var(--font-size-section-title);
}

.batch-execution-problems ul {
  margin: 0;
  padding: 0;
  list-style: none;
}

.batch-execution-problems li {
  display: grid;
  min-height: var(--table-row-height);
  align-items: center;
  gap: var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
  grid-template-columns: minmax(var(--field-width-xs), 0.45fr) minmax(0, 1fr);
}

.batch-execution-problems li strong,
.batch-execution-problems li span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.batch-execution-problems li span {
  color: var(--text-secondary);
}
</style>
