<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ContextSwitchBar, EmptyState, PageSection } from '@/shared/components'

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
  <div class="page-container">
    <ContextSwitchBar
      label="选品库切换"
      appearance="framed"
      :items="selectionItems"
      :active-key="selectedItem.key"
      @select="selectTab"
    />
    <PageSection>
      <EmptyState :description="selectedItem.description" />
    </PageSection>
  </div>
</template>
