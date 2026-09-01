<script setup lang="ts">
import { ChevronRight, Folder } from '@lucide/vue'
import { NProgress } from 'naive-ui'
import { computed } from 'vue'

import CompactEntityRow from '@/shared/components/CompactEntityRow.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import { AppButton } from '@/shared/ui'

import {
  BATCH_EXECUTION_STATUS_META,
  type BatchProductExecutionView,
} from '../model/types'

const props = defineProps<{
  product: BatchProductExecutionView
  active: boolean
}>()

defineEmits<{
  select: []
}>()

const percentage = computed(() =>
  props.product.totalCount === 0
    ? 0
    : (props.product.completedCount / props.product.totalCount) * 100,
)

const progressStatus = computed<'default' | 'success' | 'warning' | 'error'>(
  () => {
    if (props.product.status === 'SUCCESS') return 'success'
    if (props.product.status === 'FAILED') return 'error'
    if (props.product.status === 'PARTIAL_FAILED') return 'warning'
    return 'default'
  },
)
</script>

<template>
  <CompactEntityRow
    :title="product.productName"
    :count="`${product.completedCount}/${product.totalCount}`"
    :active="active"
    :select-label="`查看产品任务 ${product.productName}`"
    data-testid="batch-product-task-row"
    :data-product-id="product.productId"
    :data-product-status="product.status"
    @select="$emit('select')"
  >
    <template #icon><Folder :size="16" /></template>
    <template #title>
      <span class="batch-product-task-row__main">
        <span class="batch-product-task-row__name">{{
          product.productName
        }}</span>
        <span class="batch-product-task-row__progress">
          <span class="batch-product-task-row__progress-bar">
            <NProgress
              type="line"
              :percentage="percentage"
              :show-indicator="false"
              :status="progressStatus"
              :processing="product.status === 'RUNNING'"
            />
          </span>
          <StatusTag
            :label="BATCH_EXECUTION_STATUS_META[product.status].label"
            :tone="BATCH_EXECUTION_STATUS_META[product.status].tone"
            appearance="dot"
          />
          <span>{{ BATCH_EXECUTION_STATUS_META[product.status].label }}</span>
        </span>
      </span>
    </template>
    <template #count>
      {{ product.completedCount }}/{{ product.totalCount }}
    </template>
    <template #actions>
      <AppButton
        tone="text"
        :aria-label="`查看 ${product.productName} 详情`"
        @click="$emit('select')"
      >
        <ChevronRight :size="15" />
      </AppButton>
    </template>
  </CompactEntityRow>
</template>

<style scoped>
.batch-product-task-row__main,
.batch-product-task-row__progress {
  display: flex;
  min-width: 0;
}

.batch-product-task-row__main {
  width: 100%;
  flex-direction: column;
  gap: var(--space-1);
}

.batch-product-task-row__progress {
  align-items: center;
  gap: var(--space-1);
}

.batch-product-task-row__name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.batch-product-task-row__progress-bar {
  min-width: var(--space-6);
  flex: 1;
}

.batch-product-task-row__progress > span:last-child {
  flex: 0 0 auto;
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
  font-weight: var(--font-weight-regular);
}
</style>
