<script setup lang="ts">
import {
  Button as VanButton,
  Loading as VanLoading,
  NoticeBar as VanNoticeBar,
} from 'vant'

import { TaskStatusTag, type ActiveTaskSummaryReadDto } from '@/entities/task'

withDefaults(
  defineProps<{
    task: ActiveTaskSummaryReadDto | null | undefined
    initialLoading: boolean
    initialError: boolean
    backgroundError: boolean
    errorMessage: string
    compact?: boolean
  }>(),
  { compact: false },
)

const emit = defineEmits<{
  retry: []
  select: [taskId: string]
}>()
</script>

<template>
  <section
    class="active-task-summary"
    :class="{ 'active-task-summary--compact': compact }"
    aria-label="当前任务"
  >
    <div v-if="!compact" class="active-task-summary__heading">
      <span>当前任务</span>
      <VanLoading v-if="initialLoading" size="var(--icon-size-small)">
        加载中
      </VanLoading>
    </div>

    <div v-else-if="initialLoading" class="active-task-summary__compact-state">
      <VanLoading size="var(--icon-size-small)">当前任务加载中</VanLoading>
    </div>

    <div v-if="initialError" class="active-task-summary__error">
      <VanNoticeBar
        class="mobile-notice-bar--warning"
        :text="errorMessage"
        wrapable
      />
      <VanButton block @click="emit('retry')">重新加载当前任务</VanButton>
    </div>

    <template v-else-if="!initialLoading">
      <VanNoticeBar
        v-if="backgroundError"
        class="mobile-notice-bar--warning"
        :text="`${errorMessage}，已保留当前任务状态`"
        wrapable
      />
      <button
        v-if="task"
        type="button"
        class="active-task-summary__task"
        :aria-label="`查看任务：${task.execution_display_name}`"
        @click="emit('select', task.task_id)"
      >
        <span class="active-task-summary__task-title">
          <strong>{{ task.execution_display_name }}</strong>
          <TaskStatusTag :status="task.status" />
        </span>
        <span
          v-if="task.latest_event && !compact"
          class="active-task-summary__message"
        >
          {{ task.latest_event.message }}
        </span>
      </button>
      <p v-else-if="task === null" class="active-task-summary__idle">空闲</p>
    </template>
  </section>
</template>

<style scoped>
.active-task-summary {
  display: grid;
  min-width: 0;
  gap: var(--space-2);
}

.active-task-summary__heading,
.active-task-summary__task-title {
  display: flex;
  min-width: 0;
  gap: var(--space-2);
  align-items: center;
  justify-content: space-between;
}

.active-task-summary__heading {
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
}

.active-task-summary__error {
  display: grid;
  gap: var(--space-2);
}

.active-task-summary__task {
  display: grid;
  width: 100%;
  min-width: 0;
  min-height: var(--touch-target-min);
  gap: var(--space-1);
  padding: var(--space-2);
  color: var(--text-primary);
  text-align: left;
  background: var(--bg-subtle);
  border: var(--border-width) solid var(--border-subtle);
  border-radius: var(--radius-control);
}

.active-task-summary__task:focus-visible {
  border-color: var(--focus-ring-color);
  outline: var(--focus-ring-width) solid var(--focus-ring-color);
  outline-offset: var(--focus-ring-offset);
}

.active-task-summary__task strong,
.active-task-summary__message {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.active-task-summary__message,
.active-task-summary__idle {
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
}

.active-task-summary__idle {
  display: grid;
  min-height: var(--touch-target-min);
  padding: var(--space-2);
  align-content: center;
  background: var(--bg-subtle);
  border-radius: var(--radius-control);
}

.active-task-summary__compact-state {
  display: flex;
  min-height: var(--touch-target-min);
  align-items: center;
}

.active-task-summary--compact .active-task-summary__task,
.active-task-summary--compact .active-task-summary__idle {
  padding: var(--space-2) var(--space-3);
}
</style>
