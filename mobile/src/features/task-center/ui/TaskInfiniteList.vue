<script setup lang="ts">
import {
  Button as VanButton,
  Empty as VanEmpty,
  List as VanList,
  PullRefresh as VanPullRefresh,
  Skeleton as VanSkeleton,
} from 'vant'

import { type TaskListItem, TaskListCard } from '@/entities/task'

defineProps<{
  tasks: TaskListItem[]
  initialLoading: boolean
  initialError: boolean
  nextPageError: boolean
  refreshing: boolean
  loadingMore: boolean
  hasMore: boolean
}>()

const emit = defineEmits<{
  refresh: []
  retry: []
  loadMore: []
  retryLoadMore: []
  select: [taskId: string]
}>()
</script>

<template>
  <div v-if="initialLoading" class="task-list-state" data-testid="task-loading">
    <VanSkeleton v-for="index in 3" :key="index" title :row="3" />
  </div>

  <div
    v-else-if="initialError"
    class="task-list-state"
    data-testid="task-error"
  >
    <VanEmpty image="error" description="加载失败">
      <VanButton type="primary" @click="emit('retry')">重试</VanButton>
    </VanEmpty>
  </div>

  <VanPullRefresh
    v-else
    class="task-list-refresh"
    :model-value="refreshing"
    @refresh="emit('refresh')"
  >
    <VanEmpty
      v-if="tasks.length === 0"
      description="暂无任务"
      data-testid="task-empty"
    />
    <VanList
      v-else
      :loading="loadingMore"
      :finished="!hasMore || nextPageError"
      :finished-text="nextPageError ? '' : '没有更多任务了'"
      @load="emit('loadMore')"
    >
      <div class="task-list" data-testid="task-list">
        <button
          v-for="task in tasks"
          :key="task.taskId"
          type="button"
          class="task-list__item mobile-pressable mobile-pressable--card"
          @click="emit('select', task.taskId)"
        >
          <TaskListCard :task="task" />
        </button>
      </div>
      <div
        v-if="nextPageError"
        class="task-list__next-error"
        data-testid="task-next-page-error"
      >
        <span>加载失败</span>
        <VanButton block @click="emit('retryLoadMore')">重试</VanButton>
      </div>
    </VanList>
  </VanPullRefresh>
</template>

<style scoped>
.task-list-state {
  display: grid;
  gap: var(--space-4);
  min-height: 100%;
  padding: var(--space-4) max(var(--space-4), var(--safe-area-right))
    var(--space-4) max(var(--space-4), var(--safe-area-left));
  align-content: center;
}

.task-list-refresh {
  min-height: 100%;
}

.task-list {
  display: grid;
  gap: var(--layout-card-gap);
  padding: var(--space-2)
    max(var(--layout-page-padding-x), var(--safe-area-right)) var(--space-4)
    max(var(--layout-page-padding-x), var(--safe-area-left));
}

.task-list__item {
  width: 100%;
  min-width: 0;
  min-height: var(--touch-target-min);
  padding: 0;
  color: inherit;
  text-align: left;
  background: none;
  border: 0;
  border-radius: var(--radius-card);
}

.task-list__item:focus-visible {
  outline: var(--focus-ring-width) solid var(--focus-ring-color);
  outline-offset: var(--focus-ring-offset);
}

.task-list__next-error {
  display: grid;
  gap: var(--space-2);
  padding: 0 max(var(--layout-page-padding-x), var(--safe-area-right))
    var(--space-4) max(var(--layout-page-padding-x), var(--safe-area-left));
}
</style>
