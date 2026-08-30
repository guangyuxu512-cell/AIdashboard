<script setup lang="ts">
import { ActionSheet as VanActionSheet, showToast } from 'vant'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { MOBILE_ROUTE_NAMES } from '@/app/router/routes'
import { TASK_STATUSES, TASK_STATUS_META } from '@/entities/task'
import {
  TaskFilterSheet,
  TaskInfiniteList,
  type TaskStatusFilter,
  useTaskCenter,
} from '@/features/task-center'
import { MobileListToolbar } from '@/shared/ui'

interface TaskStatusAction {
  name: string
  value: TaskStatusFilter
}

const router = useRouter()
const filterOpen = ref(false)
const statusOpen = ref(false)
const taskCenter = useTaskCenter()
const statusActions: TaskStatusAction[] = [
  { name: '全部', value: 'all' },
  ...TASK_STATUSES.map((status) => ({
    name: TASK_STATUS_META[status].label,
    value: status,
  })),
]
const statusLabel = computed(
  () =>
    statusActions.find((action) => action.value === taskCenter.status.value)
      ?.name ?? '全部',
)
const totalLabel = computed(() => {
  const data = taskCenter.query.data.value
  return data === undefined ? '—' : `${data.pages[0]?.total ?? 0}个`
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

function selectStatus(action: TaskStatusAction): void {
  taskCenter.setStatus(action.value)
  statusOpen.value = false
}
</script>

<template>
  <div class="mobile-list-page">
    <MobileListToolbar
      title="任务"
      :meta="totalLabel"
      :selector-label="statusLabel"
      :selector-aria-label="`选择任务状态，当前${statusLabel}`"
      filter-label="筛选"
      @selector="statusOpen = true"
      @filter="filterOpen = true"
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
        :loading-more="taskCenter.query.isFetchingNextPage.value"
        :has-more="Boolean(taskCenter.query.hasNextPage.value)"
        @refresh="refresh"
        @retry="taskCenter.query.refetch"
        @load-more="taskCenter.loadMore"
        @retry-load-more="taskCenter.retryLoadMore"
        @select="openTask"
      />
    </div>

    <VanActionSheet
      v-model:show="statusOpen"
      :actions="statusActions"
      cancel-text="取消"
      close-on-click-action
      safe-area-inset-bottom
      @select="selectStatus"
    />

    <TaskFilterSheet
      v-model="filterOpen"
      :filters="taskCenter.appliedFilters.value"
      @apply="taskCenter.applyFilters"
    />
  </div>
</template>
