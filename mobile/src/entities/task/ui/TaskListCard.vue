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

const currentSummary = computed(() => {
  if (props.task.status === 'failed') return '任务执行失败'
  if (props.task.status === 'lost') return '任务状态已丢失'

  const message = props.task.currentMessage?.trim()
  if (message) return message

  if (props.task.status === 'pending') return '等待执行'
  if (props.task.status === 'running') return '正在执行'
  return '任务已成功完成'
})
</script>

<template>
  <article class="task-list-card mobile-card" data-testid="task-card">
    <div class="task-list-card__heading">
      <h2>{{ task.executionName }}</h2>
      <TaskStatusTag :status="task.status" />
    </div>

    <div class="task-list-card__meta">
      <span>{{ task.deviceDisplayName }}</span>
      <span aria-hidden="true">·</span>
      <time :datetime="task.createdAt">{{ createdAtText }}</time>
    </div>

    <p class="task-list-card__message" data-testid="task-card-message">
      {{ currentSummary }}
    </p>

    <div v-if="task.progress" class="task-list-card__progress">
      <div class="task-list-card__progress-label">
        <span>进度</span>
        <span>{{ progressText }}</span>
      </div>
      <VanProgress
        v-if="task.progress.total !== null"
        :percentage="progressPercentage"
        :show-pivot="false"
        stroke-width="var(--progress-height-compact)"
      />
    </div>
  </article>
</template>

<style scoped>
.task-list-card {
  display: grid;
  gap: var(--layout-card-row-gap);
  padding: var(--layout-card-padding);
  color: var(--text-primary);
}

.task-list-card__heading,
.task-list-card__progress-label {
  display: flex;
  min-width: 0;
  gap: var(--space-2);
  align-items: center;
  justify-content: space-between;
}

.task-list-card__meta {
  display: flex;
  min-width: 0;
  gap: var(--space-1);
  align-items: center;
}

.task-list-card__heading h2 {
  min-width: 0;
  overflow: hidden;
  font-size: var(--font-size-label);
  line-height: var(--line-height-label);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-list-card__meta,
.task-list-card__message,
.task-list-card__progress-label {
  color: var(--text-tertiary);
}

.task-list-card__message {
  color: var(--text-secondary);
}

.task-list-card__meta {
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
}

.task-list-card__meta span,
.task-list-card__meta time,
.task-list-card__message {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-list-card__meta time {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
}
</style>
