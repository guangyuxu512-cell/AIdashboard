<script setup lang="ts">
import { computed } from 'vue'

import {
  formatTaskDuration,
  resolveExecutionName,
  resolveTaskArtwork,
  TASK_STATUS_META,
  type TaskReadDto,
} from '@/entities/task'
import { MobileIcon } from '@/shared/icons'

const props = defineProps<{
  task: TaskReadDto
  now?: Date
}>()

const executionName = computed(() =>
  resolveExecutionName({
    execution_display_name: props.task.execution_display_name,
    skill_id: props.task.skill_id,
  }),
)
const statusMeta = computed(() => TASK_STATUS_META[props.task.status])
const artwork = computed(() => resolveTaskArtwork(props.task.status))
const durationText = computed(() =>
  formatTaskDuration(
    {
      status: props.task.status,
      startedAt: props.task.started_at,
      finishedAt: props.task.finished_at,
    },
    props.now,
  ),
)
</script>

<template>
  <div
    class="task-detail-summary"
    :class="`task-detail-summary--${task.status}`"
    data-testid="task-detail-summary"
  >
    <div class="task-detail-summary__leading" aria-hidden="true">
      <span
        class="task-detail-summary__artwork"
        :class="`task-detail-summary__artwork--${artwork.state}`"
        data-testid="task-detail-artwork"
      >
        <MobileIcon :name="artwork.icon" />
      </span>
    </div>

    <div class="task-detail-summary__content">
      <h1 class="task-detail-summary__title" data-testid="task-detail-title">
        {{ executionName }}
      </h1>
      <p class="task-detail-summary__status" data-testid="task-detail-status">
        <i class="task-detail-summary__status-dot" aria-hidden="true" />
        <span>{{ statusMeta.label }}</span>
        <template v-if="durationText">
          <span aria-hidden="true">·</span>
          <span
            class="task-detail-summary__duration"
            data-testid="task-detail-duration"
          >
            {{ durationText }}
          </span>
        </template>
      </p>
    </div>
  </div>
</template>

<style scoped>
.task-detail-summary {
  display: grid;
  min-width: 0;
  min-height: var(--visual-v2-business-card-min-height);
  padding: var(--visual-v2-business-card-padding-top)
    var(--visual-v2-business-card-padding-right)
    var(--visual-v2-business-card-padding-bottom)
    var(--visual-v2-business-card-padding-left);
  grid-template-columns: var(--visual-v2-business-card-leading-column) minmax(
      0,
      1fr
    );
  align-items: center;
}

.task-detail-summary__leading {
  display: flex;
  height: var(--visual-v2-business-card-leading-height);
  align-items: center;
  justify-content: center;
}

.task-detail-summary__artwork {
  display: grid;
  width: var(--visual-v2-task-artwork-size);
  height: var(--visual-v2-task-artwork-size);
  border: var(--border-width) solid currentcolor;
  border-radius: var(--visual-v2-task-artwork-radius);
  place-items: center;
}

.task-detail-summary__artwork--running {
  color: var(--status-success);
  background: var(--status-success-soft);
}

.task-detail-summary__artwork--pending {
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.task-detail-summary__artwork--error {
  color: var(--status-danger);
  background: var(--status-danger-soft);
}

.task-detail-summary__artwork--done {
  color: var(--status-neutral);
  background: var(--status-neutral-soft);
}

.task-detail-summary__artwork .mobile-icon {
  width: var(--visual-v2-task-artwork-icon-size);
  height: var(--visual-v2-task-artwork-icon-size);
  font-size: var(--visual-v2-task-artwork-icon-size);
}

.task-detail-summary__content,
.task-detail-summary__title,
.task-detail-summary__status,
.task-detail-summary__duration {
  min-width: 0;
}

.task-detail-summary__title {
  margin: 0 0 var(--visual-v2-task-card-title-gap);
  overflow: hidden;
  color: var(--visual-v2-page-text-primary);
  font-size: var(--typography-v2-business-card-title-size);
  font-weight: var(--typography-v2-business-card-title-weight);
  line-height: var(--typography-v2-business-card-title-line-height);
  letter-spacing: var(--typography-v2-business-card-title-letter-spacing);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-detail-summary__status {
  display: flex;
  gap: var(--visual-v2-business-card-inline-gap);
  align-items: center;
  overflow: hidden;
  font-size: var(--typography-v2-status-size);
  font-weight: var(--typography-v2-status-weight);
  line-height: var(--typography-v2-status-line-height);
  white-space: nowrap;
}

.task-detail-summary--pending .task-detail-summary__status {
  color: var(--status-warning);
}

.task-detail-summary--running .task-detail-summary__status {
  color: var(--visual-v2-detail-status-running);
}

.task-detail-summary--success .task-detail-summary__status {
  color: var(--status-success);
}

.task-detail-summary--failed .task-detail-summary__status,
.task-detail-summary--lost .task-detail-summary__status {
  color: var(--status-danger);
}

.task-detail-summary__status-dot {
  width: var(--visual-v2-business-card-status-dot-size);
  height: var(--visual-v2-business-card-status-dot-size);
  flex: none;
  background: currentcolor;
  border-radius: var(--radius-round);
}

.task-detail-summary__duration {
  overflow: hidden;
  color: var(--visual-v2-business-card-meta-color);
  font-size: var(--typography-v2-meta-size);
  font-weight: var(--typography-v2-meta-weight);
  line-height: var(--typography-v2-meta-line-height);
  text-overflow: ellipsis;
}
</style>
