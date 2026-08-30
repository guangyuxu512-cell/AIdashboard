<script setup lang="ts">
import { Tag as VanTag } from 'vant'
import { computed } from 'vue'

import { MobileIcon } from '@/shared/icons'

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
      <MobileIcon name="task" tile />
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

    <MobileIcon
      class="task-list-card__chevron"
      name="chevron-right"
      data-testid="task-card-chevron"
    />
  </article>
</template>

<style scoped>
.task-list-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  column-gap: var(--layout-card-leading-content-gap);
  padding: var(--layout-card-padding-y) var(--layout-card-padding-x);
  align-items: center;
  color: var(--text-primary);
}

.task-list-card__leading {
  display: grid;
  width: var(--layout-card-leading-icon-slot-width);
  color: var(--text-secondary);
  font-size: var(--icon-size-card-leading);
  place-items: center;
}

.task-list-card__content {
  display: grid;
  min-width: 0;
  gap: var(--layout-card-row-gap);
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
  gap: var(--layout-compact-gap);
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
  display: grid;
  width: var(--layout-card-trailing-icon-slot-width);
  justify-self: end;
  color: var(--text-tertiary);
  font-size: var(--icon-size-card-chevron);
  place-items: center;
}
</style>
