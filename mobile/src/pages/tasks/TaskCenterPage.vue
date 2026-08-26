<script setup lang="ts">
import {
  Button as VanButton,
  showToast,
  Tab as VanTab,
  Tabs as VanTabs,
} from 'vant'
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { TASK_STATUSES, TASK_STATUS_META } from '@/entities/task'
import {
  TaskFilterSheet,
  TaskInfiniteList,
  useTaskCenter,
} from '@/features/task-center'
import { MOBILE_ROUTE_NAMES } from '@/app/router/routes'

const router = useRouter()
const filterOpen = ref(false)
const taskCenter = useTaskCenter()

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
  <div class="task-center-page">
    <div class="task-center-page__tabs">
      <VanTabs
        v-model:active="taskCenter.status.value"
        sticky
        shrink
        data-testid="status-tabs"
        @change="taskCenter.setStatus"
      >
        <VanTab title="全部" name="all" />
        <VanTab
          v-for="status in TASK_STATUSES"
          :key="status"
          :title="TASK_STATUS_META[status].label"
          :name="status"
        />
      </VanTabs>
    </div>

    <div class="task-center-page__toolbar">
      <p v-if="taskCenter.query.data.value !== undefined">
        {{ taskCenter.query.data.value.pages[0]?.total ?? 0 }} 个任务
      </p>
      <VanButton
        icon="filter-o"
        data-testid="open-filter"
        @click="filterOpen = true"
      >
        筛选
      </VanButton>
    </div>

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

    <TaskFilterSheet
      v-model="filterOpen"
      :filters="taskCenter.appliedFilters.value"
      @apply="taskCenter.applyFilters"
    />
  </div>
</template>

<style scoped>
.task-center-page {
  min-height: 100%;
}

.task-center-page__tabs {
  padding-right: var(--safe-area-right);
  padding-left: var(--safe-area-left);
  background: var(--bg-surface);
}

.task-center-page__toolbar {
  display: flex;
  min-height: var(--touch-target-min);
  padding: var(--space-2)
    max(var(--layout-page-padding-x), var(--safe-area-right)) var(--space-2)
    max(var(--layout-page-padding-x), var(--safe-area-left));
  align-items: center;
  justify-content: space-between;
  color: var(--text-secondary);
  background: var(--bg-app);
}
</style>
