<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ContextSwitchBar, EmptyState, PageSection } from '@/shared/components'

const selectionItems = [
  { key: 'candidate-pool', label: '候选池' },
  { key: 'collection-tasks', label: '采集任务' },
]

const route = useRoute()
const router = useRouter()
const selectedTab = computed(() =>
  route.query.tab === 'collection-tasks'
    ? 'collection-tasks'
    : 'candidate-pool',
)

function selectTab(value: string) {
  void router.push({
    query: {
      ...route.query,
      tab: value === 'collection-tasks' ? 'collection-tasks' : undefined,
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
      :active-key="selectedTab"
      @select="selectTab"
    />
    <PageSection>
      <EmptyState
        :description="
          selectedTab === 'collection-tasks'
            ? '采集任务功能待接入'
            : '候选池功能待接入'
        "
      />
    </PageSection>
  </div>
</template>
