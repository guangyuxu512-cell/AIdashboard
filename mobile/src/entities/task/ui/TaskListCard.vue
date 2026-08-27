<script setup lang="ts">
import { Icon as VanIcon, Tag as VanTag } from 'vant'
import { computed } from 'vue'

import type { TaskListItem } from '../model/types'
import TaskStatusTag from './TaskStatusTag.vue'

const props = defineProps<{ task: TaskListItem }>()

const createdAtText = computed(() =>
  new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(new Date(props.task.createdAt)),
)

const metaTags = computed(() => {
  const deviceName = props.task.deviceDisplayName.trim() || '—'
  const skillName = props.task.skillDisplayName?.trim()
  return [
    deviceName,
    skillName &&
    skillName !== deviceName &&
    skillName !== props.task.executionName.trim()
      ? skillName
      : null,
  ].filter((value): value is string => Boolean(value))
})
</script>

<template>
  <article class="task-list-card mobile-card" data-testid="task-card">
    <span
      class="task-list-card__leading"
      data-testid="task-card-leading"
      aria-hidden="true"
    >
      <VanIcon name="todo-list-o" />
    </span>

    <span class="task-list-card__content">
      <h2 class="task-list-card__name" data-testid="task-card-name">
        {{ task.executionName }}
      </h2>
      <span class="task-list-card__state" data-testid="task-card-state">
        <TaskStatusTag :status="task.status" />
        <span aria-hidden="true">·</span>
        <time :datetime="task.createdAt">{{ createdAtText }}</time>
      </span>
      <span class="task-list-card__tags" data-testid="task-card-tags">
        <VanTag v-for="tag in metaTags" :key="tag" plain>{{ tag }}</VanTag>
      </span>
    </span>

    <VanIcon
      class="task-list-card__chevron"
      name="arrow"
      data-testid="task-card-chevron"
      aria-hidden="true"
    />
  </article>
</template>

<style scoped>
.task-list-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  column-gap: var(--space-3);
  padding: var(--layout-card-padding);
  align-items: center;
  color: var(--text-primary);
}

.task-list-card__leading {
  display: grid;
  color: var(--text-secondary);
  font-size: var(--icon-size-default);
  place-items: center;
}

.task-list-card__content {
  display: grid;
  min-width: 0;
  gap: var(--space-1);
}

.task-list-card__name,
.task-list-card__state,
.task-list-card__tags {
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
}

.task-list-card__state,
.task-list-card__tags {
  display: flex;
  gap: var(--space-1);
  align-items: center;
}

.task-list-card__name {
  font-size: var(--font-size-label);
  line-height: var(--line-height-label);
  text-overflow: ellipsis;
}

.task-list-card__state {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
}

.task-list-card__state time,
.task-list-card__tags .van-tag {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-list-card__chevron {
  color: var(--text-tertiary);
  font-size: var(--icon-size-small);
}
</style>
