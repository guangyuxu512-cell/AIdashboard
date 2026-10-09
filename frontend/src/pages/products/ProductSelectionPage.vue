<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ContextSwitchBar, StatusTag } from '@/shared/components'
import { apiMode } from '@/shared/api'
import SelectionWorkspace from '@/features/product-selection/ui/SelectionWorkspace.vue'

const selectionItems = [
  {
    key: 'candidate-pool',
    label: '候选池',
    description: '候选池功能待接入',
  },
  {
    key: 'collection-tasks',
    label: '采集任务',
    description: '采集任务功能待接入',
  },
  {
    key: 'selection-strategy',
    label: '选品策略',
    description: '选品策略待接入',
  },
]

const route = useRoute()
const router = useRouter()
const selectedItem = computed(
  () =>
    selectionItems.find((item) => item.key === route.query.tab) ??
    selectionItems[0]!,
)
const panel = computed<
  'candidate-pool' | 'selection-strategy' | 'collection-tasks'
>(() =>
  selectedItem.value.key === 'collection-tasks'
    ? 'collection-tasks'
    : selectedItem.value.key === 'selection-strategy'
      ? 'selection-strategy'
      : 'candidate-pool',
)

function selectTab(value: string) {
  void router.push({
    query: {
      ...route.query,
      tab: value === 'candidate-pool' ? undefined : value,
    },
  })
}
</script>

<template>
  <div class="page-container product-selection-page">
    <div class="product-selection-navigation">
      <ContextSwitchBar
        label="选品库切换"
        appearance="framed"
        :items="selectionItems"
        :active-key="selectedItem.key"
        @select="selectTab"
      />
      <StatusTag v-if="apiMode === 'mock'" label="演示数据" />
    </div>
    <SelectionWorkspace :panel="panel" />
  </div>
</template>

<style scoped>
.product-selection-page {
  height: 100%;
  min-height: 0;
}
.product-selection-navigation {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.product-selection-navigation > :first-child {
  flex: 1;
}
</style>
