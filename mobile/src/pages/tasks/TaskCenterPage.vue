<script setup lang="ts">
import { showToast } from 'vant'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { MOBILE_ROUTE_NAMES } from '@/app/router/routes'
import {
  TaskFilterSheet,
  TaskInfiniteList,
  TaskListControls,
  useTaskCenter,
} from '@/features/task-center'
import {
  type MobileMainHeaderAction,
  useMobileMainHeaderAction,
} from '@/shared/ui'

const router = useRouter()
const filterOpen = ref(false)
const taskCenter = useTaskCenter()
const mainHeader = useMobileMainHeaderAction()
const headerAction: MobileMainHeaderAction = {
  label: '筛选运行日期',
  run: () => {
    filterOpen.value = true
  },
}
const resultCount = computed(() =>
  taskCenter.currentTotal.value === null
    ? '—'
    : `${taskCenter.currentTotal.value}个`,
)

onMounted(() => mainHeader?.setAction(headerAction))
onBeforeUnmount(() => {
  if (mainHeader?.action.value === headerAction) mainHeader.setAction(null)
})

function openTask(taskId: string): void {
  void router.push({
    name: MOBILE_ROUTE_NAMES.taskDetail,
    params: { taskId },
  })
}

async function refresh(): Promise<void> {
  if (!(await taskCenter.refresh())) showToast('刷新失败')
}
</script>

<template>
  <div class="mobile-list-page task-center-page-v2">
    <TaskListControls
      :search-query="taskCenter.searchQuery.value"
      :filter="taskCenter.status.value"
      :totals="taskCenter.metricTotals.value"
      :metrics-busy="taskCenter.metricsBusy.value"
      :result-label="taskCenter.resultLabel.value"
      :result-count="resultCount"
      :date-label="taskCenter.dateLabel.value"
      @update-search-query="taskCenter.searchQuery.value = $event"
      @select-filter="taskCenter.toggleStatus"
    />

    <div
      class="mobile-list-page__scroll mobile-scroll-container"
      data-testid="task-list-scroll"
      aria-label="任务列表"
      tabindex="0"
    >
      <TaskInfiniteList
        :tasks="taskCenter.tasks.value"
        :initial-loading="taskCenter.isInitialLoading.value"
        :initial-error="taskCenter.isInitialError.value"
        :next-page-error="taskCenter.isNextPageError.value"
        :refreshing="taskCenter.refreshing.value"
        :loading-more="taskCenter.isFetchingNextPage.value"
        :has-more="taskCenter.hasNextPage.value"
        :empty-description="taskCenter.emptyDescription.value"
        @refresh="refresh"
        @retry="taskCenter.retry"
        @load-more="taskCenter.loadMore"
        @retry-load-more="taskCenter.retryLoadMore"
        @select="openTask"
      />
    </div>

    <TaskFilterSheet
      v-model="filterOpen"
      :filters="taskCenter.appliedFilters.value"
      @apply="taskCenter.applyFilters"
    />
  </div>
</template>

<style scoped>
.task-center-page-v2 {
  color: var(--visual-v2-page-text-primary);
}
</style>
