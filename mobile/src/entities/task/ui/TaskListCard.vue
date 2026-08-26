<script setup lang="ts">
import { Progress as VanProgress } from 'vant'
import { computed } from 'vue'

import type { TaskListItem } from '../model/types'
import TaskStatusTag from './TaskStatusTag.vue'

const props = defineProps<{ task: TaskListItem }>()

const progressPercentage = computed(() => {
  const progress = props.task.progress
  if (!progress?.total || progress.total <= 0) return 0
  return Math.min(100, Math.max(0, (progress.current / progress.total) * 100))
})

const progressText = computed(() => {
  const progress = props.task.progress
  if (!progress) return null
  return progress.total === null
    ? `已处理 ${progress.current}`
    : `${progress.current} / ${progress.total}`
})

const createdAtText = computed(() =>
  new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(new Date(props.task.createdAt)),
)
</script>

<template>
  <article class="task-list-card" data-testid="task-card">
    <div class="task-list-card__heading">
      <h2>{{ task.executionName }}</h2>
      <TaskStatusTag :status="task.status" />
    </div>

    <dl class="task-list-card__facts">
      <div>
        <dt>设备</dt>
        <dd>{{ task.deviceDisplayName }}</dd>
      </div>
      <div>
        <dt>创建时间</dt>
        <dd>{{ createdAtText }}</dd>
      </div>
    </dl>

    <div class="task-list-card__progress">
      <div class="task-list-card__progress-label">
        <span>进度</span>
        <span>{{ progressText || '—' }}</span>
      </div>
      <VanProgress
        v-if="task.progress?.total !== null && task.progress"
        :percentage="progressPercentage"
        :show-pivot="false"
        stroke-width="6"
      />
      <p v-if="task.currentMessage" class="task-list-card__message">
        {{ task.currentMessage }}
      </p>
    </div>
  </article>
</template>

<style scoped>
.task-list-card {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-4);
  color: var(--text-primary);
  background: var(--bg-surface);
  border: var(--border-width) solid var(--border-subtle);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-surface);
}

.task-list-card__heading,
.task-list-card__progress-label {
  display: flex;
  gap: var(--space-2);
  align-items: flex-start;
  justify-content: space-between;
}

.task-list-card__heading h2 {
  min-width: 0;
  overflow: hidden;
  font-size: var(--font-size-label);
  line-height: var(--line-height-label);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-list-card__facts {
  display: grid;
  gap: var(--space-1);
  margin: 0;
}

.task-list-card__facts div {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: var(--space-2);
}

.task-list-card__facts dt,
.task-list-card__message,
.task-list-card__progress-label {
  color: var(--text-secondary);
}

.task-list-card__facts dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
  text-align: right;
}

.task-list-card__progress {
  display: grid;
  gap: var(--space-2);
}

.task-list-card__progress-label {
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
}

.task-list-card__message {
  overflow-wrap: anywhere;
}
</style>
