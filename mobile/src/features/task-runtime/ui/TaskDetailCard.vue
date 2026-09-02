<script setup lang="ts">
import type { TaskReadDto } from '@/entities/task'

import type { TaskDetailDeviceState } from '../model/task-detail-display'
import TaskDetailInfo from './TaskDetailInfo.vue'
import TaskDetailSummary from './TaskDetailSummary.vue'

defineProps<{
  task: TaskReadDto
  deviceName?: string | null
  deviceState: TaskDetailDeviceState
  now?: Date
}>()
</script>

<template>
  <section
    class="task-detail-card"
    data-testid="task-detail"
    aria-label="任务信息"
  >
    <TaskDetailSummary :task="task" :now="now" />
    <TaskDetailInfo
      :task="task"
      :device-name="deviceName"
      :device-state="deviceState"
    />
  </section>
</template>

<style scoped>
.task-detail-card {
  min-width: 0;
  flex: none;
  overflow: hidden;
  color: var(--visual-v2-page-text-primary);
  background: var(--visual-v2-detail-surface-background);
  border: var(--visual-v2-business-card-border-width) solid
    var(--visual-v2-detail-surface-border-color);
  border-radius: var(--visual-v2-business-card-radius);
  box-shadow: var(--visual-v2-detail-surface-shadow);
}
</style>
