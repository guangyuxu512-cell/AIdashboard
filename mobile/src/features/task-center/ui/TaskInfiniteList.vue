<script setup lang="ts">
import {
  Button as VanButton,
  Empty as VanEmpty,
  List as VanList,
  NoticeBar as VanNoticeBar,
  PullRefresh as VanPullRefresh,
  Skeleton as VanSkeleton,
} from 'vant'

import { type TaskListItem, TaskListCard } from '@/entities/task'

defineProps<{
  tasks: TaskListItem[]
  initialLoading: boolean
  initialError: boolean
  backgroundError: boolean
  nextPageError: boolean
  errorMessage: string
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
  <VanNoticeBar
    v-if="backgroundError"
    type="warning"
    :text="`${errorMessage}，当前展示上次成功加载的数据`"
    wrapable
    data-testid="background-error"
  />

  <div v-if="initialLoading" class="task-list-state" data-testid="task-loading">
    <VanSkeleton v-for="index in 3" :key="index" title :row="3" />
  </div>

  <div
    v-else-if="initialError"
    class="task-list-state"
    data-testid="task-error"
  >
    <VanEmpty image="error" :description="errorMessage">
      <VanButton type="primary" @click="emit('retry')">重新加载</VanButton>
    </VanEmpty>
  </div>

  <VanPullRefresh v-else :model-value="refreshing" @refresh="emit('refresh')">
    <VanEmpty
      v-if="tasks.length === 0"
      description="当前筛选条件下暂无任务"
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
          class="task-list__item"
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
        <VanNoticeBar
          type="warning"
          :text="`${errorMessage}，已保留当前任务`"
          wrapable
        />
        <VanButton block @click="emit('retryLoadMore')">重试加载更多</VanButton>
      </div>
    </VanList>
  </VanPullRefresh>
</template>

<style scoped>
.task-list-state {
  display: grid;
  gap: var(--space-4);
  min-height: 50vh;
  padding: var(--space-4) max(var(--space-4), var(--safe-area-right))
    var(--space-4) max(var(--space-4), var(--safe-area-left));
  align-content: center;
}

.task-list {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-3)
    max(var(--layout-page-padding-x), var(--safe-area-right)) var(--space-6)
    max(var(--layout-page-padding-x), var(--safe-area-left));
}

.task-list__item {
  width: 100%;
  min-width: 0;
  min-height: var(--touch-target-min);
  padding: 0;
  color: inherit;
  text-align: left;
  background: transparent;
  border: 0;
  border-radius: var(--radius-card);
}

.task-list__item:focus-visible {
  outline: var(--border-width) solid var(--color-primary);
  outline-offset: var(--space-1);
}

.task-list__next-error {
  display: grid;
  gap: var(--space-2);
  padding: 0 max(var(--layout-page-padding-x), var(--safe-area-right))
    var(--space-4) max(var(--layout-page-padding-x), var(--safe-area-left));
}
</style>
