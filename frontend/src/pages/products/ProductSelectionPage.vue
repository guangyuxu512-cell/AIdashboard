<script setup lang="ts">
import { NTabPane } from 'naive-ui'
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { EmptyState, PageSection } from '@/shared/components'
import { AppTabs } from '@/shared/ui'

const route = useRoute()
const router = useRouter()
const selectedTab = computed(() =>
  route.query.tab === 'collection-tasks'
    ? 'collection-tasks'
    : 'candidate-pool',
)

function selectTab(value: string | number) {
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
    <PageSection>
      <AppTabs :model-value="selectedTab" @update:model-value="selectTab">
        <NTabPane name="candidate-pool" tab="候选池">
          <EmptyState description="候选池功能待接入" />
        </NTabPane>
        <NTabPane name="collection-tasks" tab="采集任务">
          <EmptyState description="采集任务功能待接入" />
        </NTabPane>
      </AppTabs>
    </PageSection>
  </div>
</template>
