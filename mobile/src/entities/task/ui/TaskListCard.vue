<script setup lang="ts">
import { Tag as VanTag } from 'vant'
import { computed } from 'vue'

import { MobileIcon } from '@/shared/icons'
import { MobileBusinessCardFrame } from '@/shared/ui'

import { TASK_STATUS_META } from '../model/status-meta'
import type { TaskListItem } from '../model/types'
import TaskStatusTag from './TaskStatusTag.vue'

const props = withDefaults(
  defineProps<{
    task: TaskListItem
    visualV2?: boolean
    buttonTestId?: string
  }>(),
  { buttonTestId: undefined, visualV2: false },
)

const emit = defineEmits<{
  select: [taskId: string]
}>()

const statusMeta = computed(() => TASK_STATUS_META[props.task.status])
const taskTimestamp = computed(
  () => props.task.startedAt ?? props.task.createdAt,
)
const taskTimeLabel = computed(() => (props.task.startedAt ? '开始' : '创建'))
const taskTimeText = computed(() => {
  const date = new Date(taskTimestamp.value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
})
const createdAtText = computed(() =>
  new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(new Date(props.task.createdAt)),
)
const deviceName = computed(
  () => props.task.deviceDisplayName.trim() || '设备未命名',
)
const legacyMetaTags = computed(() => {
  const skillName = props.task.skillDisplayName?.trim()
  return [
    deviceName.value,
    skillName &&
    skillName !== deviceName.value &&
    skillName !== props.task.executionName.trim()
      ? skillName
      : null,
  ].filter((value): value is string => Boolean(value))
})
</script>

<template>
  <MobileBusinessCardFrame
    v-if="visualV2"
    class="task-list-card task-list-card--visual-v2"
    :class="`task-list-card--${task.status}`"
    :label="`查看任务：${task.executionName}`"
    :button-test-id="buttonTestId"
    chevron-test-id="task-card-chevron"
    data-testid="task-card"
    @activate="emit('select', task.taskId)"
  >
    <template #leading>
      <span class="task-list-card-v2__artwork" data-testid="task-card-leading">
        <MobileIcon name="task" />
      </span>
    </template>

    <template #title>
      <span class="task-list-card-v2__name" data-testid="task-card-name">
        {{ task.executionName }}
      </span>
    </template>

    <template #status>
      <span class="task-list-card-v2__state" data-testid="task-card-state">
        <i class="task-list-card-v2__state-dot" aria-hidden="true" />
        <span>{{ statusMeta.label }}</span>
      </span>
    </template>

    <template #meta>
      <span class="task-list-card-v2__meta" data-testid="task-card-meta">
        <span>{{ taskTimeLabel }} {{ taskTimeText }}</span>
        <span aria-hidden="true">·</span>
        <span>{{ deviceName }}</span>
      </span>
    </template>
  </MobileBusinessCardFrame>

  <article
    v-else
    class="task-list-card task-list-card--legacy mobile-card"
    data-testid="task-card"
  >
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
        <VanTag v-for="tag in legacyMetaTags" :key="tag" plain>
          {{ tag }}
        </VanTag>
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
.task-list-card-v2__artwork {
  display: grid;
  width: var(--visual-v2-task-artwork-size);
  height: var(--visual-v2-task-artwork-size);
  color: var(--color-primary);
  background: var(--visual-v2-detail-weak-background);
  border: var(--border-width) solid var(--visual-v2-detail-weak-border-color);
  border-radius: var(--visual-v2-task-artwork-radius);
  place-items: center;
}

.task-list-card-v2__artwork .mobile-icon {
  width: var(--visual-v2-task-artwork-icon-size);
  height: var(--visual-v2-task-artwork-icon-size);
  font-size: var(--visual-v2-task-artwork-icon-size);
}

.task-list-card-v2__name,
.task-list-card-v2__state,
.task-list-card-v2__meta,
.task-list-card-v2__meta span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-list-card-v2__name {
  display: block;
}

.task-list-card-v2__state,
.task-list-card-v2__meta {
  display: flex;
  gap: var(--visual-v2-business-card-inline-gap);
  align-items: center;
}

.task-list-card-v2__state-dot {
  width: var(--visual-v2-business-card-status-dot-size);
  height: var(--visual-v2-business-card-status-dot-size);
  flex: none;
  background: currentcolor;
  border-radius: var(--radius-round);
}

.task-list-card--pending .task-list-card-v2__state {
  color: var(--status-warning);
}

.task-list-card--running .task-list-card-v2__state {
  color: var(--device-list-status-running);
}

.task-list-card--success .task-list-card-v2__state {
  color: var(--status-success);
}

.task-list-card--failed .task-list-card-v2__state,
.task-list-card--lost .task-list-card-v2__state {
  color: var(--status-danger);
}

.task-list-card-v2__meta {
  color: var(--visual-v2-business-card-meta-color);
}

.task-list-card--legacy {
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
  color: var(--text-tertiary);
  font-size: var(--icon-size-card-chevron);
  justify-self: end;
  place-items: center;
}
</style>
