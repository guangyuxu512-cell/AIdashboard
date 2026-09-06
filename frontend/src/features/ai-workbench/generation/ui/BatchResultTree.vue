<script setup lang="ts">
import { Download } from '@lucide/vue'

import EmptyState from '@/shared/components/EmptyState.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import { AppButton } from '@/shared/ui'

import {
  GENERATION_OUTPUT_ROLE_META,
  GENERATION_RESULT_STATUS_META,
  type BatchProductResultView,
} from '../model/types'

defineProps<{
  results: BatchProductResultView[]
}>()

defineEmits<{
  download: []
}>()
</script>

<template>
  <div
    v-if="results.length"
    class="batch-result-tree"
    data-testid="batch-result-tree"
  >
    <div class="batch-result-tree__actions">
      <AppButton tone="text" @click="$emit('download')">
        <Download :size="15" />
        下载批次
      </AppButton>
    </div>
    <details v-for="product in results" :key="product.productId" open>
      <summary>{{ product.productName }}</summary>
      <div class="batch-result-tree__groups">
        <details v-for="group in product.groups" :key="group.groupId" open>
          <summary>
            <span>{{ group.groupName }}</span>
            <span class="batch-result-tree__group-actions">
              <small
                >{{
                  group.templates.reduce(
                    (total, template) => total + template.results.length,
                    0,
                  )
                }}
                张</small
              >
              <AppButton
                tone="text"
                :aria-label="`下载 ${group.groupName} 结果`"
                @click.stop="$emit('download')"
              >
                <Download :size="14" />
                下载组
              </AppButton>
            </span>
          </summary>
          <ul>
            <li v-for="template in group.templates" :key="template.templateId">
              <div class="batch-result-tree__template">
                <strong>{{ template.templateName }}</strong>
                <span>{{
                  GENERATION_OUTPUT_ROLE_META[template.outputRole].label
                }}</span>
              </div>
              <div class="batch-result-tree__items">
                <span
                  v-for="item in template.results"
                  :key="item.id"
                  class="batch-result-tree__item"
                >
                  <span>{{ item.name }}</span>
                  <StatusTag
                    :label="GENERATION_RESULT_STATUS_META[item.status].label"
                    :tone="GENERATION_RESULT_STATUS_META[item.status].tone"
                  />
                  <span
                    v-if="item.status === 'SUCCESS' && item.savedToProductId"
                    class="batch-result-tree__asset-status"
                  >
                    已加入素材库
                  </span>
                  <AppButton
                    tone="text"
                    :aria-label="`下载 ${item.name}`"
                    @click="$emit('download')"
                  >
                    <Download :size="13" />
                    下载
                  </AppButton>
                </span>
              </div>
            </li>
          </ul>
        </details>
      </div>
    </details>
  </div>
  <EmptyState v-else description="暂无批量结果" />
</template>

<style scoped>
.batch-result-tree {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-3);
}

.batch-result-tree__actions {
  display: flex;
  justify-content: flex-end;
}

.batch-result-tree details {
  min-width: 0;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
  background: var(--bg-surface-solid);
}

.batch-result-tree summary {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3);
  color: var(--text-primary);
  cursor: pointer;
  font-weight: var(--font-weight-medium);
}

.batch-result-tree summary small {
  color: var(--text-secondary);
  font-weight: var(--font-weight-regular);
}

.batch-result-tree__group-actions {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: var(--space-2);
}

.batch-result-tree__groups {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-2);
  padding: 0 var(--space-3) var(--space-3);
}

.batch-result-tree__groups details {
  background: var(--bg-subtle);
}

.batch-result-tree ul {
  margin: 0;
  padding: 0 var(--space-3) var(--space-3);
  list-style: none;
}

.batch-result-tree li {
  display: grid;
  min-width: 0;
  gap: var(--space-3);
  padding: var(--space-2) 0;
  border-top: 1px solid var(--border-subtle);
  grid-template-columns: minmax(var(--field-width-xs), 0.35fr) minmax(0, 1fr);
}

.batch-result-tree__template,
.batch-result-tree__items,
.batch-result-tree__items > span {
  display: flex;
  min-width: 0;
}

.batch-result-tree__template {
  flex-direction: column;
  gap: var(--space-1);
}

.batch-result-tree__template span {
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}

.batch-result-tree__items {
  flex-wrap: wrap;
  gap: var(--space-2);
}

.batch-result-tree__item {
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-control);
  color: var(--text-secondary);
  background: var(--bg-surface-solid);
  font-size: var(--font-size-secondary);
}

.batch-result-tree__item > span:first-child {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.batch-result-tree__asset-status {
  color: var(--text-tertiary);
  white-space: nowrap;
}
</style>
